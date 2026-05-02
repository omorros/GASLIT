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
import { DossierTTS } from "@/components/voice/DossierTTS";
import { fetchLiveKitToken, postForensicQA } from "@/lib/api";

function Listen({
  onFinal,
}: {
  onFinal: (text: string) => void;
}) {
  const room = useRoomContext();
  useEffect(() => {
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
      void room.off(RoomEvent.TranscriptionReceived, handler);
    };
  }, [room, onFinal]);
  return null;
}

export function ForensicQAMic({
  roomName = "forensic_room",
  quarantineId,
  /** ElevenLabs Flash TTS after each `/api/forensic-qa` answer (PRD dossier-style readout). */
  speakAnswers = true,
}: {
  roomName?: string;
  quarantineId?: string;
  speakAnswers?: boolean;
}) {
  const [token, setToken] = useState<string | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lastAnswer, setLastAnswer] = useState<string | null>(null);
  const identity = useMemo(() => `forensic-${Math.random().toString(36).slice(2, 10)}`, []);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const j = await fetchLiveKitToken(roomName, identity);
        if (!c) {
          setToken(j.token);
          setUrl(j.url);
        }
      } catch (e) {
        if (!c) setErr(String(e));
      }
    })();
    return () => {
      c = true;
    };
  }, [roomName, identity]);

  const onFinal = useCallback(
    async (text: string) => {
      try {
        const j = await postForensicQA(text, quarantineId);
        setLastAnswer(j.answer);
      } catch (e) {
        setErr(String(e));
      }
    },
    [quarantineId],
  );

  if (err && !token)
    return (
      <section style={card}>
        <h4 style={{ margin: 0 }}>Forensic Q&amp;A mic</h4>
        <p style={{ color: "#f66" }}>{err}</p>
      </section>
    );

  if (!token || !url)
    return (
      <section style={card}>
        <h4 style={{ margin: 0 }}>Forensic Q&amp;A mic</h4>
        <p>Connecting…</p>
      </section>
    );

  return (
    <section style={card}>
      <h4 style={{ margin: 0 }}>Forensic Q&amp;A mic</h4>
      <p style={{ fontSize: 12, opacity: 0.8 }}>Room: {roomName}</p>
      <LiveKitRoom serverUrl={url} token={token} connect={true} audio={true} video={false}>
        <Listen onFinal={onFinal} />
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 8 }}>
          <TrackToggle source={Track.Source.Microphone} />
          <span style={{ fontSize: 13 }}>Ask a question</span>
        </div>
        <RoomAudioRenderer />
      </LiveKitRoom>
      {lastAnswer && (
        <>
          <pre
            style={{
              marginTop: 12,
              padding: 8,
              background: "#0d0d0f",
              border: "1px solid #2a2a2e",
              fontSize: 13,
              whiteSpace: "pre-wrap",
            }}
          >
            {lastAnswer}
          </pre>
          {speakAnswers && (
            <DossierTTS
              text={lastAnswer}
              delayMs={400}
              statusLabel="Answer audio"
            />
          )}
        </>
      )}
    </section>
  );
}

const card: CSSProperties = {
  border: "1px solid #2a2a2e",
  borderRadius: 8,
  padding: 12,
  background: "#121214",
};
