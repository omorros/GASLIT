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
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchLiveKitToken, postVoiceInput } from "@/lib/api";

type Mode = "livekit" | "web-speech";

function TranscriptionListener({
  onFinal,
  mode,
}: {
  onFinal: (text: string) => void;
  mode: Mode;
}) {
  const room = useRoomContext();

  useEffect(() => {
    if (mode !== "livekit") return;

    const handler = (segments: TranscriptionSegment[]) => {
      const text = segments
        .filter((s) => s.final)
        .map((s) => s.text)
        .join(" ")
        .trim();
      if (text) onFinal(text);
    };

    room.on(RoomEvent.TranscriptionReceived, handler);
    return () => {
      room.off(RoomEvent.TranscriptionReceived, handler);
    };
  }, [room, onFinal, mode]);

  return null;
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

  if (err && !token)
    return (
      <section style={card}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <p style={{ color: "#f66" }}>{err}</p>
        <p style={{ fontSize: 12 }}>Set LIVEKIT_* on the API and NEXT_PUBLIC_API_BASE if needed.</p>
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
      {mode === "web-speech" ? (
        <PushToTalkWebSpeech onFinal={sendTranscript} />
      ) : (
        <LiveKitRoom serverUrl={url} token={token} connect={true} audio={true} video={false}>
          <TranscriptionListener onFinal={sendTranscript} mode="livekit" />
          <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
            <TrackToggle source={Track.Source.Microphone} />
            <span style={{ fontSize: 14 }}>Microphone · waveform via LiveKit</span>
          </div>
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
