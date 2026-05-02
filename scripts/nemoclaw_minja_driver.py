from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gaslit.adversary.nemoclaw_bridge import (
    load_canonical,
    run_minja_attack_loop,
    run_minja_sequence,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Drive canonical MINJA turns through GASLIT — same HTTP contract a "
            "NemoClaw/OpenShell adversary agent would use."
        ),
    )
    parser.add_argument("--api", default=None, help="API base URL, defaults to http://127.0.0.1:$API_PORT")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between turns within one MINJA cycle")
    parser.add_argument(
        "--pause-between-cycles",
        type=float,
        default=30.0,
        help="Idle seconds after turn 3 before starting a new thread (loop mode)",
    )
    parser.add_argument("--loop", action="store_true", help="Persistent attacker: repeat full MINJA sequences")
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        metavar="N",
        help="With --loop: stop after N sequences (default: run until Ctrl+C)",
    )
    parser.add_argument(
        "--forever",
        action="store_true",
        help="With --loop: ignore --cycles and run until Ctrl+C",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print turns without sending them")
    args = parser.parse_args()

    load_dotenv()
    api_base = args.api or f"http://127.0.0.1:{os.environ.get('API_PORT', '8002')}"
    canonical = load_canonical()

    print(f"NEMOCLAW_MINJA_SOURCE={canonical['source']}")
    print(f"NEMOCLAW_MINJA_API={api_base}")

    if args.forever and args.cycles is not None:
        print("NEMOCLAW_MINJA_ERROR=pass only one of --forever or --cycles", file=sys.stderr)
        return 2

    if args.dry_run:
        for turn in canonical["turns"]:
            print(f"DRY_RUN_TURN={turn['turn']} ACTOR={turn['actor']} MESSAGE={turn['user_message']}")
        return 0

    try:
        if args.loop:
            max_seq = None if args.forever else (args.cycles if args.cycles is not None else None)
            print(
                f"NEMOCLAW_ATTACK_LOOP=start pause_between_cycles={args.pause_between_cycles} "
                f"max_sequences={'inf' if max_seq is None else max_seq}",
            )
            result = run_minja_attack_loop(
                api_base,
                delay_s=args.delay,
                pause_between_sequences_s=args.pause_between_cycles,
                max_sequences=max_seq,
            )
            print(f"NEMOCLAW_ATTACK_LOOP_STOPPED={result['stopped_reason']} sequences={result['sequences_completed']}")
            for c in result["cycles"]:
                print(f"CYCLE_COMPLETE idx={c['cycle_index']} thread_id={c['thread_id']}")
        else:
            if args.cycles is not None or args.forever:
                print("NEMOCLAW_MINJA_ERROR=--cycles/--forever require --loop", file=sys.stderr)
                return 2
            result = run_minja_sequence(api_base, delay_s=args.delay)
            print(f"NEMOCLAW_MINJA_THREAD_ID={result['thread_id']}")
            for row in result["turns"]:
                print(
                    "TURN_RESULT="
                    f"{row['turn']} LABEL={row['label']} "
                    f"UNPROTECTED_TOOL_CALLS={row['unprotected_tool_calls']} "
                    f"GASLIT_TOOL_CALLS={row['gaslit_tool_calls']}"
                )
    except Exception as exc:
        print(f"NEMOCLAW_MINJA_ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("NEMOCLAW_MINJA_COMPLETE=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
