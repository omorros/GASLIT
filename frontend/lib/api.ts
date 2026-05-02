/**
 * API calls target either:
 * - `NEXT_PUBLIC_API_BASE` when set (direct to FastAPI), or
 * - `/backend/*` (proxied by Next.js → FastAPI) so the browser only talks to :3000.
 */

const DEFAULT_SERVER_API = "http://127.0.0.1:8002";

/** Resolved API root for this runtime (browser uses same-origin proxy by default). */
export function apiUrl(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  const explicit = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (explicit) {
    return `${explicit.replace(/\/$/, "")}${normalized}`;
  }
  if (typeof window !== "undefined") {
    return `/backend${normalized}`;
  }
  return `${DEFAULT_SERVER_API}${normalized}`;
}

/** Turns browser "Failed to fetch" into an actionable message (API down / wrong port). */
export function formatApiNetworkError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  if (
    err instanceof TypeError ||
    raw.includes("Failed to fetch") ||
    raw.includes("NetworkError") ||
    raw.includes("Load failed")
  ) {
    return (
      `Cannot reach the FastAPI backend. Start it from the repo root: ` +
      `uvicorn api.main:app --port 8002 ` +
      `(venv on, .env with MONGODB_URI + LIVEKIT_* + ELEVENLABS_*). ` +
      `The UI proxies /backend → :8002 so you only need Next + API running.`
    );
  }
  return raw;
}

async function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (e) {
    throw new Error(formatApiNetworkError(e));
  }
}

export type ConvaiPublicConfig = {
  agent_id: string | null;
  prompt_version?: string;
  system_prompt_hint?: string;
};

export async function fetchConvaiConfig(): Promise<ConvaiPublicConfig> {
  const r = await apiFetch(apiUrl("/api/voice/convai-config"));
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<ConvaiPublicConfig>;
}

export async function postVoiceInput(transcript: string, source: string, room: string) {
  const r = await apiFetch(apiUrl("/api/voice-input"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript, source, room }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postForensicQA(question: string, quarantineId?: string) {
  const r = await apiFetch(apiUrl("/api/forensic-qa"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, quarantine_id: quarantineId ?? null }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ answer: string }>;
}

export async function fetchLiveKitToken(room: string, identity: string) {
  const r = await apiFetch(apiUrl("/api/livekit/token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ room, identity }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ token: string; url: string; room: string }>;
}

export type Persona = "adversary" | "narrator" | "forensic";

export async function postTTS(
  text: string,
  persona: Persona = "forensic",
): Promise<ArrayBuffer> {
  const r = await apiFetch(apiUrl("/api/voice/tts"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, persona }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.arrayBuffer();
}

export type AgentRequest = {
  message: string;
  user_id: string;
  thread_id: string;
  turn_number: number;
  tool_name?: string;
};

export type AgentResponse = {
  response: string;
  retrieved_memories: Array<Record<string, unknown>>;
  filtered_memories?: Array<Record<string, unknown>>;
  tool_calls: Array<{ tool: string; amount?: number }>;
  contract_applied?: string | null;
  agent_id: "unprotected" | "gaslit";
};

export async function postUnprotectedAgent(req: AgentRequest): Promise<AgentResponse> {
  const r = await apiFetch(apiUrl("/api/unprotected-agent"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postGaslitAgent(req: AgentRequest): Promise<AgentResponse> {
  const r = await apiFetch(apiUrl("/api/gaslit-agent"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type TrustScore = {
  score: number;
  n_memories: number;
  n_quarantined: number;
  ts: string;
};

export async function getTrustScore(): Promise<TrustScore> {
  const r = await apiFetch(apiUrl("/api/trust-score"));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type SentinelStatus = {
  status: "online" | "offline" | "starting" | string;
  mode: string;
  run_id?: string;
  superstep?: number;
  cluster?: string | null;
  service?: string | null;
  note?: string;
};

export async function getSentinelStatus(): Promise<SentinelStatus> {
  const r = await apiFetch(apiUrl("/api/sentinel-status"));
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function startSentinel(): Promise<SentinelStatus> {
  const r = await apiFetch(apiUrl("/api/start-sentinel"), { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function killSentinel(): Promise<SentinelStatus> {
  const r = await apiFetch(apiUrl("/api/kill-sentinel"), { method: "POST" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type MinjaLaunch = {
  attack_id: string;
  status: string;
  turns: number;
};

export async function launchMinja(narrationDelayMs = 1500): Promise<MinjaLaunch> {
  const r = await apiFetch(apiUrl("/api/launch-minja-attack"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ narration_delay_ms: narrationDelayMs }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export type FloodLaunch = { run_id: string; duration_s: number; qps: number; source: string };

export async function postScenarioFlood(
  durationS = 15,
  qps = 5,
  source: "canned" | "live" = "canned",
): Promise<FloodLaunch> {
  const r = await apiFetch(apiUrl("/api/scenario/flood"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ duration_s: durationS, qps, source }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postTriggerDrift(): Promise<unknown> {
  const r = await apiFetch(apiUrl("/api/demo/trigger-drift"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export function complianceExportUrl(quarantineId: string): string {
  return apiUrl(`/api/compliance-export/${encodeURIComponent(quarantineId)}`);
}
