"use client";

import { useEffect, useRef, useState } from "react";
import type { QuarantinePayload } from "@/hooks/useGaslitEvents";
import { ComplianceExportButton } from "./ComplianceExportButton";
import { postForensicQA, postTTS } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * Live Forensic Auditor surface — the only voice in the system.
 *
 * Behaviour:
 * - Auto-plays the dossier readout when a fresh quarantine arrives.
 * - Lets the operator type follow-up questions; the answer text streams in,
 *   then is spoken back via the SAME voice. Lines are queued so they never
 *   overlap.
 */

type SpokenLine = { id: number; text: string };

const SUGGESTIONS = [
  "Who else did this user attack?",
  "What evidence ties u_2188 to m_4419?",
  "Which sibling memories should we revoke?",
];

export function DossierPanel({
  latest,
  className,
}: {
  latest: QuarantinePayload | undefined;
  className?: string;
}) {
  // ── Voice queue (single voice, never overlapping) ─────────────────
  const [queue, setQueue] = useState<SpokenLine[]>([]);
  const [now, setNow] = useState<SpokenLine | null>(null);
  const [audio, setAudio] = useState<"idle" | "loading" | "playing" | "muted" | "error">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const playingRef = useRef(false);
  const playbackRunRef = useRef(0);
  const idRef = useRef(0);

  function enqueue(text: string) {
    if (!text.trim()) return;
    setQueue((q) => [...q, { id: ++idRef.current, text }]);
  }

  const queueHead = queue[0];

  // Drain queue serially
  useEffect(() => {
    if (playingRef.current) return;
    if (!queueHead) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    let currentAudio: HTMLAudioElement | null = null;
    const runId = ++playbackRunRef.current;
    const isCurrentRun = () => playbackRunRef.current === runId;

    const releaseObjectUrl = () => {
      if (!objectUrl) return;
      URL.revokeObjectURL(objectUrl);
      objectUrl = null;
    };

    (async () => {
      playingRef.current = true;
      setNow(queueHead);
      setAudio("loading");
      try {
        const buf = await postTTS(queueHead.text, "forensic");
        if (cancelled) {
          if (isCurrentRun()) playingRef.current = false;
          return;
        }
        const blob = new Blob([buf], { type: "audio/mpeg" });
        objectUrl = URL.createObjectURL(blob);
        const a = new Audio(objectUrl);
        currentAudio = a;
        audioRef.current = a;
        a.onended = () => {
          releaseObjectUrl();
          if (!isCurrentRun()) return;
          playingRef.current = false;
          setAudio("idle");
          setNow(null);
          setQueue((q) => q.slice(1));
        };
        a.onerror = () => {
          releaseObjectUrl();
          if (!isCurrentRun()) return;
          playingRef.current = false;
          setAudio("error");
          setNow(null);
          setQueue((q) => q.slice(1));
        };
        await a.play();
        if (!cancelled && isCurrentRun()) setAudio("playing");
      } catch {
        if (cancelled || !isCurrentRun()) return;
        playingRef.current = false;
        setAudio("error");
        setNow(null);
        setQueue((q) => q.slice(1));
      }
    })();
    return () => {
      cancelled = true;
      currentAudio?.pause();
      releaseObjectUrl();
      if (isCurrentRun()) playingRef.current = false;
    };
  }, [queueHead]);

  // Auto-readout when a new quarantine arrives
  const lastQid = useRef<string | null>(null);
  useEffect(() => {
    if (!latest?.quarantine_id || !latest.dossier_text?.trim()) return;
    if (latest.quarantine_id === lastQid.current) return;
    lastQid.current = latest.quarantine_id;
    enqueue(latest.dossier_text);
  }, [latest]);

  function toggleMute() {
    if (!audioRef.current) return;
    if (audio === "playing") {
      audioRef.current.pause();
      setAudio("muted");
    } else if (audio === "muted") {
      void audioRef.current.play();
      setAudio("playing");
    }
  }

  // ── Q&A ───────────────────────────────────────────────────────────
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [askBusy, setAskBusy] = useState(false);

  async function ask(q: string) {
    if (!q.trim() || askBusy) return;
    setAskBusy(true);
    setAnswer(null);
    try {
      const res = await postForensicQA(q.trim(), latest?.quarantine_id);
      setAnswer(res.answer);
      enqueue(res.answer);
    } catch (e) {
      setAnswer(`(Auditor offline — ${(e as Error).message})`);
    } finally {
      setAskBusy(false);
      setQuestion("");
    }
  }

  if (!latest) {
    return (
      <section
        className={cn(
          "flex items-center justify-between rounded-2xl border border-dashed border-neutral-200 bg-neutral-50/60 px-5 py-3",
          className,
        )}
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-neutral-100">
            <svg className="h-4 w-4 text-neutral-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-9 5.25h.008v.008H12v-.008Z" />
            </svg>
          </div>
          <div>
            <p className="text-[13px] font-medium text-neutral-700">Forensic Auditor — voice agent</p>
            <p className="text-[11.5px] text-neutral-500">
              Will compile a SOC2 dossier and read it aloud the moment a quarantine fires.
            </p>
          </div>
        </div>
        <span className="rounded-full border border-neutral-200 bg-white px-2 py-1 text-[10px] font-medium uppercase tracking-[0.14em] text-neutral-400">
          standby
        </span>
      </section>
    );
  }

  const dossier = latest.dossier_text || "(dossier compiling…)";
  const queueLen = queue.length;

  return (
    <section
      className={cn(
        "op-slide-up grid grid-cols-1 gap-4 rounded-2xl border border-[var(--op-green)]/30 bg-[var(--op-green-bg)] px-5 py-3 lg:grid-cols-[1fr_300px]",
        className,
      )}
    >
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-2.5 py-1 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-[var(--op-green)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--op-green)] op-pulse-dot" />
            Forensic Auditor
          </span>
          <span className="text-[11px] text-neutral-600">
            {latest.memory_id} · drift {latest.drift_score?.toFixed(2) ?? "—"} · variance{" "}
            {latest.cohort_variance?.toFixed(2) ?? "—"}×
            {latest.responsible_user ? ` · ${latest.responsible_user}` : ""}
          </span>
          <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-neutral-500">
            <VoiceIcon status={audio} />
            <span>
              {audio === "playing"
                ? "speaking"
                : audio === "loading"
                  ? "rendering…"
                  : audio === "muted"
                    ? "muted"
                    : audio === "error"
                      ? "audio off"
                      : "idle"}
              {queueLen > 1 && ` · queue ${queueLen - 1}`}
            </span>
            {(audio === "playing" || audio === "muted") && (
              <button onClick={toggleMute} className="ml-1 underline-offset-2 hover:underline">
                {audio === "muted" ? "play" : "pause"}
              </button>
            )}
          </span>
        </div>

        <p className="max-h-[68px] overflow-y-auto whitespace-pre-wrap text-[12.5px] leading-relaxed text-neutral-800">
          {now?.text && now.text !== dossier ? `▸ ${now.text}` : dossier}
        </p>

        {/* Q&A row */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void ask(question);
          }}
          className="flex items-center gap-1.5"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={askBusy}
            placeholder="Ask the auditor — e.g. ‘Who else did u_2188 attack?’"
            className="flex-1 rounded-full border border-white bg-white/80 px-3 py-1.5 text-[12px] text-neutral-800 outline-none focus:border-[var(--op-green)] focus:ring-2 focus:ring-[var(--op-green)]/20 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={askBusy || !question.trim()}
            className="inline-flex items-center gap-1 rounded-full bg-neutral-900 px-3 py-1.5 text-[11.5px] font-semibold text-white transition-colors hover:bg-neutral-700 disabled:opacity-40"
          >
            {askBusy ? "Thinking…" : "Ask"}
          </button>
        </form>
        <div className="flex flex-wrap items-center gap-1">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => void ask(s)}
              disabled={askBusy}
              className="rounded-full border border-white bg-white/60 px-2 py-0.5 text-[10.5px] text-neutral-600 transition-colors hover:bg-white hover:text-[var(--op-green)] disabled:opacity-40"
            >
              {s}
            </button>
          ))}
        </div>
        {answer && (
          <p className="op-slide-up rounded-lg bg-white/80 px-3 py-1.5 text-[12px] leading-relaxed text-neutral-700">
            <span className="font-semibold text-[var(--op-green)]">Auditor:</span> {answer}
          </p>
        )}
      </div>

      <aside className="flex flex-col items-stretch gap-1.5 border-l border-[var(--op-green)]/20 pl-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-500">
            Quarantine ID
          </p>
          <p className="font-mono text-[11px] text-neutral-700">{latest.quarantine_id}</p>
        </div>
        {latest.siblings_found && latest.siblings_found.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-neutral-500">
              Siblings · {latest.siblings_found.length}
            </p>
            <p className="font-mono text-[11px] text-neutral-700">
              {latest.siblings_found.slice(0, 3).join(", ")}
            </p>
          </div>
        )}
        <ComplianceExportButton quarantineId={latest.quarantine_id} className="mt-auto" />
      </aside>
    </section>
  );
}

function VoiceIcon({ status }: { status: "idle" | "loading" | "playing" | "muted" | "error" }) {
  const color =
    status === "playing"
      ? "text-[var(--op-green)]"
      : status === "loading"
        ? "text-amber-500"
        : status === "error"
          ? "text-red-500"
          : "text-neutral-400";
  return (
    <svg className={cn("h-3 w-3", color)} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.114 5.636a9 9 0 0 1 0 12.728M16.463 8.288a5.25 5.25 0 0 1 0 7.424M6.75 8.25l4.72-4.72a.75.75 0 0 1 1.28.53v15.88a.75.75 0 0 1-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.009 9.009 0 0 1 2.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75Z" />
    </svg>
  );
}
