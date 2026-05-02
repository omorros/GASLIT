"use client";

import type { DaySpec } from "@/hooks/useScenarioPlayer";
import { cn } from "@/lib/utils";

export function ScenarioHeader({
  days,
  currentDay,
  spec,
  busy,
  isDone,
  onAdvance,
  onReset,
  className,
}: {
  days: DaySpec[];
  currentDay: number;
  spec: DaySpec | null;
  busy: boolean;
  isDone: boolean;
  onAdvance: () => void;
  onReset: () => void;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex items-center justify-between gap-4 rounded-2xl border border-[var(--op-border)] bg-white px-5 py-3.5",
        className,
      )}
    >
      {/* Day pills */}
      <div className="flex items-center gap-2">
        {days.map((d) => {
          const isActive = d.day === currentDay;
          const isDoneStep = d.day < currentDay;
          return (
            <div
              key={d.day}
              className={cn(
                "flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11.5px] font-medium transition-colors",
                isActive
                  ? "border-[var(--op-green)] bg-[var(--op-green-bg)] text-[var(--op-green)]"
                  : isDoneStep
                    ? "border-neutral-200 bg-neutral-50 text-neutral-500"
                    : "border-neutral-200 bg-white text-neutral-400",
              )}
            >
              <span
                className={cn(
                  "flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold",
                  isActive
                    ? "bg-[var(--op-green)] text-white"
                    : isDoneStep
                      ? "bg-neutral-300 text-white"
                      : "bg-neutral-100 text-neutral-500",
                )}
              >
                {isDoneStep ? "✓" : d.day}
              </span>
              <span className="font-mono text-[10px] text-neutral-400">{d.date}</span>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        {currentDay === 0 && (
          <p className="hidden text-[12px] text-neutral-500 lg:block">
            5-day attack simulation · single click each day
          </p>
        )}
        {!isDone && (
          <button
            onClick={onAdvance}
            disabled={busy}
            className={cn(
              "inline-flex items-center gap-2 rounded-full bg-neutral-900 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {busy ? (
              <>
                <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                Running…
              </>
            ) : currentDay === 0 ? (
              <>
                Start Day 1
                <Arrow />
              </>
            ) : currentDay >= days.length ? (
              <>Finish</>
            ) : (
              <>
                {spec ? `Advance to Day ${currentDay + 1}` : `Run Day ${currentDay + 1}`}
                <Arrow />
              </>
            )}
          </button>
        )}
        {isDone && (
          <button
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-full border border-neutral-200 bg-white px-4 py-2 text-[13px] font-medium text-neutral-700 transition-colors hover:bg-neutral-50"
          >
            ↺ Restart simulation
          </button>
        )}
      </div>
    </section>
  );
}

function Arrow() {
  return (
    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
    </svg>
  );
}
