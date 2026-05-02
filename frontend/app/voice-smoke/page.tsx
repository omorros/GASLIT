"use client";

import { useState } from "react";
import { ConvAIWidget } from "@/components/voice/ConvAIWidget";
import { DossierTTS } from "@/components/voice/DossierTTS";
import { ForensicQAMic } from "@/components/voice/ForensicQAMic";
import { LiveKitVoiceInput } from "@/components/voice/LiveKitVoiceInput";
import { VoiceFallback, useVoiceFallbackHotkey } from "@/components/voice/VoiceFallback";

const SAMPLE_DOSSIER =
  "Memory m-4419 quarantined at 14:22 UTC. Drift score 0.91, threshold 0.62. Cohort variance 4.2 times baseline.";

export default function Home() {
  const [showDossier, setShowDossier] = useState(false);
  useVoiceFallbackHotkey("attacker_room");

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 22, letterSpacing: "0.04em" }}>GASLIT — voice integration</h1>
      <p style={{ opacity: 0.75, fontSize: 14 }}>
        Teammate 3 will mount these inside DualConsole / dossier. This page smoke-tests LiveKit + ElevenLabs.
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
        <ForensicQAMic />
        <section>
          <h3 style={{ fontSize: 15, marginBottom: 8 }}>ElevenLabs Conversational AI</h3>
          <ConvAIWidget />
        </section>
        <VoiceFallback />
      </div>
    </main>
  );
}
