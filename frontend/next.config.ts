import type { NextConfig } from "next";
import path from "path";
import { config } from "dotenv";

/**
 * Next.js only auto-loads `frontend/.env*`. Mirror repo-root `.env` so one file
 * can hold `ELEVENLABS_AGENT_ID`, `LIVEKIT_URL`, and `NEXT_PUBLIC_*` without
 * running `scripts/sync_frontend_env.py` every time.
 */
const rootDir = path.join(__dirname, "..");
// Later files override earlier (frontend/.env.local wins over repo-root .env).
for (const p of [
  path.join(rootDir, ".env"),
  path.join(rootDir, ".env.local"),
  path.join(__dirname, ".env"),
  path.join(__dirname, ".env.local"),
]) {
  config({ path: p, override: true });
}

/** Empty = browser uses same-origin `/backend/*` rewrite to FastAPI (avoids CORS / connection issues). */
const nextPublicApiBase = process.env.NEXT_PUBLIC_API_BASE?.trim() ?? "";
const agentId =
  process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID?.trim() ||
  process.env.ELEVENLABS_AGENT_ID?.trim() ||
  "";
const wsPort = process.env.WS_PORT?.trim() || "8003";
const defaultWsUrl = `ws://127.0.0.1:${wsPort}`;

/** Where Next.js proxies `/backend/*` (browser default when NEXT_PUBLIC_API_BASE is unset). */
function backendProxyTarget(): string {
  return (
    process.env.BACKEND_PROXY_TARGET?.trim() ||
    process.env.NEXT_PUBLIC_API_BASE?.trim() ||
    "http://127.0.0.1:8002"
  ).replace(/\/$/, "");
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_BASE: nextPublicApiBase,
    NEXT_PUBLIC_ELEVENLABS_AGENT_ID: agentId,
    NEXT_PUBLIC_LIVEKIT_URL:
      process.env.NEXT_PUBLIC_LIVEKIT_URL?.trim() ||
      process.env.LIVEKIT_URL?.trim() ||
      "",
    NEXT_PUBLIC_VOICE_TRANSCRIPTION_MODE:
      process.env.NEXT_PUBLIC_VOICE_TRANSCRIPTION_MODE?.trim() || "livekit",
    NEXT_PUBLIC_DEMO_QUARANTINE_ID:
      process.env.NEXT_PUBLIC_DEMO_QUARANTINE_ID?.trim() || "",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL?.trim() || defaultWsUrl,
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${backendProxyTarget()}/:path*`,
      },
    ];
  },
};

export default nextConfig;
