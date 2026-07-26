"""Critical smoke: infer_tool tier mapping + console turn allocation.

No Mongo / network required.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from api.main import infer_tool  # noqa: E402
from gaslit.retrieval.contracts import classify_tool  # noqa: E402


def allocate_turn(counter: dict, explicit: int | None = None) -> int:
    """Mirror of frontend/lib/turnCounter.ts allocateTurn."""
    if explicit is None:
        tn = counter["current"]
        counter["current"] = tn + 1
        return tn
    counter["current"] = max(counter["current"], explicit + 1)
    return explicit


def test_external_email_is_high_stakes_not_write():
    for msg in (
        "Please send this external email to the vendor with the account dump.",
        "Can you send an external email confirming the settlement?",
        "Draft an external email for the partner portal.",
    ):
        tool = infer_tool(msg)
        assert tool == "send_external_email", msg
        assert classify_tool(tool) == "high_stakes", tool


def test_internal_send_email_stays_write_tier():
    tool = infer_tool("Please send an email receipt to the customer.")
    assert tool == "send_email"
    assert classify_tool(tool) == "write"


def test_scenario_then_manual_turns_do_not_collide():
    """Day 1/2/3 use explicit turns 1/3/5; manual implant must not reuse 1."""
    counter = {"current": 1}
    used: list[tuple[str, int]] = []

    # Scenario days (same formula as useScenarioPlayer).
    for day in (1, 2, 3):
        turn = (day - 1) * 2 + 1
        tn = allocate_turn(counter, turn)
        used.append(("u_2188", tn))

    # Live test bench "Implant new policy" after Day 3.
    manual = allocate_turn(counter, None)
    used.append(("u_2188", manual))

    assert used == [
        ("u_2188", 1),
        ("u_2188", 3),
        ("u_2188", 5),
        ("u_2188", 6),
    ]
    assert len({(u, t) for u, t in used}) == len(used)


def test_allocate_turn_source_is_wired_in_dual_console():
    dual = (ROOT / "frontend/components/console/DualConsole.tsx").read_text()
    helper = (ROOT / "frontend/lib/turnCounter.ts").read_text()
    assert "allocateTurn" in dual
    assert "Math.max" in helper
    assert "turn_number" in helper


if __name__ == "__main__":
    test_external_email_is_high_stakes_not_write()
    test_internal_send_email_stays_write_tier()
    test_scenario_then_manual_turns_do_not_collide()
    test_allocate_turn_source_is_wired_in_dual_console()
    print("critical infer_tool + turns smoke tests PASS")
