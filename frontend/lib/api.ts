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

export async function fetchConvaiConfig(): Promise<{ agent_id: string | null }> {
  const r = await apiFetch(apiUrl("/api/voice/convai-config"));
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ agent_id: string | null }>;
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

export async function postTTS(text: string): Promise<ArrayBuffer> {
  const r = await apiFetch(apiUrl("/api/voice/tts"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.arrayBuffer();
}
