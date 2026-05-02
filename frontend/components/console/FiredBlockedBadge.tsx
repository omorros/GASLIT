"use client";

import { cn } from "@/lib/utils";

export type Verdict = "idle" | "fired" | "blocked" | "thinking";

export function FiredBlockedBadge({ verdict, className }: { verdict: Verdict; className?: string }) {
  const config: Record<Verdict, { label: string; classes: string; icon: React.ReactNode }> = {
    idle: {
      label: "Standby",
      classes: "bg-neutral-100 text-neutral-500 border-neutral-200",
      icon: <span className="h-2 w-2 rounded-full bg-neutral-400" />,
    },
    thinking: {
      label: "Processing",
      classes: "bg-amber-50 text-amber-700 border-amber-200",
      icon: <span className="h-2 w-2 rounded-full bg-amber-500 op-pulse-dot" />,
    },
    fired: {
      label: "Tool fired",
      classes: "bg-red-50 text-red-700 border-red-300",
      icon: (
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
        </svg>
      ),
    },
    blocked: {
      label: "Blocked",
      classes: "bg-[var(--op-green-bg)] text-[var(--op-green)] border-[var(--op-green)]/40",
      icon: (
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
        </svg>
      ),
    },
  };

  const c = config[verdict];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-semibold",
        c.classes,
        className,
      )}
    >
      {c.icon}
      <span>{c.label}</span>
    </span>
  );
}
