"use client";

import { postTTS } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

/**
 * Fetches ElevenLabs Flash TTS from the API and auto-plays after `delayMs` (PRD: ~1s after dossier opens).
 */
export function DossierTTS({
  text,
  delayMs = 1000,
  play = true,
}: {
  text: string | null;
  delayMs?: number;
  play?: boolean;
}) {
  const [status, setStatus] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!text?.trim() || !play) return;

    let cancelled = false;
    const t = window.setTimeout(async () => {
      setStatus("loading");
      try {
        const buf = await postTTS(text);
        if (cancelled) return;
        const blob = new Blob([buf], { type: "audio/mpeg" });
        const url = URL.createObjectURL(blob);
        const a = new Audio(url);
        audioRef.current = a;
        a.onended = () => {
          URL.revokeObjectURL(url);
          setStatus("idle");
        };
        await a.play();
        setStatus("playing");
      } catch {
        setStatus("error");
      }
    }, delayMs);

    return () => {
      cancelled = true;
      clearTimeout(t);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, [text, delayMs, play]);

  if (!text) return null;

  return (
    <div style={{ fontSize: 12, opacity: 0.75, marginTop: 8 }}>
      Dossier audio: {status === "loading" ? "loading…" : status === "playing" ? "playing" : status === "error" ? "error" : "queued"}
    </div>
  );
}
