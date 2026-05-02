"use client";

import { useEffect, useRef, useState } from "react";

/** Locked WS schema — see docs/contracts.md and ws/bridge.py */
export type AgentStatusPayload = {
  agent_id: string;
  status: "online" | "offline" | "starting" | string;
};

export type RetrievalPayload = {
  memory_id: string;
  agent_id: string;
  contract_id: string;
  retrieved_rank: number;
  score: number;
  filtered: boolean;
};

export type DriftUpdatePayload = {
  memory_id: string;
  drift_score: number;
  cohort_variance: number;
  retrieval_count: number;
  above_threshold: boolean;
};

export type QuarantinePayload = {
  quarantine_id: string;
  memory_id: string;
  drift_score?: number;
  cohort_variance?: number;
  responsible_user?: string;
  siblings_found?: string[];
  dossier_text?: string;
  investigation_id?: string;
};

export type GaslitEvent =
  | { type: "agent_status"; payload: AgentStatusPayload; ts: string }
  | { type: "retrieval"; payload: RetrievalPayload; ts: string }
  | { type: "drift_update"; payload: DriftUpdatePayload; ts: string }
  | { type: "quarantine"; payload: QuarantinePayload; ts: string };

export type ConnectionState = "off" | "connecting" | "live" | "error";

export type UseGaslitEventsResult = {
  state: ConnectionState;
  /** Latest 200 events (newest first) */
  events: GaslitEvent[];
  retrievals: RetrievalPayload[];
  drifts: Record<string, DriftUpdatePayload>;
  quarantines: QuarantinePayload[];
  /** Per-agent last-seen timestamp ms (synthesized from event activity) */
  agentHeartbeat: Record<string, number>;
  /** Hard reset all in-memory state */
  reset: () => void;
};

const MAX_EVENTS = 200;
const MAX_RETRIEVALS = 80;

export function useGaslitEvents(): UseGaslitEventsResult {
  const [state, setState] = useState<ConnectionState>("off");
  const [events, setEvents] = useState<GaslitEvent[]>([]);
  const [retrievals, setRetrievals] = useState<RetrievalPayload[]>([]);
  const [drifts, setDrifts] = useState<Record<string, DriftUpdatePayload>>({});
  const [quarantines, setQuarantines] = useState<QuarantinePayload[]>([]);
  const [agentHeartbeat, setAgentHeartbeat] = useState<Record<string, number>>({});
  const wsRef = useRef<WebSocket | null>(null);

  const reset = () => {
    setEvents([]);
    setRetrievals([]);
    setDrifts({});
    setQuarantines([]);
    setAgentHeartbeat({});
  };

  useEffect(() => {
    const url = process.env.NEXT_PUBLIC_WS_URL?.trim() || "ws://127.0.0.1:8003";
    setState("connecting");

    let ws: WebSocket;
    let reconnectTimer: number | null = null;
    let stopped = false;

    function connect() {
      try {
        ws = new WebSocket(url);
        wsRef.current = ws;
      } catch {
        setState("error");
        return;
      }

      ws.onopen = () => setState("live");
      ws.onerror = () => setState("error");
      ws.onclose = () => {
        if (stopped) return;
        setState("off");
        reconnectTimer = window.setTimeout(connect, 1500);
      };

      ws.onmessage = (ev) => {
        let msg: GaslitEvent;
        try {
          msg = JSON.parse(ev.data as string) as GaslitEvent;
        } catch {
          return;
        }
        if (!msg?.type) return;

        const now = Date.now();
        setEvents((prev) => [msg, ...prev].slice(0, MAX_EVENTS));

        if (msg.type === "retrieval") {
          setRetrievals((prev) => [msg.payload, ...prev].slice(0, MAX_RETRIEVALS));
          const who = msg.payload.agent_id || "librarian";
          setAgentHeartbeat((prev) => ({ ...prev, [who]: now, librarian: now, scribe: now }));
        } else if (msg.type === "drift_update") {
          setDrifts((prev) => ({ ...prev, [msg.payload.memory_id]: msg.payload }));
          setAgentHeartbeat((prev) => ({ ...prev, sentinel: now }));
        } else if (msg.type === "quarantine") {
          setQuarantines((prev) => [msg.payload, ...prev].slice(0, 16));
          setAgentHeartbeat((prev) => ({
            ...prev,
            sentinel: now,
            forensic: now,
          }));
        } else if (msg.type === "agent_status") {
          setAgentHeartbeat((prev) => ({ ...prev, [msg.payload.agent_id]: now }));
        }
      };
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      try {
        ws?.close();
      } catch {
        /* noop */
      }
    };
  }, []);

  return { state, events, retrievals, drifts, quarantines, agentHeartbeat, reset };
}
