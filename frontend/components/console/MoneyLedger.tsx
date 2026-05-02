"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export function MoneyLedger({
  balance,
  locked = false,
  label = "Treasury",
  className,
}: {
  balance: number;
  locked?: boolean;
  label?: string;
  className?: string;
}) {
  const [displayed, setDisplayed] = useState(balance);
  const [drop, setDrop] = useState(false);
  const prevRef = useRef(balance);

  useEffect(() => {
    if (balance < prevRef.current) {
      setDrop(true);
      const start = prevRef.current;
      const target = balance;
      const dur = 700;
      const t0 = performance.now();
      let raf = 0;
      const step = (now: number) => {
        const k = Math.min(1, (now - t0) / dur);
        const v = Math.round(start + (target - start) * (1 - Math.pow(1 - k, 3)));
        setDisplayed(v);
        if (k < 1) raf = requestAnimationFrame(step);
        else window.setTimeout(() => setDrop(false), 320);
      };
      raf = requestAnimationFrame(step);
      return () => cancelAnimationFrame(raf);
    }
    setDisplayed(balance);
    prevRef.current = balance;
    return undefined;
  }, [balance]);

  useEffect(() => {
    prevRef.current = balance;
  }, [balance]);

  const tone = drop ? "text-red-600" : locked ? "text-neutral-900" : "text-neutral-900";

  return (
    <div className={cn("flex flex-col gap-0.5", className)}>
      <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-400">
        {label}
      </span>
      <span
        className={cn(
          "font-['Space_Grotesk'] font-bold tabular-nums tracking-tight",
          drop && "op-num-drop",
          tone,
        )}
        style={{ fontSize: "1.6rem", lineHeight: "1.05" }}
      >
        ${displayed.toLocaleString("en-US")}
      </span>
      {locked && (
        <span className="inline-flex w-fit items-center gap-1 text-[10px] font-medium text-[var(--op-green)]">
          <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75M6.75 21.75h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
          </svg>
          Treasury locked by belief contract
        </span>
      )}
    </div>
  );
}
