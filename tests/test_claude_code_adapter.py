"""Synthetic contracts for passive Claude Code transcript collection."""

import copy
import json
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from graphen_trace.adapters.claude_code import ClaudeCodeAdapter, normalize
from graphen_trace.adapters.claude_code.collector import ClaudeCodeCollector
from graphen_trace.adapters.claude_code.source import ClaudeCodeSource
from graphen_trace.api.app import create_app
from graphen_trace.services.discovery import AGENTS
from graphen_trace.services.storage import Storage


def session_records() -> list[dict]:
    """Returns invented data, never a real Claude Code transcript."""
    return [
        {
            "type": "user",
            "sessionId": "synthetic-session",
            "uuid": "user-1",
            "cwd": "/synthetic/workspace",
            "version": "2.1.311",
            "timestamp": "2026-11-01T10:00:00Z",
            "message": {"role": "user", "content": "synthetic prompt"},
        },
        {
            "type": "assistant",
            "sessionId": "synthetic-session",
            "uuid": "assistant-1",
            "parentUuid": "user-1",
            "timestamp": "2026-11-01T10:00:01Z",
            "requestedModel": "requested-model",
            "message": {
                "id": "generation-1",
                "role": "assistant",
                "model": "effective-model",
                "provider": "synthetic-provider",
                "stop_reason": "tool_use",
                "content": [
                    {"type": "thinking", "thinking": "synthetic thinking"},
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "Bash",
                        "input": {"command": "true"},
                    },
                ],
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 3,
                    "cache_creation_input_tokens": 2,
                    "output_tokens_details": {"reasoning_tokens": 99},
                },
            },
        },
        {
            "type": "user",
            "uuid": "result-1",
            "timestamp": "2026-11-01T10:00:02Z",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "call-1",
                        "content": "synthetic tool output",
                        "is_error": False,
                    }
                ],
            },
        },
        {"type": "cost-state", "totalCostUSD": 12.5, "modelUsage": {}},
        {"type": "future-type", "unknown": {"preserved": True}},
    ]


def write_session(root: Path, records: list[dict], name: str = "session") -> Path:
    workspace = root / "encoded-workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / f"{name}.jsonl"
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return path


def create_collector(root: Path) -> ClaudeCodeCollector:
    storage = Storage(root / "graphen.db")
    storage.initialize()
    return ClaudeCodeCollector(ClaudeCodeSource(root / "projects"), storage)


def test_lossless_projection_and_conservative_usage(tmp_path: Path) -> None:
    records = session_records()
    write_session(tmp_path, records)
    source = ClaudeCodeSource(tmp_path, "installed-version")
    session = normalize.normalize_session(source.sessions()[0])
    assert session["id"] == "synthetic-session"
    assert session["version"] == "2.1.311"
    assert session["parent_id"] is None
    assert session["reported_cost"] is None
    assert session["cost_incomplete"] is True
    assert session["usage"] == {
        "input_tokens": 12,
        "output_tokens": 4,
        "cache_read_tokens": 3,
        "cache_write_tokens": 2,
        "reasoning_tokens": None,
    }
    assert session["usage_incomplete"] == ["reasoning_tokens"]
    assert session["generation_count"] == 1
    assert [json.loads(row["data"]) for row in session["timeline_records"]] == records
    assistant = session["timeline"][1]
    assert assistant["id"] == "assistant-1"
    assert assistant["model"]["id"] == "effective-model"
    assert assistant["source_record"]["requestedModel"] == "requested-model"
    assert assistant["tools"][0]["status"] == "completed"
    assert assistant["tools"][0]["output"] == "synthetic tool output"
    assert assistant["tools"][0]["duration_ms"] is None
    assert assistant["interaction_id"] is None


def test_sync_append_rewrite_remove_and_idempotency(tmp_path: Path) -> None:
    collector = create_collector(tmp_path)
    records = session_records()
    path = write_session(collector.source.projects_dir, records)
    assert collector.sync() == 1
    assert collector.sync() == 0
    records.append({"type": "permission-mode", "permissionDecision": "allow"})
    write_session(collector.source.projects_dir, records)
    assert collector.sync() == 1
    records[1]["message"]["usage"]["output_tokens"] = 7
    write_session(collector.source.projects_dir, records)
    assert collector.sync() == 1
    assert collector.storage.usage("claude")["usage"]["output_tokens"] == 7
    path.unlink()
    collector.sync()
    assert collector.storage.revisions(normalize.SOURCE, "claude") == {}


def test_incomplete_snapshot_retains_valid_data_and_hides_details(
    tmp_path: Path,
) -> None:
    collector = create_collector(tmp_path)
    path = write_session(collector.source.projects_dir, session_records())
    collector.sync()
    committed = collector.storage.revisions(normalize.SOURCE, "claude")
    path.write_text('{"private-content":', encoding="utf-8")
    assert collector.sync() == 0
    assert collector.status["state"] == "partial"
    assert collector.storage.revisions(normalize.SOURCE, "claude") == committed
    diagnostics = json.dumps(collector.status)
    assert "private-content" not in diagnostics
    assert str(path) not in diagnostics
    assert "synthetic-session" not in diagnostics


def test_bad_file_does_not_block_other_sessions(tmp_path: Path) -> None:
    write_session(tmp_path, session_records())
    bad_path = write_session(tmp_path, [], "bad")
    bad_path.write_bytes(b"[]\ninvalid\n\xff\n")
    source = ClaudeCodeSource(tmp_path)
    assert len(source.sessions()) == 1
    assert source.snapshot_incomplete
    assert len(source.warnings) == 3


def test_identity_conflicts_and_symlinks_are_not_ingested(tmp_path: Path) -> None:
    path = write_session(tmp_path, session_records())
    write_session(tmp_path, session_records(), "duplicate")
    source = ClaudeCodeSource(tmp_path)
    assert source.sessions() == []
    assert source.snapshot_incomplete
    path.unlink()
    path.symlink_to(tmp_path / "encoded-workspace" / "duplicate.jsonl")
    assert len(source.sessions()) == 1
    assert source.snapshot_incomplete


def test_conflicting_identity_within_one_file(tmp_path: Path) -> None:
    records = session_records()
    records[1]["sessionId"] = "another-session"
    write_session(tmp_path, records)
    source = ClaudeCodeSource(tmp_path)
    assert source.sessions() == []
    assert source.warnings


def test_only_project_transcripts_are_read(tmp_path: Path) -> None:
    write_session(tmp_path, session_records())
    (tmp_path / "settings.json").write_text("not a transcript", encoding="utf-8")
    (tmp_path / "history.jsonl").write_text("not a transcript", encoding="utf-8")
    nested = tmp_path / "encoded-workspace" / "subagents"
    nested.mkdir()
    (nested / "agent.jsonl").write_text("not a transcript", encoding="utf-8")
    source = ClaudeCodeSource(tmp_path)
    assert len(source.sessions()) == 1
    assert source.warnings == []


def test_changed_file_is_not_committed(tmp_path: Path) -> None:
    path = write_session(tmp_path, session_records())
    source = ClaudeCodeSource(tmp_path)
    original_loads = json.loads

    def load_and_append(line: bytes) -> object:
        record = original_loads(line)
        if record.get("type") == "future-type":
            with path.open("a", encoding="utf-8") as stream:
                stream.write('{"type": "appended"}\n')
        return record

    with mock.patch.object(json, "loads", side_effect=load_and_append):
        assert source.sessions() == []
    assert source.snapshot_incomplete


def test_failed_directory_scan_keeps_committed_sessions(tmp_path: Path) -> None:
    collector = create_collector(tmp_path)
    write_session(collector.source.projects_dir, session_records())
    collector.sync()
    committed = collector.storage.revisions(normalize.SOURCE, "claude")
    with mock.patch.object(Path, "iterdir", side_effect=PermissionError("private")):
        assert collector.sync() == 0
    assert collector.storage.revisions(normalize.SOURCE, "claude") == committed
    assert collector.status["state"] == "partial"


def test_unknown_field_shapes_and_error_results_are_preserved(tmp_path: Path) -> None:
    records = session_records()
    records[2]["message"]["content"][0]["is_error"] = True
    records.append({"type": "assistant", "uuid": {"unknown": True}, "message": []})
    write_session(tmp_path, records)
    session = normalize.normalize_session(ClaudeCodeSource(tmp_path).sessions()[0])
    assert session["generation_count"] == 1
    assert session["timeline"][1]["tools"][0]["status"] == "error"
    assert session["timeline"][1]["tools"][0]["error"] == "synthetic tool output"
    assert json.loads(session["timeline_records"][-1]["data"]) == records[-1]


def test_updates_and_repeated_generation_do_not_double_count(tmp_path: Path) -> None:
    records = session_records()
    update = copy.deepcopy(records[1])
    update["message"]["usage"]["output_tokens"] = 9
    records.append(update)
    continuation = copy.deepcopy(update)
    continuation["uuid"] = "assistant-2"
    records.append(continuation)
    write_session(tmp_path, records)
    session = normalize.normalize_session(ClaudeCodeSource(tmp_path).sessions()[0])
    assert session["generation_count"] == 1
    assert session["usage"]["output_tokens"] == 9
    assert session["timeline"][1]["kind"] == "native-update"
    assert len(session["timeline_records"]) == len(records)


@pytest.mark.parametrize("value", [True, -1, "4", 1.5, None])
def test_invalid_usage_stays_unknown(value: object) -> None:
    assert (
        normalize.token_usage({"usage": {"input_tokens": value}})["input_tokens"]
        is None
    )


def test_missing_usage_and_tool_result_stay_unknown(tmp_path: Path) -> None:
    records = session_records()[:2]
    records[1]["message"].pop("usage")
    records[1]["isSidechain"] = True
    write_session(tmp_path, records)
    session = normalize.normalize_session(ClaudeCodeSource(tmp_path).sessions()[0])
    assert all(value is None for value in session["usage"].values())
    assert session["timeline"][1]["tools"][0]["status"] is None
    assert session["parent_id"] is None


def test_unavailable_source_and_read_error_have_private_diagnostics(
    tmp_path: Path,
) -> None:
    source = ClaudeCodeSource(tmp_path / "missing-private-directory")
    with pytest.raises(
        FileNotFoundError, match="^Claude Code projects directory is unavailable$"
    ):
        source.sessions()
    write_session(tmp_path, session_records())
    source = ClaudeCodeSource(tmp_path)
    with mock.patch.object(Path, "open", side_effect=PermissionError("private path")):
        assert source.sessions() == []
    assert source.snapshot_incomplete
    assert "private path" not in str(source.warnings)


def test_api_pagination_links_results_outside_page_and_searches_text(
    tmp_path: Path,
) -> None:
    collector = create_collector(tmp_path)
    write_session(collector.source.projects_dir, session_records())
    collector.sync()
    app = create_app()
    app.state.storage = collector.storage
    client = TestClient(app)
    base = "/api/sessions/synthetic-session"
    detail = client.get(base, params={"agent": "claude"})
    assert detail.status_code == 200
    response = client.get(
        base + "/timeline", params={"agent": "claude", "limit": 1, "offset": 1}
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["tools"][0]["output"] == "synthetic tool output"
    assert response.json()["items"][0]["sequence"] == 1
    latest = client.get(
        base + "/timeline", params={"agent": "claude", "limit": 2, "latest": True}
    ).json()
    assert latest["offset"] == 4
    assert latest["total"] == 5
    assert latest["items"][0]["kind"] == "future-type"
    search = client.get(base + "/search", params={"agent": "claude", "q": "prompt"})
    assert search.status_code == 200
    assert search.json()["total"] == 1
    hidden = client.get(base + "/search", params={"agent": "claude", "q": "thinking"})
    assert hidden.json()["total"] == 0
    totals = client.get("/api/usage", params={"agent": "claude"}).json()
    assert totals["source"] == normalize.SOURCE
    assert totals["session_count"] == 1
    assert totals["reported_cost"] is None
    assert AGENTS["claude"] is True
    assert ClaudeCodeAdapter().validated_versions == ()
