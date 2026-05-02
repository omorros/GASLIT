"use client";

import Link from "next/link";
import {
  Skull,
  PenLine,
  Search,
  ScanEye,
  Scale,
  ArrowRight,
  Play,
  ChevronRight,
} from "lucide-react";
import NavBar from "@/components/NavBar";
import { DotPattern } from "@/components/ui/dot-pattern";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { BorderBeam } from "@/components/ui/border-beam";
import { Marquee } from "@/components/ui/marquee";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

/* ─── Agent definitions (per PRD §6) ───────────────────── */
type Agent = {
  key: string;
  name: string;
  model: string;
  role: string;
  Icon: React.ComponentType<{ className?: string }>;
  tone: "adversary" | "neutral" | "sentinel" | "forensic";
};

const AGENTS: Agent[] = [
  { key: "adversary", name: "Adversary",      model: "Fireworks · Llama 3.3", role: "ATTACK",   Icon: Skull,   tone: "adversary" },
  { key: "scribe",    name: "Scribe",         model: "Claude Sonnet 4.6",     role: "WRITE",    Icon: PenLine, tone: "neutral" },
  { key: "librarian", name: "Librarian",      model: "Claude Sonnet 4.6",     role: "RETRIEVE", Icon: Search,  tone: "neutral" },
  { key: "sentinel",  name: "Sentinel",       model: "Nemotron 120B",         role: "DETECT",   Icon: ScanEye, tone: "sentinel" },
  { key: "forensic",  name: "Forensic",       model: "Claude Sonnet 4.6",     role: "EXPLAIN",  Icon: Scale,   tone: "forensic" },
];

/* ─── Agent chip in the ribbon ─────────────────────────── */
const AgentChip = ({ agent, index }: { agent: Agent; index: number }) => {
  const isAdversary = agent.tone === "adversary";
  const isSentinel = agent.tone === "sentinel";
  const isForensic = agent.tone === "forensic";

  const cardBorder = isSentinel
    ? "border-[#aae030]"
    : isAdversary
    ? "border-red-200"
    : isForensic
    ? "border-amber-200"
    : "border-neutral-200";

  const cardBg = isSentinel
    ? "bg-[#f0fad8]"
    : isAdversary
    ? "bg-red-50/30"
    : isForensic
    ? "bg-amber-50/30"
    : "bg-white";

  const iconWrap = isAdversary
    ? "bg-red-50 text-red-500 border-red-100"
    : isSentinel
    ? "bg-[#76b900] text-white border-[#76b900]"
    : isForensic
    ? "bg-amber-50 text-amber-600 border-amber-100"
    : "bg-neutral-50 text-neutral-700 border-neutral-200";

  const accent = isAdversary
    ? "text-red-500"
    : isSentinel
    ? "text-[#5e9100]"
    : isForensic
    ? "text-amber-600"
    : "text-neutral-400";

  return (
    <div
      className="tv-flag-in group relative flex w-[150px] xl:w-[170px] shrink-0 flex-col"
      style={{ "--tv-delay": `${0.5 + index * 0.1}s` } as React.CSSProperties}
    >
      <div
        className={`relative flex h-full flex-col gap-2.5 rounded-2xl border ${cardBorder} ${cardBg} p-3.5 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_14px_30px_-14px_rgba(0,0,0,0.2)]`}
      >
        {isSentinel && (
          <BorderBeam size={120} duration={6} colorFrom="#76b900" colorTo="#aae030" borderWidth={1.4} />
        )}

        {/* Top row: number + role */}
        <div className="flex items-center justify-between">
          <span className={`text-[8.5px] font-mono font-bold uppercase tracking-[0.18em] ${accent}`}>
            {String(index + 1).padStart(2, "0")} · {agent.role}
          </span>
          <span className="relative flex h-1.5 w-1.5">
            <span
              className={`tv-pulse-dot absolute inline-flex h-full w-full rounded-full opacity-75 ${
                isAdversary ? "bg-red-400" : isSentinel ? "bg-[#8fd400]" : isForensic ? "bg-amber-400" : "bg-neutral-300"
              }`}
            />
            <span
              className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
                isAdversary ? "bg-red-500" : isSentinel ? "bg-[#76b900]" : isForensic ? "bg-amber-500" : "bg-neutral-400"
              }`}
            />
          </span>
        </div>

        {/* Icon */}
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl border ${iconWrap}`}>
          <agent.Icon className="h-5 w-5" />
        </div>

        {/* Name + model */}
        <div className="flex flex-col gap-0.5">
          <h3 className="font-['Space_Grotesk'] text-[15px] font-bold leading-tight text-neutral-900">
            {agent.name}
          </h3>
          <p className="text-[9px] font-mono uppercase tracking-wider text-neutral-400 truncate">
            {agent.model}
          </p>
        </div>

        {/* Sentinel marker */}
        {isSentinel && (
          <span className="absolute -top-2 right-3 rounded-full bg-[#76b900] px-2 py-0.5 text-[7.5px] font-mono font-bold uppercase tracking-[0.2em] text-white">
            gaslit
          </span>
        )}
      </div>
    </div>
  );
};

/* ─── Connector between agents (line + chevron + traveling pulse) ─ */
const Connector = ({ delay = 0, danger = false }: { delay?: number; danger?: boolean }) => (
  <div
    className="tv-flag-in relative mt-[58px] flex h-px w-8 xl:w-12 shrink-0 items-center justify-center"
    style={{ "--tv-delay": `${0.6 + delay * 0.1}s` } as React.CSSProperties}
    aria-hidden="true"
  >
    {/* base line */}
    <div className="absolute inset-0 bg-neutral-200" />
    {/* traveling pulse */}
    <div
      className="absolute -top-px h-[3px] w-6 rounded-full opacity-90"
      style={{
        background: danger
          ? "linear-gradient(90deg, transparent, #ef4444, transparent)"
          : "linear-gradient(90deg, transparent, #76b900, transparent)",
        animation: `tv-scan 2.6s cubic-bezier(0.45,0,0.55,1) ${0.4 + delay * 0.25}s infinite`,
      }}
    />
    {/* chevron */}
    <ChevronRight
      className={`relative h-3.5 w-3.5 ${danger ? "text-red-300" : "text-neutral-300"}`}
    />
  </div>
);

/* ─── Partner badge for marquee ────────────────────────── */
const PartnerBadge = ({ name }: { name: string }) => (
  <div className="flex items-center gap-2 rounded-md border border-neutral-200 bg-white px-3 py-1 hover:border-[#aae030] transition-colors">
    <span className="h-1 w-1 rounded-full bg-[#76b900]" />
    <span className="text-[10px] font-mono font-semibold uppercase tracking-wider text-neutral-600">
      {name}
    </span>
  </div>
);

const PARTNERS = [
  "MongoDB Atlas",
  "NVIDIA Nemotron",
  "Anthropic Claude",
  "ElevenLabs",
  "LiveKit",
  "Voyage AI",
  "Fireworks AI",
  "AWS ECS Fargate · eu-west-2",
  "LangGraph",
  "NeMo Guardrails",
  "NemoClaw",
];

/* ─── Main page ────────────────────────────────────────── */
export default function Home() {
  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      <NavBar />

      <main className="relative flex flex-1 flex-col overflow-hidden">
        {/* Atmosphere */}
        <DotPattern
          className="text-[#c5e87a]/35 [mask-image:radial-gradient(ellipse_75%_60%_at_50%_42%,black,transparent)]"
          width={22}
          height={22}
          cr={1.1}
        />
        {/* Soft radial glow centered behind wordmark */}
        <div
          className="glow-pulse pointer-events-none absolute left-1/2 top-[35%] -translate-x-1/2 -translate-y-1/2 h-[480px] w-[680px] rounded-full"
          style={{ background: "radial-gradient(circle, rgba(118,185,0,0.13) 0%, transparent 65%)" }}
          aria-hidden="true"
        />

        {/* Center-stage hero — vertically centered, full width */}
        <div className="relative z-10 flex flex-1 flex-col items-center justify-center gap-7 px-6 py-6">
          {/* Kicker */}
          <Badge
            variant="green"
            className="tv-flag-in px-3.5 py-1 text-[10px]"
            style={{ "--tv-delay": "0.05s" } as React.CSSProperties}
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="tv-pulse-dot absolute inline-flex h-full w-full rounded-full bg-[#8fd400] opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#76b900]" />
            </span>
            belief-layer defence · OWASP ASI06 · london 02 may
          </Badge>

          {/* Wordmark */}
          <div className="relative">
            <h1
              className="font-['Space_Grotesk'] font-black leading-[0.85] tracking-tighter text-center"
              style={{ fontSize: "clamp(4rem, 13vw, 11rem)" }}
              aria-label="GASLIT"
            >
              {"GASLIT".split("").map((letter, i) => (
                <span
                  key={i}
                  className={`tv-flag-in inline-block ${i < 3 ? "text-neutral-900" : "text-[#76b900]"}`}
                  style={{ "--tv-delay": `${0.1 + i * 0.06}s` } as React.CSSProperties}
                >
                  {letter}
                </span>
              ))}
            </h1>
            {/* Scanline sweep across wordmark on load */}
            <div className="pointer-events-none absolute inset-0 overflow-hidden">
              <div
                className="absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/30 to-transparent"
                style={{ animation: "tv-scan 1.4s cubic-bezier(0.4,0,0.6,1) 0.6s 1 forwards", transform: "translateX(-100%)" }}
              />
            </div>
          </div>

          {/* Tagline */}
          <div className="flex flex-col items-center gap-2 text-center max-w-2xl">
            <p
              className="tv-flag-in font-['Space_Grotesk'] text-xl md:text-2xl font-semibold leading-snug text-neutral-800"
              style={{ "--tv-delay": "0.55s" } as React.CSSProperties}
            >
              Police what they&apos;re allowed to{" "}
              <em className="not-italic text-[#76b900]">believe</em>.
            </p>
            <p
              className="tv-flag-in text-[13px] leading-relaxed text-neutral-500 max-w-lg"
              style={{ "--tv-delay": "0.62s" } as React.CSSProperties}
            >
              Memory poisoning has a{" "}
              <span className="font-semibold text-neutral-700">&gt;95% attack success rate</span> on
              unprotected agents. GASLIT stops it at the retrieval layer between MongoDB and the LLM.
            </p>
          </div>

          {/* CTAs */}
          <div
            className="tv-flag-in flex flex-col sm:flex-row items-center gap-4"
            style={{ "--tv-delay": "0.7s" } as React.CSSProperties}
          >
            <Link href="/console?attack=minja">
              <ShimmerButton
                background="linear-gradient(135deg, #4d7a00, #76b900)"
                shimmerColor="#c5e87a"
                className="gap-2 text-sm font-semibold px-7 py-3 shadow-[0_10px_30px_-10px_rgba(118,185,0,0.7)] hover:-translate-y-0.5 transition-transform"
              >
                <Play className="h-3.5 w-3.5 fill-current" /> Run MINJA Attack
              </ShimmerButton>
            </Link>
            <Link
              href="/about"
              className="group inline-flex items-center gap-1.5 text-sm font-semibold text-neutral-600 hover:text-[#76b900] transition-colors"
            >
              Read the threat model
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>

          {/* Agent ribbon */}
          <div className="mt-2 flex w-full max-w-5xl flex-col items-center gap-3">
            <div className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-[0.22em] text-neutral-400">
              <span className="h-px w-6 bg-neutral-200" />
              <span>defence pipeline · 5 agents · mongodb-coordinated</span>
              <span className="h-px w-6 bg-neutral-200" />
            </div>
            <div className="flex items-stretch justify-center">
              {AGENTS.map((agent, i) => (
                <div key={agent.key} className="flex items-stretch">
                  <AgentChip agent={agent} index={i} />
                  {i < AGENTS.length - 1 && (
                    <Connector delay={i} danger={i === 0} />
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom rail · stats + partner marquee */}
        <footer className="relative z-10 shrink-0 border-t border-neutral-100 bg-white">
          <div className="flex items-center gap-4 px-6 py-2">
            {/* Live stats — PRD-cited facts only */}
            <div className="hidden md:flex shrink-0 items-center gap-3 text-[10px] font-mono uppercase tracking-widest">
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="tv-pulse-dot absolute inline-flex h-full w-full rounded-full bg-[#8fd400] opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#76b900]" />
                </span>
                <span className="text-neutral-500">pipeline live</span>
              </div>
              <Separator orientation="vertical" className="h-3" />
              <div>
                <span className="font-bold text-neutral-900">&lt;200</span>
                <span className="ml-0.5 text-neutral-400">ms p99</span>
              </div>
              <Separator orientation="vertical" className="h-3" />
              <div>
                <span className="font-bold text-[#76b900]">0.62</span>
                <span className="ml-0.5 text-neutral-400">drift</span>
              </div>
              <Separator orientation="vertical" className="h-3" />
              <div>
                <span className="font-bold text-neutral-900">11</span>
                <span className="ml-0.5 text-neutral-400">mongo features</span>
              </div>
              <Separator orientation="vertical" className="h-3" />
            </div>

            {/* Partner marquee */}
            <Marquee className="flex-1 [--duration:55s] [--gap:0.5rem] !p-0" pauseOnHover>
              {PARTNERS.map((p) => (
                <PartnerBadge key={p} name={p} />
              ))}
            </Marquee>
          </div>
        </footer>
      </main>
    </div>
  );
}
