"use client";

import { useEffect, useMemo, useState } from "react";
import type { DaySpotlight } from "@/hooks/useScenarioPlayer";
import type { DriftUpdatePayload, RetrievalPayload, QuarantinePayload } from "@/hooks/useGaslitEvents";
import { cn } from "@/lib/utils";

type Agent = {
  id: DaySpotlight;
  name: string;
  description: string;
  model: string;
};

const AGENTS: Agent[] = [
  { id: "scribe", name: "Scribe", description: "Distill turns → HMAC memory", model: "Claude Sonnet 4.6" },
  { id: "librarian", name: "Librarian", description: "Hybrid retrieval + contracts", model: "Claude Sonnet 4.6" },
  { id: "sentinel", name: "Sentinel", description: "Drift detection · quarantine", model: "Nemotron 3 Super 120B" },
  { id: "forensic", name: "Forensic Auditor", description: "Provenance walk · SOC2 dossier", model: "Claude Sonnet 4.6" },
];

const FRESH_MS = 4000;

export function AgentSpotlight({
  spotlight,
  heartbeat,
  retrievals,
  drifts,
  quarantines,
  sentinelOnline,
  scribeBusy,
  className,
}: {
  spotlight: DaySpotlight;
  heartbeat: Record<string, number>;
  retrievals: RetrievalPayload[];
  drifts: Record<string, DriftUpdatePayload>;
  quarantines: QuarantinePayload[];
  sentinelOnline: boolean;
  /** True while a paired POST is in flight — Scribe is actively distilling. */
  scribeBusy: boolean;
  className?: string;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 600);
    return () => window.clearInterval(t);
  }, []);

  const lastRetrieval = retrievals[0];
  const topDrift = useMemo(() => {
    const list = Object.values(drifts);
    list.sort((a, b) => b.drift_score - a.drift_score);
    return list[0];
  }, [drifts]);
  const lastQuarantine = quarantines[0];

  const recent = (id: string) => now - (heartbeat[id] ?? 0) < FRESH_MS;

  // Per-agent live action label
  const labels: Record<DaySpotlight, string> = {
    scribe: scribeBusy
      ? "writing memory…"
      : recent("scribe")
        ? "memory persisted"
        : "idle",
    librarian: lastRetrieval
      ? `${lastRetrieval.filtered ? "filtered" : "passed"} ${lastRetrieval.memory_id} · ${lastRetrieval.contract_id}`
      : "idle",
    sentinel: !sentinelOnline
      ? "offline"
      : topDrift
        ? `drift ${topDrift.drift_score.toFixed(2)} · variance ${topDrift.cohort_variance.toFixed(1)}×`
        : "watching",
    forensic: lastQuarantine
      ? `dossier · ${lastQuarantine.memory_id}`
      : "standby",
    none: "",
  };

  return (
    <section className={cn("grid grid-cols-4 gap-2.5", className)}>
      {AGENTS.map((a) => {
        const isSpotlighted = spotlight === a.id;
        const isActive =
          isSpotlighted ||
          (a.id === "scribe" && scribeBusy) ||
          (a.id === "librarian" && recent("librarian")) ||
          (a.id === "sentinel" && (recent("sentinel") || sentinelOnline)) ||
          (a.id === "forensic" && (recent("forensic") || !!lastQuarantine));
        const label = labels[a.id];
        return (
          <article
            key={a.id}
            className={cn(
              "op-dim relative flex flex-col gap-0.5 rounded-xl border bg-white px-3 py-2.5 transition-all",
              isSpotlighted
                ? "border-[var(--op-green)]/60 bg-[var(--op-green-bg)] op-focus-pulse"
                : isActive
                  ? "border-[var(--op-green)]/30 bg-white"
                  : "border-[var(--op-border)] is-dimmed",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="font-['Space_Grotesk'] text-[12px] font-bold tracking-tight text-neutral-900">
                {a.name}
              </span>
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  isActive
                    ? isSpotlighted
                      ? "bg-[var(--op-green)] op-pulse-dot"
                      : "bg-[var(--op-green)]"
                    : "bg-neutral-300",
                )}
              />
            </div>
            <p className="text-[10.5px] leading-snug text-neutral-500">{a.description}</p>
            <p
              className={cn(
                "mt-0.5 truncate font-mono text-[10px]",
                isActive ? "text-[var(--op-green)]" : "text-neutral-400",
              )}
              title={label}
            >
              › {label || "—"}
            </p>
          </article>
        );
      })}
    </section>
  );
}
