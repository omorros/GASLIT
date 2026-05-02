"use client";

import Link from "next/link";
import NavBar from "@/components/NavBar";

export default function ConsolePage() {
  return (
    <div className="flex flex-col min-h-screen bg-neutral-950">
      <NavBar />

      <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 text-center">
        {/* Status indicator */}
        <div className="flex items-center gap-2 rounded-full border border-[#76b900]/30 bg-[#76b900]/10 px-4 py-1.5 text-[11px] font-mono uppercase tracking-widest text-[#8fd400]">
          <span className="relative flex h-1.5 w-1.5">
            <span className="tv-pulse-dot absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-amber-500" />
          </span>
          operator console · building
        </div>

        <h1 className="font-['Space_Grotesk'] font-black text-white" style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>
          Operator Console
        </h1>

        <p className="max-w-md text-neutral-400 text-[15px] leading-relaxed">
          The full operator console with dual-pane chat, drift gauge, memory trust score,
          LiveKit voice input, forensic dossier, and kill-restart is being wired up by Dev C.
        </p>

        {/* Components coming */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full text-left">
          {[
            { name: "DualConsole", desc: "LEFT (unprotected) vs RIGHT (GASLIT)", done: false },
            { name: "DriftGauge", desc: "Live drift score bar per memory", done: false },
            { name: "FiredBlockedIndicator", desc: "32px+ red/green full-pane banner", done: false },
            { name: "MoneyLedger", desc: "$50K slot-machine animation on FIRED", done: false },
            { name: "MemoryTrustScore", desc: "0–100 score, amber/red thresholds", done: false },
            { name: "DossierRenderer", desc: "ElevenLabs TTS forensic dossier", done: false },
            { name: "MinjaAttackButton", desc: "▶ Run MINJA Attack with narration", done: false },
            { name: "TerminalKillRestart", desc: "kill -9 Sentinel → checkpoint resume", done: false },
          ].map(({ name, desc }) => (
            <div key={name} className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/5 p-3">
              <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-amber-500/60" />
              <div>
                <p className="text-[12px] font-mono font-bold text-white">{name}</p>
                <p className="text-[11px] text-neutral-500">{desc}</p>
              </div>
            </div>
          ))}
        </div>

        <Link
          href="/"
          className="flex items-center gap-1.5 text-sm font-semibold text-neutral-500 hover:text-[#8fd400] transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
          Back to home
        </Link>
      </main>
    </div>
  );
}
