"use client";

import { useEffect, useState } from "react";
import { getTrustScore, type TrustScore } from "@/lib/api";

export function useTrustScore(intervalMs = 4000): TrustScore | null {
  const [score, setScore] = useState<TrustScore | null>(null);

  useEffect(() => {
    let alive = true;
    let timer: number | null = null;

    async function tick() {
      try {
        const r = await getTrustScore();
        if (alive) setScore(r);
      } catch {
        /* keep last */
      }
      if (alive) timer = window.setTimeout(tick, intervalMs);
    }

    tick();

    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [intervalMs]);

  return score;
}
