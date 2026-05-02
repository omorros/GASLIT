"""Smoke test — belief-contract auto-classifier picks the right tier.

Pure unit test, no DB needed.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from gaslit.retrieval.contracts import classify_tool, contract_for, _filters_for, _weights_for


def test_high_stakes_patterns():
    for t in ("refund_request", "process_refund", "transfer_funds",
              "delete_account", "pay_invoice", "send_external_email",
              "wire_funds", "cancel_subscription"):
        assert classify_tool(t) == "high_stakes", f"{t} should be high_stakes"


def test_write_patterns():
    for t in ("update_preference", "create_ticket", "send_email",
              "post_message", "modify_address", "email_receipt",
              "escalate_to_manager"):
        assert classify_tool(t) == "write", f"{t} should be write"


def test_read_only_default():
    for t in ("lookup_order", "get_balance", "list_transactions"):
        assert classify_tool(t) == "read_only", f"{t} should be read_only"


def test_high_stakes_contract_requires_hmac_and_tool_grounded():
    c = contract_for("process_refund")
    assert c["tier"] == "high_stakes"
    assert c["requires_hmac"] is True
    assert c["fail_open"] is False
    flat = {k: v for f in c["filters"] for k, v in f.items()}
    assert flat.get("source_type") == "tool_grounded"
    assert flat.get("quarantined") is False


def test_high_stakes_weights_favour_provenance():
    w = _weights_for("high_stakes")
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert w["provenance"] >= 0.4


if __name__ == "__main__":
    test_high_stakes_patterns()
    test_write_patterns()
    test_read_only_default()
    test_high_stakes_contract_requires_hmac_and_tool_grounded()
    test_high_stakes_weights_favour_provenance()
    print("auto_classifier smoke tests PASS")
