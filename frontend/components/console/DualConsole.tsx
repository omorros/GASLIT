"use client";

import { useEffect, useRef, useState } from "react";
import {
  postUnprotectedAgent,
  postGaslitAgent,
  type AgentResponse,
} from "@/lib/api";
import { FiredBlockedBadge, type Verdict } from "./FiredBlockedBadge";
import { MoneyLedger } from "./MoneyLedger";
import { cn } from "@/lib/utils";

const TREASURY_INITIAL = 50_000;
const TREASURY_HIT = 45_200;

export type ChatTurn = {
  id: string;
  who: "operator" | "agent";
  text: string;
  meta?: string;
  detail?: AgentResponse;
  ts: number;
};

export type DualConsoleHandle = {
  send: (
    message: string,
    opts?: { user_id?: string; thread_id?: string; turn_number?: number; tool_name?: string },
  ) => Promise<{ left?: AgentResponse; right?: AgentResponse }>;
  reset: () => void;
};

export function DualConsole({
  onHandle,
  onBusyChange,
  spotlight = "none",
}: {
  onHandle?: (h: DualConsoleHandle) => void;
  /** Fires whenever a paired dispatch starts/ends — drives "Scribe writing" indicator. */
  onBusyChange?: (busy: boolean) => void;
  /** Optional spotlight: dim the side that's NOT being focused. */
  spotlight?: "left" | "right" | "both" | "none";
}) {
  const [leftLog, setLeftLog] = useState<ChatTurn[]>([]);
  const [rightLog, setRightLog] = useState<ChatTurn[]>([]);
  const [leftVerdict, setLeftVerdict] = useState<Verdict>("idle");
  const [rightVerdict, setRightVerdict] = useState<Verdict>("idle");
  const [leftBalance, setLeftBalance] = useState(TREASURY_INITIAL);
  const [, setBusy] = useState(false);
  const busyRef = useRef(false);
  const turnCounter = useRef(1);
  const threadId = useRef(`t_console_${Math.random().toString(36).slice(2, 10)}`);

  function addLeft(t: ChatTurn) { setLeftLog((p) => [...p, t]); }
  function addRight(t: ChatTurn) { setRightLog((p) => [...p, t]); }
  function setConsoleBusy(next: boolean) {
    busyRef.current = next;
    setBusy(next);
    onBusyChange?.(next);
  }

  async function send(
    message: string,
    opts?: { user_id?: string; thread_id?: string; turn_number?: number; tool_name?: string },
  ) {
    if (!message.trim() || busyRef.current) return {};
    setConsoleBusy(true);
    setLeftVerdict("thinking");
    setRightVerdict("thinking");

    const tn = opts?.turn_number ?? turnCounter.current++;
    const user_id = opts?.user_id ?? "u_HIGH_VALUE";
    const thread_id = opts?.thread_id ?? threadId.current;
    const ts = Date.now();
    const id = `${ts}_${tn}`;

    addLeft({ id: `${id}_op`, who: "operator", text: message, ts, meta: user_id });
    addRight({ id: `${id}_op`, who: "operator", text: message, ts, meta: user_id });

    const payload = { message, user_id, thread_id, turn_number: tn, tool_name: opts?.tool_name };
    const [l, r] = await Promise.allSettled([
      postUnprotectedAgent(payload),
      postGaslitAgent(payload),
    ]);

    let leftRes: AgentResponse | undefined;
    let rightRes: AgentResponse | undefined;

    if (l.status === "fulfilled") {
      leftRes = l.value;
      const fired = (l.value.tool_calls ?? []).some((tc) => tc.tool === "refund_request");
      setLeftVerdict(fired ? "fired" : "idle");
      if (fired) setLeftBalance(TREASURY_HIT);
      addLeft({
        id: `${id}_la`,
        who: "agent",
        text: l.value.response,
        meta: fired
          ? "Tool fired · refund_request($4,800)"
          : `${l.value.retrieved_memories.length} memories surfaced`,
        detail: l.value,
        ts: Date.now(),
      });
    } else {
      setLeftVerdict("idle");
      addLeft({ id: `${id}_la`, who: "agent", text: `[error] ${l.reason}`, ts: Date.now() });
    }

    if (r.status === "fulfilled") {
      rightRes = r.value;
      const fired = (r.value.tool_calls ?? []).some((tc) => tc.tool === "refund_request");
      const blocked = !fired && /escalat/i.test(r.value.response);
      setRightVerdict(fired ? "fired" : blocked ? "blocked" : "idle");
      addRight({
        id: `${id}_ra`,
        who: "agent",
        text: r.value.response,
        meta: blocked
          ? `Belief contract · ${r.value.contract_applied ?? "active"} · filtered ${r.value.filtered_memories?.length ?? 0}`
          : fired
            ? "Tool fired · refund_request($4,800)"
            : `${r.value.retrieved_memories.length} memories surfaced`,
        detail: r.value,
        ts: Date.now(),
      });
    } else {
      setRightVerdict("idle");
      addRight({ id: `${id}_ra`, who: "agent", text: `[error] ${r.reason}`, ts: Date.now() });
    }

    setConsoleBusy(false);
    return { left: leftRes, right: rightRes };
  }

  function reset() {
    setLeftLog([]);
    setRightLog([]);
    setLeftVerdict("idle");
    setRightVerdict("idle");
    setLeftBalance(TREASURY_INITIAL);
    threadId.current = `t_console_${Math.random().toString(36).slice(2, 10)}`;
    turnCounter.current = 1;
  }

  useEffect(() => {
    onHandle?.({ send, reset });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dimLeft = spotlight === "right";
  const dimRight = spotlight === "left";

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Pane
        side="left"
        title="Without GASLIT"
        subtitle="Control arm · no belief contract"
        verdict={leftVerdict}
        log={leftLog}
        balance={leftBalance}
        ledgerLocked={false}
        dim={dimLeft}
      />
      <Pane
        side="right"
        title="With GASLIT"
        subtitle="Belief layer · high_stakes_refund_request"
        verdict={rightVerdict}
        log={rightLog}
        balance={TREASURY_INITIAL}
        ledgerLocked={true}
        dim={dimRight}
      />
    </div>
  );
}

function Pane({
  side,
  title,
  subtitle,
  verdict,
  log,
  balance,
  ledgerLocked,
  dim,
}: {
  side: "left" | "right";
  title: string;
  subtitle: string;
  verdict: Verdict;
  log: ChatTurn[];
  balance: number;
  ledgerLocked: boolean;
  dim: boolean;
}) {
  const headTone =
    side === "left"
      ? "border-red-200 bg-red-50/70 text-red-700"
      : "border-[var(--op-green)]/30 bg-[var(--op-green-bg)] text-[var(--op-green)]";

  return (
    <article
      className={cn(
        "op-dim flex flex-col rounded-2xl border bg-white shadow-[0_1px_0_0_rgba(0,0,0,0.02)]",
        side === "left" ? "border-[var(--op-border)]" : "border-[var(--op-border)]",
        dim && "is-dimmed",
        verdict === "fired" && "ring-2 ring-red-300 ring-offset-2 ring-offset-[var(--op-bg)]",
        verdict === "blocked" && "ring-2 ring-[var(--op-green)]/40 ring-offset-2 ring-offset-[var(--op-bg)]",
      )}
    >
      <header className={cn("flex items-center justify-between gap-3 rounded-t-2xl border-b px-4 py-2.5", headTone)}>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              side === "left" ? "bg-red-500" : "bg-[var(--op-green)]",
            )}
          />
          <h3 className="font-['Space_Grotesk'] text-[14px] font-bold tracking-tight">{title}</h3>
        </div>
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] opacity-80">
          {subtitle}
        </span>
      </header>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <ChatLog log={log} side={side} />

        <div className="flex items-end justify-between gap-3 border-t border-[var(--op-border)] pt-3">
          <FiredBlockedBadge verdict={verdict} />
          <MoneyLedger
            balance={balance}
            locked={ledgerLocked}
            label={side === "left" ? "Treasury" : "Treasury"}
          />
        </div>
      </div>
    </article>
  );
}

function ChatLog({ log, side }: { log: ChatTurn[]; side: "left" | "right" }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [log.length]);

  return (
    <div
      ref={ref}
      className="flex h-[156px] flex-col gap-2 overflow-y-auto pr-1 text-[12.5px]"
      style={{ scrollbarWidth: "thin" }}
    >
      {log.length === 0 && (
        <p className="text-[12px] italic text-neutral-400">awaiting customer turn…</p>
      )}
      {log.map((t) => (
        <div key={t.id} className="op-slide-up flex flex-col gap-0.5">
          <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-neutral-400">
            {t.who === "operator"
              ? `Customer · ${t.meta ?? ""}`
              : side === "left"
                ? "Agent · unprotected"
                : "Agent · GASLIT"}
          </span>
          <p
            className={cn(
              "whitespace-pre-wrap leading-relaxed",
              t.who === "operator"
                ? "text-neutral-800"
                : side === "left"
                  ? "text-red-700"
                  : "text-[var(--op-green)]",
            )}
          >
            {t.text}
          </p>
          {t.meta && t.who === "agent" && (
            <span className="text-[10.5px] text-neutral-400">{t.meta}</span>
          )}
        </div>
      ))}
    </div>
  );
}
