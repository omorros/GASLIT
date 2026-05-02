"use client";

import { useState } from "react";
import { complianceExportUrl } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ComplianceExportButton({
  quarantineId,
  className,
}: {
  quarantineId: string | null;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);

  async function onClick() {
    if (!quarantineId || busy) return;
    setBusy(true);
    try {
      const r = await fetch(complianceExportUrl(quarantineId));
      if (!r.ok) throw new Error(await r.text());
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `gaslit-soc2-${quarantineId}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("[compliance-export]", e);
    } finally {
      setBusy(false);
    }
  }

  const enabled = !!quarantineId && !busy;

  return (
    <button
      onClick={onClick}
      disabled={!enabled}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-full bg-neutral-900 px-3.5 py-2 text-[12px] font-semibold text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
    >
      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
      </svg>
      {busy ? "Exporting…" : "Export SOC2 evidence"}
    </button>
  );
}
