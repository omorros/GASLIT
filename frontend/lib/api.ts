const base = () => process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8002";

export async function postVoiceInput(transcript: string, source: string, room: string) {
  const r = await fetch(`${base()}/api/voice-input`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript, source, room }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postForensicQA(question: string, quarantineId?: string) {
  const r = await fetch(`${base()}/api/forensic-qa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, quarantine_id: quarantineId ?? null }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ answer: string }>;
}

export async function fetchLiveKitToken(room: string, identity: string) {
  const r = await fetch(`${base()}/api/livekit/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ room, identity }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ token: string; url: string; room: string }>;
}

export async function postTTS(text: string): Promise<ArrayBuffer> {
  const r = await fetch(`${base()}/api/voice/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.arrayBuffer();
}
