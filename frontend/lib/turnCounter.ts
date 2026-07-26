/**
 * Allocate the next Scribe turn_number for the operator console.
 *
 * memory_id is derived from (user_id, thread_id, turn_number). When the
 * scenario player supplies an explicit turn, the manual counter must still
 * advance past it — otherwise a later live-bench send reuses the same key
 * and Scribe treats the write as an idempotent no-op.
 */
export function allocateTurn(
  counter: { current: number },
  explicit?: number,
): number {
  if (explicit == null) {
    return counter.current++;
  }
  counter.current = Math.max(counter.current, explicit + 1);
  return explicit;
}
