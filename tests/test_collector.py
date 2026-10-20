"""Contract fixtures and synchronization tests for OpenCode V2 metadata."""

import json
import sqlite3
from pathlib import Path

import pytest

from graphen_trace.adapters.opencode.normalize import normalize_timeline
from graphen_trace.adapters.opencode.source import (
    OpenCodeSource,
    UnsupportedSourceError,
)
from graphen_trace.services.collector import Collector
from graphen_trace.services.storage import Storage


def _timeline(
    storage: Storage, session_id: str, page: tuple[int, int] = (50, 0)
) -> dict:
    """Builds the API projection from the canonical message payload rows."""
    result = storage.timeline(session_id, page)
    result["items"] = normalize_timeline(result["items"])
    return result


@pytest.fixture
def source_database(tmp_path: Path) -> Path:
    """Creates a synthetic V2 source without personal information."""
    path = tmp_path / "opencode.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            "CREATE TABLE session_v2 (id TEXT PRIMARY KEY, project_id TEXT, "
            "parent_id TEXT, title TEXT, directory TEXT, version TEXT, "
            "time_created INTEGER, time_updated INTEGER);"
            "CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT, "
            "type TEXT, seq INTEGER, time_created INTEGER, time_updated INTEGER, "
            "data TEXT);"
            "INSERT INTO session_v2 VALUES "
            "('s1', 'project', NULL, 'Example', '/example', '2.0.32', 1000, 1000);"
        )
        connection.execute(
            "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "m1",
                "s1",
                "assistant",
                1,
                1000,
                1000,
                json.dumps(
                    {
                        "model": {"id": "example", "providerID": "openai"},
                        "tokens": {
                            "input": 10,
                            "output": 4,
                            "reasoning": 2,
                            "cache": {"read": 5, "write": 0},
                        },
                        "content": [{"text": "sensitive output"}],
                    }
                ),
            ),
        )
    return path


@pytest.fixture
def collector(source_database: Path, tmp_path: Path) -> Collector:
    """Builds a collector with isolated source and target databases."""
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    return Collector(OpenCodeSource(source_database, "2.0.32"), storage)


def test_replayed_tool_id_uses_latest_observation(collector: Collector) -> None:
    """A native call replayed across messages is not another execution."""
    data = {
        "content": [
            {
                "type": "tool",
                "id": "same-call",
                "name": "task",
                "state": {"status": "running"},
            }
        ]
    }
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute(
            "UPDATE session_message SET data=?",
            (json.dumps(data),),
        )
        data["content"][0]["state"]["status"] = "completed"
        connection.execute(
            "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("m2", "s1", "assistant", 2, 2000, 2000, json.dumps(data)),
        )
    collector.sync()
    timeline = _timeline(collector.storage, "s1")["items"]
    assert timeline[0]["tools"] == []
    assert timeline[1]["tools"][0]["status"] == "completed"
    assert timeline[1]["tools"][0]["duration_ms"] is None


def test_import_is_idempotent_and_captures_complete_content(
    collector: Collector,
) -> None:
    """A restart resumes committed revisions and full native content is preserved."""
    assert collector.sync() == 1
    assert collector.sync() == 0
    resumed = Collector(collector.source, collector.storage)
    assert resumed.sync() == 0
    sessions = collector.storage.sessions(50, 0)
    assert len(sessions) == 1
    assert sessions[0]["usage"]["input_tokens"] == 10
    assert sessions[0]["usage"]["cache_read_tokens"] == 5
    assert "sensitive output" not in json.dumps(sessions)
    assert "sensitive output" in json.dumps(_timeline(collector.storage, "s1"))
    assert collector.status["state"] == "collecting"


def test_sqlite_stores_one_message_payload_and_minimal_session_projection(
    collector: Collector,
) -> None:
    """The Graphen database keeps one native payload, not a second raw projection."""
    collector.sync()
    with collector.storage.connect() as connection:
        session_data = connection.execute(
            "SELECT data FROM observed_session WHERE agent='opencode' AND id='s1'"
        ).fetchone()[0]
        message_data = connection.execute(
            "SELECT data FROM observed_message WHERE agent='opencode' AND id='m1'"
        ).fetchone()[0]
    assert "raw_data" not in session_data
    assert "source_record" not in session_data
    with sqlite3.connect(collector.source.path) as source_connection:
        source_data = source_connection.execute(
            "SELECT data FROM session_message WHERE id='m1'"
        ).fetchone()[0]
    assert json.loads(message_data) == json.loads(source_data)
    assert "raw_data" not in message_data
    assert "tools" not in message_data


def test_full_records_and_usage_keep_native_values(collector: Collector) -> None:
    """Full payloads survive normalization and tokens are not double-counted."""
    payload = {
        "content": [
            {"type": "reasoning", "text": "reasoning details"},
            {"type": "text", "text": "full response " * 1000},
        ],
        "tokens": {
            "input": 10,
            "output": 4,
            "reasoning": 2,
            "cache": {"read": 5, "write": 0},
        },
        "cost": 0.25,
        "extra_native_field": {"keep": True},
    }
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("UPDATE session_message SET data=?", (json.dumps(payload),))
        connection.execute(
            "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "m2",
                "s1",
                "assistant",
                2,
                2000,
                2000,
                json.dumps({"tokens": {"input": 20}}),
            ),
        )
    collector.sync()
    assert _timeline(collector.storage, "s1")["items"][0]["raw_data"] == payload
    session = collector.storage.session("s1")
    assert "raw_data" not in session
    assert session["usage"]["input_tokens"] == 30
    assert session["usage"]["output_tokens"] == 4
    assert "input_tokens" not in session["usage_incomplete"]
    assert "output_tokens" in session["usage_incomplete"]
    totals = collector.storage.usage()
    assert totals["session_count"] == 1
    assert totals["generation_count"] == 2
    assert totals["usage"]["input_tokens"] == 30
    assert totals["usage"]["cache_read_tokens"] == 5
    assert totals["reported_cost"] == 0.25
    assert totals["cost_incomplete"]


def test_message_update_and_deletion_are_reconciled(collector: Collector) -> None:
    """Changes replace aggregates instead of double-counting usage."""
    collector.sync()
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute(
            "UPDATE session_message SET time_updated=2000, data=?",
            (json.dumps({"tokens": {"input": 20}}),),
        )
    assert collector.sync() == 1
    assert collector.storage.sessions(50, 0)[0]["usage"]["input_tokens"] == 20
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("DELETE FROM session_message")
    assert collector.sync() == 1
    assert collector.storage.sessions(50, 0)[0]["usage"]["input_tokens"] is None
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("DELETE FROM session_v2")
    collector.sync()
    assert collector.storage.sessions(50, 0) == []
    assert _timeline(collector.storage, "s1")["total"] == 0


def test_timeline_preserves_tool_state_and_payloads(collector: Collector) -> None:
    """Tools retain native IDs, state, input and full results without truncation."""
    tool = {
        "type": "tool",
        "id": "call-1",
        "name": "bash",
        "state": {
            "status": "completed",
            "input": {"command": "private command"},
            "content": [{"text": "private output"}],
            "metadata": {"exit": 1, "sessionId": "child"},
        },
        "time": {"created": 1000, "completed": 1200},
    }
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute(
            "INSERT INTO session_message VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "user-1",
                "s1",
                "user",
                0,
                900,
                900,
                json.dumps({"text": "private prompt"}),
            ),
        )
        connection.execute(
            "UPDATE session_message SET data=?, time_updated=2000 WHERE id='m1'",
            (json.dumps({"content": [tool, tool], "finish": "tool-calls"}),),
        )
    collector.sync()
    page = _timeline(collector.storage, "s1")
    assert [item["kind"] for item in page["items"]] == ["user", "assistant"]
    generation = page["items"][1]
    assert generation["interaction_id"] == "user-1"
    assert generation["interaction_source"] == "sequence"
    assert len(generation["tools"]) == 1
    execution = generation["tools"][0]
    assert execution["status"] == "completed"
    assert execution["exit_code"] == 1
    assert execution["duration_ms"] == 200
    assert execution["child_session_id"] == "child"
    assert execution["input"] == {"command": "private command"}
    assert execution["output"] == [{"text": "private output"}]
    assert page["items"][0]["raw_data"]["text"] == "private prompt"
    assert _timeline(collector.storage, "s1", (1, 1))["items"][0]["id"] == "m1"
    assert _timeline(collector.storage, "s1", (1, 1))["total"] == 2


@pytest.mark.parametrize("version", ["2.0.33", "2.1.0", "3.0.0", "unknown"])
def test_unvalidated_versions_collect_by_structural_contract(
    collector: Collector,
    version: str,
) -> None:
    """Version warnings do not prevent collection of a recognizable projection."""
    collector.source.version = version
    assert collector.sync() == 1
    assert collector.status["state"] == "partial"
    assert collector.status["warnings"]
    assert collector.storage.sessions(50, 0)[0]["usage"]["input_tokens"] == 10
    assert collector.sync() == 0
    assert collector.status["warnings"]


def test_unavailable_messages_preserve_sessions_and_previous_details(
    collector: Collector,
) -> None:
    """A missing message contract disables that capability, not all capture."""
    collector.sync()
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("DROP TABLE session_message")
    assert collector.sync() == 1
    assert collector.status["state"] == "partial"
    assert not collector.status["capabilities"]["messages"]
    assert collector.storage.session("s1")["message_count"] is None
    assert _timeline(collector.storage, "s1")["total"] == 1
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("DROP TABLE session_v2")
    with pytest.raises(UnsupportedSourceError):
        collector.sync()


def test_missing_optional_columns_do_not_block_readable_records(
    collector: Collector,
) -> None:
    """Missing metadata and order disable only the capabilities that depend on them."""
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("ALTER TABLE session_v2 DROP COLUMN title")
        connection.execute("ALTER TABLE session_message DROP COLUMN seq")
        connection.execute("ALTER TABLE session_message DROP COLUMN time_updated")
    collector.sync()
    assert collector.status["state"] == "partial"
    assert collector.storage.session("s1")["title"] is None
    timeline = _timeline(collector.storage, "s1")["items"]
    assert timeline[0]["sequence"] is None
    assert timeline[0]["interaction_id"] is None
    assert timeline[0]["usage"]["input_tokens"] == 10
    assert collector.sync() == 1


def test_changed_token_format_does_not_hide_tools_or_raw_content(
    collector: Collector,
) -> None:
    """A field-specific normalization error leaves the other features usable."""
    data = {
        "tokens": ["new-format"],
        "content": [
            {"type": "text", "text": "preserved response"},
            {
                "type": "tool",
                "id": "call",
                "name": "bash",
                "state": {"status": "running"},
            },
        ],
    }
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute("UPDATE session_message SET data=?", (json.dumps(data),))
    collector.sync()
    item = _timeline(collector.storage, "s1")["items"][0]
    assert item["usage"] is None
    assert item["tools"][0]["name"] == "bash"
    assert item["raw_data"] == data
    assert collector.status["state"] == "partial"


def test_missing_source_is_not_created(tmp_path: Path) -> None:
    """Read-only access never creates an absent agent database."""
    source = OpenCodeSource(tmp_path / "missing.db", "2.0.32")
    with pytest.raises(sqlite3.OperationalError):
        with source.snapshot():
            pass
    assert not source.path.exists()


@pytest.mark.parametrize("version", ["2.0.32", "v2.0.32", "opencode v2.0.32"])
def test_cli_version_formats_are_recognized(
    source_database: Path,
    version: str,
) -> None:
    """Version detection accepts the validated executable version formats."""
    source = OpenCodeSource(source_database, version)
    with source.snapshot() as connection:
        assert len(source.session_index(connection)) == 1


def test_source_is_read_only_and_unknown_payloads_are_preserved(
    collector: Collector,
) -> None:
    """Unrecognized JSON is preserved and warned about, not discarded."""
    collector.sync()
    with collector.source.snapshot() as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM session_v2")
    previous = collector.storage.revisions("opencode:sqlite:v2")
    with sqlite3.connect(collector.source.path) as connection:
        connection.execute(
            "UPDATE session_message SET time_updated=3000, data='invalid json'"
        )
    collector.sync()
    assert collector.storage.revisions("opencode:sqlite:v2") != previous
    item = _timeline(collector.storage, "s1")["items"][0]
    assert item["raw_payload"] == "invalid json"
    assert item["normalization_warnings"]
    assert collector.status["state"] == "partial"
    assert collector.sync() == 0
    assert collector.status["warnings"]


def test_committed_wal_updates_are_visible(collector: Collector) -> None:
    """The reader observes WAL updates while the agent connection remains open."""
    collector.sync()
    connection = sqlite3.connect(collector.source.path)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("UPDATE session_v2 SET title='Updated', time_updated=4000")
        connection.commit()
        assert collector.sync() == 1
        assert collector.storage.sessions(50, 0)[0]["title"] == "Updated"
    finally:
        connection.close()


def test_storage_rolls_back_records_and_revisions(collector: Collector) -> None:
    """A failure during persistence never commits a partially advanced revision."""
    collector.sync()
    record = collector.storage.sessions(50, 0)[0]
    previous_revision = record["revision"]
    record["revision"] = "uncommitted"
    with pytest.raises(KeyError):
        collector.storage.apply("opencode:sqlite:v2", [record, {}], {"s1"})
    assert collector.storage.revisions("opencode:sqlite:v2")["s1"] == previous_revision
