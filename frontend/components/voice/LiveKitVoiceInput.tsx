"use client";

import {
  LiveKitRoom,
  RoomAudioRenderer,
  TrackToggle,
  useRoomContext,
} from "@livekit/components-react";
import "@livekit/components-styles";
import { RoomEvent, Track, TranscriptionSegment } from "livekit-client";
import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchLiveKitToken, postVoiceInput } from "@/lib/api";

type Mode = "livekit" | "web-speech";

const MAX_TRANSCRIPT_LINES = 80;

function TranscriptionListener({
  onSegments,
  mode,
}: {
  onSegments: (segments: TranscriptionSegment[]) => void;
  mode: Mode;
}) {
  const room = useRoomContext();

  useEffect(() => {
    if (mode !== "livekit") return;

    const handler = (segments: TranscriptionSegment[]) => {
      onSegments(segments);
    };

    room.on(RoomEvent.TranscriptionReceived, handler);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handler);
    };
  }, [room, onSegments, mode]);

  return null;
}

function TranscriptTerminal({
  lines,
  interim,
}: {
  lines: readonly string[];
  interim: string;
}) {
  const scrollRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, interim]);

  return (
    <pre
      ref={scrollRef}
      style={{
        marginTop: 12,
        padding: 10,
        minHeight: 120,
        maxHeight: 220,
        overflow: "auto",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: 12,
        lineHeight: 1.45,
        background: "#0a0a0c",
        color: "#9dffa8",
        border: "1px solid #1e3d1e",
        borderRadius: 6,
      }}
    >
      {lines.map((ln, i) => (
        <span key={i}>
          <span style={{ opacity: 0.45 }}>$ </span>
          {ln}
          {"\n"}
        </span>
      ))}
      {interim ? (
        <span style={{ color: "#7bdc8f" }}>
          <span style={{ opacity: 0.45 }}>&gt; </span>
          {interim}
          <span>▌</span>
        </span>
      ) : null}
    </pre>
  );
}

function PushToTalkWebSpeech({ onFinal }: { onFinal: (text: string) => void }) {
  const [supported, setSupported] = useState(true);

  const start = () => {
    if (typeof window === "undefined") return;
    const W = window as unknown as {
      SpeechRecognition?: new () => SpeechRecognition;
      webkitSpeechRecognition?: new () => SpeechRecognition;
    };
    const R = W.SpeechRecognition ?? W.webkitSpeechRecognition;
    if (!R) {
      setSupported(false);
      return;
    }
    const rec = new R();
    rec.lang = "en-GB";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (ev: SpeechRecognitionEvent) => {
      const t = ev.results[0]?.[0]?.transcript?.trim();
      if (t) onFinal(t);
    };
    rec.start();
  };

  if (!supported)
    return <p style={{ color: "#f66" }}>Web Speech API not available in this browser.</p>;

  return (
    <div>
      <button type="button" onClick={start} style={btn}>
        Push to talk (Web Speech fallback)
      </button>
      <p style={{ fontSize: 12, opacity: 0.7, marginTop: 8 }}>
        Uses browser STT — enable LiveKit transcriptions + set mode to <code>livekit</code> for production.
      </p>
    </div>
  );
}

export function LiveKitVoiceInput({
  roomName = "attacker_room",
  title = "Attacker voice (left console)",
}: {
  roomName?: string;
  title?: string;
}) {
  const mode = (process.env.NEXT_PUBLIC_VOICE_TRANSCRIPTION_MODE as Mode) ?? "livekit";
  const [token, setToken] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [transcriptLines, setTranscriptLines] = useState<string[]>([]);
  const [interimLine, setInterimLine] = useState("");
  const lastPostedFinal = useRef<string>("");
  const identity = useMemo(() => `gaslit-${Math.random().toString(36).slice(2, 10)}`, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const j = await fetchLiveKitToken(roomName, identity);
        if (!cancelled) {
          setToken(j.token);
          setUrl(j.url);
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [roomName, identity]);

  const sendTranscript = useCallback(
    async (text: string) => {
      try {
        await postVoiceInput(text, mode === "web-speech" ? "web-speech" : "livekit", roomName);
      } catch (e) {
        setErr(String(e));
      }
    },
    [mode, roomName],
  );

  const appendFinalLine = useCallback((text: string) => {
    const t = text.trim();
    if (!t) return;
    setTranscriptLines((prev) => {
      const next = [...prev, t];
      return next.length > MAX_TRANSCRIPT_LINES ? next.slice(-MAX_TRANSCRIPT_LINES) : next;
    });
    setInterimLine("");
  }, []);

  const onTranscriptionSegments = useCallback(
    (segments: TranscriptionSegment[]) => {
      const interim = segments
        .filter((s) => !s.final)
        .map((s) => s.text)
        .join(" ")
        .trim();
      setInterimLine(interim);

      const finalText = segments
        .filter((s) => s.final)
        .map((s) => s.text)
        .join(" ")
        .trim();
      if (!finalText) return;
      if (finalText === lastPostedFinal.current) return;
      lastPostedFinal.current = finalText;
      appendFinalLine(finalText);
      void sendTranscript(finalText);
    },
    [appendFinalLine, sendTranscript],
  );

  const onWebSpeechFinal = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t || t === lastPostedFinal.current) return;
      lastPostedFinal.current = t;
      appendFinalLine(t);
      void sendTranscript(t);
    },
    [appendFinalLine, sendTranscript],
  );

  if (err && !token)
    return (
      <section style={card}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <p style={{ color: "#f66" }}>{err}</p>
        <p style={{ fontSize: 12 }}>
          Ensure <code>uvicorn</code> is running with <code>LIVEKIT_URL</code>, <code>LIVEKIT_API_KEY</code>,{" "}
          <code>LIVEKIT_API_SECRET</code> in its <code>.env</code>. By default the UI calls the API via{" "}
          <code>/backend</code> (Next proxy to :8002).
        </p>
      </section>
    );

  if (!token || !url)
    return (
      <section style={card}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <p>Connecting token…</p>
      </section>
    );

  return (
    <section style={card}>
      <h3 style={{ margin: 0 }}>{title}</h3>
      <p style={{ fontSize: 11, opacity: 0.55, marginTop: 6 }}>
        Transcript (interim vs final) — finals POST to <code>/api/voice-input</code>.
      </p>
      {mode === "web-speech" ? (
        <>
          <PushToTalkWebSpeech onFinal={onWebSpeechFinal} />
          <TranscriptTerminal lines={transcriptLines} interim="" />
        </>
      ) : (
        <LiveKitRoom serverUrl={url} token={token} connect={true} audio={true} video={false}>
          <TranscriptionListener onSegments={onTranscriptionSegments} mode="livekit" />
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
            <TrackToggle source={Track.Source.Microphone} />
            <span style={{ fontSize: 14 }}>Microphone · waveform via LiveKit</span>
          </div>
          <TranscriptTerminal lines={transcriptLines} interim={interimLine} />
          <RoomAudioRenderer />
        </LiveKitRoom>
      )}
    </section>
  );
}

const btn: CSSProperties = {
  padding: "8px 14px",
  borderRadius: 6,
  border: "1px solid #c9a227",
  background: "#1a1810",
  color: "#e8e6e3",
};

const card: CSSProperties = {
  border: "1px solid #2a2a2e",
  borderRadius: 8,
  padding: 12,
  background: "#121214",
};
