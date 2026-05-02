"use client";

import { useEffect, useState } from "react";
import { DossierTTS } from "@/components/voice/DossierTTS";

type QuarantinePayload = {
  quarantine_id?: string;
  memory_id?: string;
  dossier_text?: string;
};

/**
 * Listens to the GASLIT WebSocket (`quarantine` events) and auto-plays ElevenLabs
 * dossier TTS when `dossier_text` is present — PRD §11 dossier readout.
 */
export function QuarantineDossierVoice({
  delayMs = 1000,
  showText = true,
}: {
  delayMs?: number;
  /** Show dossier text on screen for the audience */
  showText?: boolean;
}) {
  const [dossierText, setDossierText] = useState<string | null>(null);
  const [meta, setMeta] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<"off" | "connecting" | "live" | "error">("off");

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_WS_URL?.trim();
    if (!url) {
      setWsStatus("error");
      return;
    }

    setWsStatus("connecting");
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      setWsStatus("error");
      return;
    }

    ws.onopen = () => setWsStatus("live");
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => setWsStatus((s) => (s === "live" ? "off" : s));

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string) as {
          type?: string;
          payload?: QuarantinePayload;
        };
        if (msg.type !== "quarantine" || !msg.payload?.dossier_text?.trim()) return;
        const p = msg.payload;
        setDossierText(p.dossier_text!.trim());
        setMeta(
          [p.quarantine_id, p.memory_id].filter(Boolean).join(" · ") || null,
        );
      } catch {
        /* ignore malformed */
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  if (wsStatus === "error" && !dossierText) {
    return (
      <p style={{ fontSize: 12, opacity: 0.65 }}>
        WebSocket not connected — set <code>NEXT_PUBLIC_WS_URL</code> (default <code>ws://127.0.0.1:8003</code>) and run{" "}
        <code>ws/bridge.py</code>.
      </p>
    );
  }

  if (!dossierText) {
    return (
      <p style={{ fontSize: 12, opacity: 0.55 }}>
        Waiting for <code>quarantine</code> event… (WS: {wsStatus})
      </p>
    );
  }

  return (
    <section style={{ marginTop: 12, padding: 12, border: "1px solid #c9a227", borderRadius: 8, background: "#0d0d0f" }}>
      {meta && (
        <p style={{ fontSize: 11, fontFamily: "monospace", opacity: 0.7, marginBottom: 8 }}>{meta}</p>
      )}
      {showText && (
        <pre style={{ margin: 0, fontSize: 13, whiteSpace: "pre-wrap", color: "#e8e6e3" }}>{dossierText}</pre>
      )}
      <DossierTTS text={dossierText} delayMs={delayMs} play={true} />
    </section>
  );
}
