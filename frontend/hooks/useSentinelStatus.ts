"use client";

import { useEffect, useState } from "react";
import { getSentinelStatus, type SentinelStatus } from "@/lib/api";

export function useSentinelStatus(intervalMs = 3000): {
  status: SentinelStatus | null;
  refresh: () => void;
} {
  const [status, setStatus] = useState<SentinelStatus | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    let timer: number | null = null;

    async function loop() {
      try {
        const r = await getSentinelStatus();
        if (alive) setStatus(r);
      } catch {
        /* keep last */
      }
      if (alive) timer = window.setTimeout(loop, intervalMs);
    }

    loop();

    return () => {
      alive = false;
      if (timer) window.clearTimeout(timer);
    };
  }, [intervalMs, tick]);

  return { status, refresh: () => setTick((t) => t + 1) };
}
