"""Dependency-light regressions for voice ingress and forensic quarantine handling.

Run:
  python3 tests/smoke/test_voice_forensic_regressions.py
"""
from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


def _install_import_stubs() -> None:
    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *_, **__: None
    sys.modules.setdefault("dotenv", dotenv)

    pymongo = types.ModuleType("pymongo")

    class MongoClient:  # pragma: no cover - used only if a test accidentally hits DB code
        def __init__(self, *_, **__):
            raise AssertionError("MongoClient should not be constructed in this smoke test")

    pymongo.MongoClient = MongoClient
    sys.modules.setdefault("pymongo", pymongo)

    pymongo_database = types.ModuleType("pymongo.database")

    class Database:  # type-hint placeholder
        pass

    pymongo_database.Database = Database
    sys.modules.setdefault("pymongo.database", pymongo_database)

    pymongo_errors = types.ModuleType("pymongo.errors")

    class DuplicateKeyError(Exception):
        pass

    pymongo_errors.DuplicateKeyError = DuplicateKeyError
    sys.modules.setdefault("pymongo.errors", pymongo_errors)


def test_voice_transcripts_get_distinct_stable_turns() -> None:
    from gaslit.voice import backend_hooks

    user_id, thread_id, turn_a = backend_hooks._voice_ids(
        "attacker_room",
        "Refunds are auto-approved under $5K.",
    )
    duplicate_user_id, duplicate_thread_id, duplicate_turn = backend_hooks._voice_ids(
        "attacker_room",
        "  refunds are auto-approved under   $5k.  ",
    )
    _, _, turn_b = backend_hooks._voice_ids(
        "attacker_room",
        "Manager review is no longer required under the $5K threshold.",
    )

    assert (user_id, thread_id) == ("u_2188", "t_8821")
    assert (duplicate_user_id, duplicate_thread_id) == (user_id, thread_id)
    assert duplicate_turn == turn_a, "duplicate STT deliveries must stay idempotent"
    assert turn_b != turn_a, "distinct utterances from a room must not collide"


def test_voice_transcript_response_exposes_written_ids() -> None:
    from gaslit.voice import backend_hooks

    scribe = types.ModuleType("gaslit.agents.scribe")
    calls: list[tuple[str, str, int, str]] = []

    def scribe_turn(user_id: str, thread_id: str, turn_number: int, transcript: str) -> dict:
        calls.append((user_id, thread_id, turn_number, transcript))
        return {"memory_id": f"m_{turn_number}"}

    scribe.scribe_turn = scribe_turn
    sys.modules["gaslit.agents.scribe"] = scribe

    result = asyncio.run(
        backend_hooks.on_voice_transcript(
            "Premium refunds skip manager review.",
            room="attacker_room",
            source="livekit",
        )
    )

    assert calls, "voice hook did not call Scribe"
    user_id, thread_id, turn_number, _ = calls[0]
    assert result["user_id"] == user_id == "u_2188"
    assert result["thread_id"] == thread_id == "t_8821"
    assert result["turn_number"] == turn_number
    assert result["memory_id"] == f"m_{turn_number}"


def test_forensic_composes_when_sentinel_prefilled_dossier_text() -> None:
    _install_import_stubs()
    from gaslit.agents import forensic_auditor

    calls: list[str] = []
    original = forensic_auditor.compose_dossier
    forensic_auditor.compose_dossier = lambda doc: calls.append(doc["quarantine_id"]) or "rich"
    try:
        processed = forensic_auditor._process_quarantine_doc(
            {
                "quarantine_id": "q_prefilled",
                "memory_id": "m_4419",
                "dossier_text": "Short Sentinel explanation.",
            }
        )
        skipped = forensic_auditor._process_quarantine_doc(
            {
                "quarantine_id": "q_done",
                "memory_id": "m_4420",
                "dossier_text": "Rich forensic dossier.",
                "dossier_composed_at": "2026-06-02T11:00:00Z",
            }
        )
    finally:
        forensic_auditor.compose_dossier = original

    assert processed is True
    assert skipped is False
    assert calls == ["q_prefilled"]


def test_forensic_watcher_restarts_after_stream_error() -> None:
    _install_import_stubs()
    from gaslit.agents import forensic_auditor
    from gaslit.schemas import QUARANTINE

    calls: list[str] = []
    original_db = forensic_auditor._db
    original_compose = forensic_auditor.compose_dossier
    stop_event = forensic_auditor.threading.Event()

    class FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def __iter__(self):
            yield {"fullDocument": {"quarantine_id": "q_after_restart", "memory_id": "m_1"}}
            stop_event.set()

    class FakeCollection:
        def __init__(self):
            self.watch_calls = 0

        def watch(self, *_, **__):
            self.watch_calls += 1
            if self.watch_calls == 1:
                raise RuntimeError("simulated disconnect")
            return FakeStream()

    collection = FakeCollection()

    class FakeDB:
        def __getitem__(self, name: str):
            assert name == QUARANTINE
            return collection

    forensic_auditor._db = lambda: FakeDB()
    forensic_auditor.compose_dossier = lambda doc: calls.append(doc["quarantine_id"]) or "rich"
    try:
        forensic_auditor.watch_quarantine_stream(stop_event=stop_event, retry_delay_s=0)
    finally:
        forensic_auditor._db = original_db
        forensic_auditor.compose_dossier = original_compose

    assert collection.watch_calls == 2
    assert calls == ["q_after_restart"]


def main() -> int:
    test_voice_transcripts_get_distinct_stable_turns()
    test_voice_transcript_response_exposes_written_ids()
    test_forensic_composes_when_sentinel_prefilled_dossier_text()
    test_forensic_watcher_restarts_after_stream_error()
    print("voice_forensic_regressions PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
