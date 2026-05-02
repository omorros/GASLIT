"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import { useGaslitEvents } from "@/hooks/useGaslitEvents";
import { useTrustScore } from "@/hooks/useTrustScore";
import { useSentinelStatus } from "@/hooks/useSentinelStatus";
import { useScenarioPlayer } from "@/hooks/useScenarioPlayer";
import { DriftGaugeStrip } from "@/components/console/DriftGaugeStrip";
import { DualConsole, type DualConsoleHandle } from "@/components/console/DualConsole";
import { ScenarioHeader } from "@/components/console/ScenarioHeader";
import { AgentSpotlight } from "@/components/console/AgentSpotlight";
import { DossierPanel } from "@/components/console/DossierPanel";
import { ManualPrompt } from "@/components/console/ManualPrompt";
import { EventTape } from "@/components/console/EventTape";

export default function ConsolePage() {
  const ev = useGaslitEvents();
  const trust = useTrustScore(4000);
  const { status: sentinel } = useSentinelStatus(3000);

  const dualHandleRef = useRef<DualConsoleHandle | null>(null);
  const [scribeBusy, setScribeBusy] = useState(false);

  const onHandle = useCallback((h: DualConsoleHandle) => {
    dualHandleRef.current = h;
  }, []);

  const dualSend = useCallback(
    async (message: string, opts?: { user_id?: string; turn_number?: number }) => {
      if (!dualHandleRef.current) return {};
      return await dualHandleRef.current.send(message, opts);
    },
    [],
  );

  const scenario = useScenarioPlayer({ dualSend });
  const spec = scenario.spec;
  const latestQuarantine = ev.quarantines[0];
  const sentinelOnline = sentinel?.status === "online";

  const manualSend = useCallback(
    async (message: string, user_id: string) => {
      await dualSend(message, { user_id });
    },
    [dualSend],
  );

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--op-bg)] text-[var(--op-text)]">
      {/* Top bar */}
      <header className="flex shrink-0 items-center justify-between border-b border-[var(--op-border)] bg-white px-6 py-2.5">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 text-[15px] font-bold tracking-tight">
            <span className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#76b900] opacity-50" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[#76b900]" />
            </span>
            <span className="text-[#76b900]">GAS</span>
            <span className="text-neutral-900">LIT</span>
          </Link>
          <span className="hidden text-[13px] text-neutral-400 md:inline">Operator Console</span>
        </div>
        <div className="flex items-center gap-5 text-[11.5px] text-neutral-500">
          <Indicator
            label="websocket"
            value={ev.state}
            tone={ev.state === "live" ? "ok" : ev.state === "connecting" ? "warn" : "bad"}
          />
          <Indicator
            label="sentinel"
            value={sentinel?.status ?? "…"}
            tone={sentinelOnline ? "ok" : "warn"}
            extra={sentinel?.superstep ? `superstep ${sentinel.superstep}` : undefined}
          />
          <Indicator label="memories" value={`${trust?.n_memories ?? 0}`} tone="neutral" />
          <Indicator
            label="quarantined"
            value={`${trust?.n_quarantined ?? 0}`}
            tone={(trust?.n_quarantined ?? 0) > 0 ? "warn" : "neutral"}
          />
        </div>
      </header>

      {/* Main grid — fits viewport */}
      <main className="flex min-h-0 flex-1 flex-col gap-2.5 px-6 pt-2.5 pb-3">
        <ScenarioHeader
          days={scenario.days}
          currentDay={scenario.state.currentDay}
          spec={spec}
          busy={scenario.state.busy}
          isDone={scenario.isDone}
          onAdvance={scenario.advance}
          onReset={scenario.reset}
        />

        {/* Storyline narrative + drift gauge */}
        <section className="grid grid-cols-1 gap-2.5 lg:grid-cols-[1fr_440px]">
          <article className="rounded-2xl border border-[var(--op-border)] bg-white px-5 py-2.5">
            {spec ? (
              <div className="op-slide-up flex flex-col gap-0.5">
                <span className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-[var(--op-green)]">
                  {spec.date} · attack day {spec.day}
                </span>
                <h2 className="font-['Space_Grotesk'] text-[15px] font-bold tracking-tight text-neutral-900">
                  {spec.title} <span className="font-medium text-neutral-400">— {spec.subtitle}</span>
                </h2>
                <p className="text-[12px] leading-snug text-neutral-600">{spec.narrative}</p>
              </div>
            ) : (
              <div className="flex flex-col gap-0.5">
                <span className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-neutral-400">
                  Scenario · standby
                </span>
                <h2 className="font-['Space_Grotesk'] text-[15px] font-bold tracking-tight text-neutral-900">
                  GASLIT vs. a 5-day memory-poisoning attack
                </h2>
                <p className="text-[12px] leading-snug text-neutral-600">
                  Same database serves two agents in parallel — one with the GASLIT belief layer, one
                  without. Press{" "}
                  <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[11px]">
                    Start Day 1
                  </span>{" "}
                  to walk the scripted attack, or use the live test bench to trick the system yourself.
                </p>
              </div>
            )}
          </article>

          <DriftGaugeStrip
            drifts={ev.drifts}
            trustScore={trust?.score ?? null}
            highlightMemoryId="m_4419"
          />
        </section>

        {/* Live test bench — always available */}
        <ManualPrompt onSend={manualSend} busy={scribeBusy} />

        {/* The headline — side by side */}
        <DualConsole
          onHandle={onHandle}
          onBusyChange={setScribeBusy}
          spotlight={spec?.paneSpotlight ?? "none"}
        />

        {/* Live activity row: agents + transcript */}
        <section className="grid min-h-0 grid-cols-1 gap-2.5 lg:grid-cols-[1fr_460px]">
          <AgentSpotlight
            spotlight={spec?.spotlight ?? "none"}
            heartbeat={ev.agentHeartbeat}
            retrievals={ev.retrievals}
            drifts={ev.drifts}
            quarantines={ev.quarantines}
            sentinelOnline={sentinelOnline}
            scribeBusy={scribeBusy}
          />
          <EventTape events={ev.events} className="h-[150px]" />
        </section>

        {/* Forensic dossier + interactive Q&A — only meaningful after Day 4 */}
        <DossierPanel latest={latestQuarantine} />
      </main>
    </div>
  );
}

function Indicator({
  label,
  value,
  tone,
  extra,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "bad" | "neutral";
  extra?: string;
}) {
  const dot =
    tone === "ok"
      ? "bg-[var(--op-green)]"
      : tone === "warn"
        ? "bg-amber-500"
        : tone === "bad"
          ? "bg-red-500"
          : "bg-neutral-300";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      <span className="font-medium uppercase tracking-[0.12em] text-neutral-400">{label}</span>
      <span className="text-neutral-700">{value}</span>
      {extra && <span className="text-neutral-400">· {extra}</span>}
    </span>
  );
}
