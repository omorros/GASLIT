"use client";

import Script from "next/script";
import { createElement, useEffect, useState } from "react";
import { fetchConvaiConfig, formatApiNetworkError } from "@/lib/api";

/**
 * ElevenLabs Conversational AI embed — agent id from env or GET /api/voice/convai-config
 * (reads ELEVENLABS_AGENT_ID on the FastAPI process; no Next env required).
 */
export function ConvAIWidget() {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [phase, setPhase] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [promptVersion, setPromptVersion] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const envId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID?.trim();

    (async () => {
      try {
        const j = await fetchConvaiConfig();
        if (cancelled) return;
        setPromptVersion(j.prompt_version?.trim() || null);
        const aid = envId || j.agent_id?.trim() || "";
        if (aid) {
          setAgentId(aid);
          setPhase("ready");
        } else {
          setPhase("empty");
        }
      } catch (e) {
        if (cancelled) return;
        if (envId) {
          setAgentId(envId);
          setPhase("ready");
          setErrMsg(null);
          return;
        }
        setErrMsg(formatApiNetworkError(e));
        setPhase("error");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (phase === "loading") {
    return (
      <p style={{ fontSize: 13, opacity: 0.75, marginTop: 8 }}>
        Loading ElevenLabs agent…
      </p>
    );
  }

  if (phase === "error" && errMsg) {
    return (
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          padding: 12,
          borderRadius: 8,
          border: "1px solid #8b4513",
          background: "#1a1810",
          color: "#e8c4a8",
        }}
      >
        <strong style={{ color: "#f66" }}>Could not load Conv AI config.</strong>
        <p style={{ margin: "8px 0 0", whiteSpace: "pre-wrap" }}>{errMsg}</p>
      </div>
    );
  }

  if (phase === "empty" || !agentId) {
    return (
      <div
        style={{
          fontSize: 13,
          lineHeight: 1.5,
          padding: 12,
          borderRadius: 8,
          border: "1px dashed #5a5340",
          background: "#1a1810",
          color: "#c9c4bc",
        }}
      >
        <strong style={{ color: "#c9a227" }}>No ElevenLabs agent id.</strong>
        <p style={{ margin: "8px 0 0", opacity: 0.9 }}>
          Set <code style={{ color: "#e8e6e3" }}>ELEVENLABS_AGENT_ID</code> in the API&apos;s{" "}
          <code style={{ color: "#e8e6e3" }}>.env</code> (same process as{" "}
          <code style={{ color: "#e8e6e3" }}>uvicorn</code>), restart the API, refresh this page.
        </p>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 12 }}>
      {promptVersion && (
        <p style={{ fontSize: 11, opacity: 0.55, marginBottom: 8 }}>
          Server prompt bundle: <code style={{ color: "#c9a227" }}>{promptVersion}</code> — ElevenLabs agent must be
          updated separately if you changed <code style={{ color: "#c9a227" }}>FORENSIC_AUDITOR_SYSTEM_PROMPT</code> (
          run <code style={{ color: "#c9a227" }}>python scripts/create_convai_agent.py</code> or the dashboard).
        </p>
      )}
      <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
      {createElement("elevenlabs-convai", {
        "agent-id": agentId,
        style: { display: "block", minHeight: 120, width: "100%" },
      })}
    </div>
  );
}
