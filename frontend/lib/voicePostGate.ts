/**
 * Dedup gate for attacker voice finals → POST /api/voice-input.
 *
 * LiveKit (and Web Speech) can emit the same final transcript more than once.
 * We must suppress duplicates after a *successful* post, but never permanently
 * block retries when the POST fails — otherwise implants are silently lost.
 */

export type VoicePostGateState = {
  lastPosted: string;
  inFlight: string;
};

export function createVoicePostGate(): VoicePostGateState {
  return { lastPosted: "", inFlight: "" };
}

/** True when this final text should be posted (not empty, not already posted/in-flight). */
export function shouldPostFinal(gate: VoicePostGateState, text: string): boolean {
  const t = text.trim();
  if (!t) return false;
  if (t === gate.lastPosted || t === gate.inFlight) return false;
  return true;
}

export function beginPost(gate: VoicePostGateState, text: string): void {
  gate.inFlight = text.trim();
}

export function completePost(gate: VoicePostGateState, text: string): void {
  const t = text.trim();
  gate.lastPosted = t;
  if (gate.inFlight === t) gate.inFlight = "";
}

/** Clear in-flight so the same transcript can be retried after a failed POST. */
export function failPost(gate: VoicePostGateState, text: string): void {
  if (gate.inFlight === text.trim()) gate.inFlight = "";
}
