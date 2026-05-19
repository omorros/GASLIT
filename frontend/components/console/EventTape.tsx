"use client";

import { useEffect, useRef } from "react";
import type { GaslitEvent } from "@/hooks/useGaslitEvents";
import { cn } from "@/lib/utils";

export function EventTape({
  events,
  className,
}: {
  events: GaslitEvent[];
  className?: string;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (wrap.current) wrap.current.scrollTop = 0;
  }, [events.length]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-2xl border border-[var(--op-border)] bg-white",
        className,
      )}
    >
      <header className="flex shrink-0 items-center justify-between border-b border-[var(--op-border)] px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--op-green)] op-pulse-dot" />
          <span className="text-[11.5px] font-semibold text-neutral-700">Live transcript</span>
          <span className="text-[10.5px] text-neutral-400">· every retrieval, drift, quarantine</span>
        </div>
        <span className="font-mono text-[10px] text-neutral-400">{events.length} events</span>
      </header>

      <div
        ref={wrap}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-2 font-mono text-[11.5px] leading-[1.55]"
        style={{ scrollbarWidth: "thin" }}
      >
        {events.length === 0 ? (
          <p className="italic text-neutral-400">awaiting WebSocket events from ws://:8003 …</p>
        ) : (
          events.slice(0, 80).map((e, i) => <Line key={`${e.ts}-${i}`} e={e} fresh={i < 2} />)
        )}
      </div>
    </section>
  );
}

function Line({ e, fresh }: { e: GaslitEvent; fresh: boolean }) {
  const ts = (e.ts || "").slice(11, 19);

  const formatNumber = (value: number | null | undefined, digits = 2) =>
    typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "n/a";

  let body: string;
  let tag: string;
  let tagColor: string;
  let textColor: string;

  if (e.type === "retrieval") {
    const p = e.payload;
    tag = "retrieval";
    tagColor = p.filtered ? "bg-red-50 text-red-700" : "bg-blue-50 text-blue-700";
    textColor = p.filtered ? "text-red-700" : "text-neutral-700";
    body = `${p.memory_id ?? "unknown"}  ·  ${p.agent_id ?? "unknown"}  ·  ${
      p.contract_id ?? "no-contract"
    }  ·  score=${formatNumber(p.score)}  ·  rank=${p.retrieved_rank ?? "n/a"}  ·  ${
      p.filtered ? "filtered" : "passed"
    }`;
  } else if (e.type === "drift_update") {
    const p = e.payload;
    tag = "drift";
    tagColor = p.above_threshold
      ? "bg-red-50 text-red-700"
      : p.drift_score >= 0.4
        ? "bg-amber-50 text-amber-700"
        : "bg-neutral-100 text-neutral-600";
    textColor = p.above_threshold ? "text-red-700" : "text-neutral-700";
    body = `${p.memory_id}  ·  score=${formatNumber(p.drift_score)}  ·  variance=${formatNumber(
      p.cohort_variance,
    )}×  ·  retrievals=${p.retrieval_count}${p.above_threshold ? "  ·  ABOVE THRESHOLD" : ""}`;
  } else if (e.type === "quarantine") {
    tag = "quarantine";
    tagColor = "bg-purple-50 text-purple-700";
    textColor = "text-purple-700 font-semibold";
    body = `${e.payload.quarantine_id}  ·  ${e.payload.memory_id}${
      e.payload.responsible_user ? `  ·  by ${e.payload.responsible_user}` : ""
    }`;
  } else {
    tag = "agent";
    tagColor = "bg-[var(--op-green-bg)] text-[var(--op-green)]";
    textColor = "text-neutral-600";
    body = `${e.payload.agent_id}  ·  ${e.payload.status}`;
  }

  return (
    <div className={cn("flex items-baseline gap-2 py-[1px]", fresh && "op-slide-up")}>
      <span className="shrink-0 tabular-nums text-neutral-400">{ts}</span>
      <span
        className={cn(
          "shrink-0 rounded px-1.5 py-[1px] text-[9.5px] font-semibold uppercase tracking-[0.06em]",
          tagColor,
        )}
      >
        {tag}
      </span>
      <span className={cn("min-w-0 truncate", textColor)}>{body}</span>
    </div>
  );
}
