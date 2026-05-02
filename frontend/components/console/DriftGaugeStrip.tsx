"use client";

import { useMemo } from "react";
import type { DriftUpdatePayload } from "@/hooks/useGaslitEvents";
import { cn } from "@/lib/utils";

const THRESHOLD = 0.62;

/**
 * One prominent gauge for the "watched" memory (default m_4419) plus an at-a-glance
 * trust score. Replaces the multi-bar HUD strip — kept the same name so existing
 * callers don't break.
 */
export function DriftGaugeStrip({
  drifts,
  trustScore,
  highlightMemoryId = "m_4419",
  className,
}: {
  drifts: Record<string, DriftUpdatePayload>;
  trustScore: number | null;
  highlightMemoryId?: string;
  className?: string;
}) {
  const watched = drifts[highlightMemoryId];

  const fallback = useMemo(() => {
    const list = Object.values(drifts);
    list.sort((a, b) => b.drift_score - a.drift_score);
    return list[0];
  }, [drifts]);

  const target = watched ?? fallback;
  const score = target?.drift_score ?? 0;
  const pct = Math.max(0, Math.min(1, score)) * 100;
  const above = score >= THRESHOLD;
  const tone = above ? "bg-red-500" : score >= 0.4 ? "bg-amber-500" : "bg-[var(--op-green)]";
  const label = target?.memory_id ?? highlightMemoryId;

  const trust = trustScore ?? 100;
  const trustTone =
    trust < 60 ? "text-red-600" : trust < 80 ? "text-amber-600" : "text-[var(--op-green)]";

  return (
    <div
      className={cn(
        "grid grid-cols-12 items-center gap-4 rounded-2xl border border-[var(--op-border)] bg-white px-5 py-4",
        className,
      )}
    >
      <div className="col-span-9 flex flex-col gap-2">
        <div className="flex items-baseline justify-between text-[11px]">
          <div className="flex items-center gap-2 font-medium text-neutral-700">
            <span className="font-mono text-[11px] text-neutral-500">{label}</span>
            <span className="text-neutral-400">·</span>
            <span className="text-neutral-500">cohort drift</span>
            {target && (
              <>
                <span className="text-neutral-400">·</span>
                <span className="text-neutral-500">
                  {target.retrieval_count} retrievals · variance {target.cohort_variance.toFixed(2)}×
                </span>
              </>
            )}
          </div>
          <span className="font-mono text-[10px] text-neutral-400">threshold {THRESHOLD.toFixed(2)}</span>
        </div>

        <div className="relative h-2.5 overflow-hidden rounded-full bg-neutral-100">
          <div
            className={cn("h-full rounded-full transition-[width] duration-700 ease-out", tone)}
            style={{ width: `${pct}%` }}
          />
          <span
            className="pointer-events-none absolute -top-1 bottom-[-4px] w-[2px] bg-neutral-400"
            style={{ left: `${THRESHOLD * 100}%` }}
            aria-hidden
          />
        </div>

        <div className="flex items-center justify-between text-[11px] text-neutral-500">
          <span className="tabular-nums">
            <span className={cn("font-semibold", above ? "text-red-600" : "text-neutral-700")}>
              {score.toFixed(2)}
            </span>{" "}
            current drift score
          </span>
          {above && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-red-200 bg-red-50 px-2 py-[1px] text-[10px] font-semibold uppercase tracking-wider text-red-700">
              <span className="h-1.5 w-1.5 rounded-full bg-red-500 op-pulse-dot" />
              above threshold · quarantine eligible
            </span>
          )}
        </div>
      </div>

      <div className="col-span-3 flex flex-col items-end gap-0.5 border-l border-[var(--op-border)] pl-4">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-400">
          Memory trust
        </span>
        <span className={cn("font-['Space_Grotesk'] font-bold tabular-nums leading-none", trustTone)} style={{ fontSize: "1.9rem" }}>
          {trust}
        </span>
        <span className="text-[10px] text-neutral-400">/ 100 · live</span>
      </div>
    </div>
  );
}
