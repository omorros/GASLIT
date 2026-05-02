"use client";

import { useState } from "react";
import { ConvAIWidget } from "@/components/voice/ConvAIWidget";
import { DossierTTS } from "@/components/voice/DossierTTS";
import { ForensicQAMic } from "@/components/voice/ForensicQAMic";
import { LiveKitVoiceInput } from "@/components/voice/LiveKitVoiceInput";
import { QuarantineDossierVoice } from "@/components/voice/QuarantineDossierVoice";
import { VoiceFallback, useVoiceFallbackHotkey } from "@/components/voice/VoiceFallback";

const SAMPLE_DOSSIER =
  "Memory m-4419 quarantined at 14:22 UTC. Drift score 0.91, threshold 0.62. Cohort variance 4.2 times baseline.";

/** Optional: set in frontend/.env.local so forensic Q&A hits a real quarantine doc. */
const DEMO_QUARANTINE_ID = process.env.NEXT_PUBLIC_DEMO_QUARANTINE_ID ?? "";

/**
 * Voice + ElevenLabs smoke test (LiveKit STT, dossier TTS, Conv AI, fallback).
 * Main marketing site lives at `/`; this route is for integration checks.
 */
export default function VoiceSmokePage() {
  const [showDossier, setShowDossier] = useState(false);
  useVoiceFallbackHotkey("attacker_room");

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 22, letterSpacing: "0.04em" }}>GASLIT — voice integration</h1>
      <p style={{ opacity: 0.75, fontSize: 14 }}>
        Smoke-test LiveKit + ElevenLabs. Production UI mounts these inside the operator console / dossier.
      </p>
      <p
        style={{
          marginTop: 10,
          fontSize: 12,
          opacity: 0.65,
          padding: 10,
          borderLeft: "3px solid #c9a227",
          background: "#1a1810",
        }}
      >
        <strong>Local dev:</strong> Terminal A — repo root:{" "}
        <code style={{ color: "#e8dcc8" }}>uvicorn api.main:app --port 8002</code> (venv + <code style={{ color: "#e8dcc8" }}>.env</code>{" "}
        with <code style={{ color: "#e8dcc8" }}>MONGODB_URI</code>, <code style={{ color: "#e8dcc8" }}>LIVEKIT_URL</code>,{" "}
        <code style={{ color: "#e8dcc8" }}>LIVEKIT_API_KEY</code>, <code style={{ color: "#e8dcc8" }}>LIVEKIT_API_SECRET</code>,{" "}
        <code style={{ color: "#e8dcc8" }}>ELEVENLABS_API_KEY</code>, <code style={{ color: "#e8dcc8" }}>ELEVENLABS_AGENT_ID</code> — in the{" "}
        <strong>repo root</strong> <code style={{ color: "#e8dcc8" }}>.env</code>, not only Next&apos;s{" "}
        <code style={{ color: "#e8dcc8" }}>frontend/.env.local</code>
        ). Terminal B: <code style={{ color: "#e8dcc8" }}>cd frontend && npm run dev</code>. Open this page at{" "}
        <code style={{ color: "#e8dcc8" }}>/voice</code>. Next proxies <code style={{ color: "#e8dcc8" }}>/backend/*</code> → API :8002 (leave{" "}
        <code style={{ color: "#e8dcc8" }}>NEXT_PUBLIC_API_BASE</code> unset unless you need a direct URL).
      </p>

      <div style={{ display: "grid", gap: 20, marginTop: 24 }}>
        <LiveKitVoiceInput />
        <button
          type="button"
          onClick={() => setShowDossier((v) => !v)}
          style={{ justifySelf: "start", padding: "8px 14px" }}
        >
          {showDossier ? "Hide" : "Show"} dossier TTS demo
        </button>
        {showDossier && (
          <section style={{ padding: 16, border: "1px solid #c9a227", borderRadius: 8 }}>
            <pre style={{ margin: 0, fontSize: 13, whiteSpace: "pre-wrap" }}>{SAMPLE_DOSSIER}</pre>
            <DossierTTS text={SAMPLE_DOSSIER} delayMs={1000} />
          </section>
        )}
        <section>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>Quarantine → dossier (WebSocket)</h3>
          <p style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>
            Subscribes to <code>NEXT_PUBLIC_WS_URL</code> (<code>type: quarantine</code>, <code>dossier_text</code>) and plays TTS — same path as the operator console.
          </p>
          <QuarantineDossierVoice />
        </section>
        <ForensicQAMic quarantineId={DEMO_QUARANTINE_ID || undefined} />
        <section>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>ElevenLabs Conversational AI</h3>
          <ConvAIWidget />
        </section>
        <VoiceFallback />
      </div>
    </main>
  );
}
