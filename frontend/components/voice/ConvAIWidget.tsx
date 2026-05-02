"use client";

import Script from "next/script";
import { createElement } from "react";

/**
 * ElevenLabs Conversational AI embed — uses public agent id only (no API secret in client).
 */
export function ConvAIWidget() {
  const agentId = process.env.NEXT_PUBLIC_ELEVENLABS_AGENT_ID ?? "";

  if (!agentId) {
    return (
      <p style={{ fontSize: 13, opacity: 0.75 }}>
        Set <code>NEXT_PUBLIC_ELEVENLABS_AGENT_ID</code> for the Conv AI widget.
      </p>
    );
  }

  return (
    <div style={{ marginTop: 12 }}>
      <Script src="https://unpkg.com/@elevenlabs/convai-widget-embed" strategy="afterInteractive" />
      {createElement("elevenlabs-convai", {
        "agent-id": agentId,
        style: { display: "block", minHeight: 120, width: "100%" },
      })}
    </div>
  );
}
