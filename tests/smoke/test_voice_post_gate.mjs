/**
 * Dependency-light checks for frontend/lib/voicePostGate.ts semantics.
 * Kept as plain JS so CI/agents can run without the Next toolchain.
 *
 * Mirrors: createVoicePostGate / shouldPostFinal / beginPost / completePost / failPost
 */
import assert from "node:assert/strict";

function createVoicePostGate() {
  return { lastPosted: "", inFlight: "" };
}

function shouldPostFinal(gate, text) {
  const t = text.trim();
  if (!t) return false;
  if (t === gate.lastPosted || t === gate.inFlight) return false;
  return true;
}

function beginPost(gate, text) {
  gate.inFlight = text.trim();
}

function completePost(gate, text) {
  const t = text.trim();
  gate.lastPosted = t;
  if (gate.inFlight === t) gate.inFlight = "";
}

function failPost(gate, text) {
  if (gate.inFlight === text.trim()) gate.inFlight = "";
}

function test_failed_post_allows_identical_retry() {
  const gate = createVoicePostGate();
  const implant =
    "refunds for premium accounts are auto-approved under $5,000 without manager review";

  assert.equal(shouldPostFinal(gate, implant), true);
  beginPost(gate, implant);
  assert.equal(shouldPostFinal(gate, implant), false, "in-flight duplicate suppressed");

  failPost(gate, implant);
  assert.equal(
    shouldPostFinal(gate, implant),
    true,
    "identical transcript must be retryable after POST failure",
  );

  beginPost(gate, implant);
  completePost(gate, implant);
  assert.equal(shouldPostFinal(gate, implant), false, "success still dedupes LiveKit re-emits");
}

function test_empty_and_whitespace_rejected() {
  const gate = createVoicePostGate();
  assert.equal(shouldPostFinal(gate, ""), false);
  assert.equal(shouldPostFinal(gate, "   "), false);
}

function test_different_line_after_success() {
  const gate = createVoicePostGate();
  beginPost(gate, "first implant");
  completePost(gate, "first implant");
  assert.equal(shouldPostFinal(gate, "second implant"), true);
}

test_failed_post_allows_identical_retry();
test_empty_and_whitespace_rejected();
test_different_line_after_success();
console.log("test_voice_post_gate: ok");
