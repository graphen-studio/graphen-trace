"""Synthetic contract and collection tests for the Kiro CLI adapter."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from graphen_trace.adapters.kiro import normalize
from graphen_trace.adapters.kiro.collector import KiroCollector
from graphen_trace.adapters.kiro.source import KiroSource
from graphen_trace.api import lifecycle
from graphen_trace.api.app import create_app
from graphen_trace.services import discovery
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


def _records() -> list[dict]:
    """Returns a synthetic CLI transcript with model and token observations."""
    return [
        {
            "version": 1,
            "kind": "Prompt",
            "data": {"message_id": "prompt-1", "content": "synthetic prompt"},
        },
        {
            "version": 1,
            "kind": "AssistantMessage",
            "data": {
                "message_id": "assistant-1",
                "turnId": "turn-1",
                "content": [{"type": "text", "text": "synthetic answer"}],
                "modelId": "synthetic-model",
                "inputTokenCount": 42,
                "outputTokenCount": 12,
                "reasoningTokenCount": 3,
            },
        },
        {
            "version": 1,
            "kind": "tool_call",
            "data": {
                "toolCallId": "tool-1",
                "toolName": "synthetic-tool",
                "args": {"safe": True},
                "status": "completed",
            },
        },
        {
            "version": 1,
            "kind": "tool_result",
            "data": {
                "toolCallId": "tool-1",
                "content": "synthetic result",
                "success": True,
            },
        },
        {"version": 1, "kind": "future_event", "data": {"safe": "preserved"}},
    ]


def _write_session(directory: Path, records: list[dict] | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    metadata_path = directory / "session-1.json"
    metadata_path.write_text(
        json.dumps(
            {
                "session_id": "session-1",
                "cwd": "/synthetic/project",
                "title": "Synthetic session",
                "created_at": "2026-10-26T10:00:00Z",
                "updated_at": "2026-10-26T10:02:00Z",
                "session_state": {
                    "conversation_metadata": {
                        "user_turn_metadatas": [
                            {
                                "turnId": "turn-1",
                                "modelId": "synthetic-model",
                                "inputTokenCount": 42,
                                "outputTokenCount": 12,
                                "metering_usage": {"unit": "credit", "value": 0.4},
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    transcript = records if records is not None else _records()
    metadata_path.with_suffix(".jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in transcript),
        encoding="utf-8",
    )
    return metadata_path


def _write_workspace_session(directory: Path) -> Path:
    """Writes synthetic events using the Kiro workspace JSONL dialect."""
    session_dir = directory / "workspace-hash" / "sess_workspace-1"
    session_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = session_dir / "session.json"
    metadata_path.write_text(
        json.dumps(
            {
                "id": "workspace-1",
                "title": "Synthetic workspace session",
                "createdAt": "2026-10-26T10:00:00Z",
                "lastModifiedAt": "2026-10-26T10:02:00Z",
                "modelId": "synthetic-workspace-model",
                "schemaVersion": "1",
                "dataModelVersion": 1,
                "workspacePaths": ["/synthetic/workspace"],
            }
        ),
        encoding="utf-8",
    )
    events = [
        {
            "id": "workspace-user-1",
            "timestamp": "2026-10-26T10:00:01Z",
            "payload": {"type": "user", "content": "synthetic workspace prompt"},
        },
        {
            "id": "workspace-assistant-1",
            "timestamp": "2026-10-26T10:00:02Z",
            "payload": {
                "type": "assistant",
                "turnId": "workspace-turn-1",
                "content": [{"type": "text", "text": "synthetic answer"}],
                "reasoningModelId": "synthetic-reasoning-model",
            },
        },
        {
            "id": "workspace-usage-1",
            "timestamp": "2026-10-26T10:00:03Z",
            "payload": {
                "type": "usage_summary",
                "promptTurnSummaries": [{"inputTokenCount": 31, "outputTokenCount": 8}],
            },
        },
        {
            "id": "workspace-tool-1",
            "timestamp": "2026-10-26T10:00:04Z",
            "payload": {
                "type": "tool_call",
                "toolCallId": "workspace-call-1",
                "toolName": "synthetic-tool",
                "args": {"safe": True},
            },
        },
        {
            "id": "workspace-result-1",
            "timestamp": "2026-10-26T10:00:05Z",
            "payload": {
                "type": "tool_result",
                "toolCallId": "workspace-call-1",
                "content": "synthetic result",
                "success": True,
            },
        },
    ]
    metadata_path.with_name("messages.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    return metadata_path


def _write_workspace_subexecution(directory: Path) -> tuple[Path, Path]:
    """Writes a workspace session and a linked child transcript."""
    metadata_path = _write_workspace_session(directory)
    events = [
        {
            "id": "workspace-user-1",
            "timestamp": "2026-10-26T10:00:00Z",
            "payload": {"type": "user", "content": "synthetic prompt"},
        },
        {
            "id": "workspace-turn-start-1",
            "timestamp": "2026-10-26T10:00:01Z",
            "payload": {
                "type": "turn_start",
                "executionId": "parent-execution-1",
            },
        },
        {
            "id": "workspace-subagent-start-1",
            "timestamp": "2026-10-26T10:00:02Z",
            "payload": {
                "type": "sub_agent_start",
                "parentExecutionId": "parent-execution-1",
                "subSessionId": "sub-execution-1",
            },
        },
        {
            "id": "workspace-subagent-complete-1",
            "timestamp": "2026-10-26T10:00:08Z",
            "payload": {
                "type": "sub_agent_complete",
                "parentExecutionId": "parent-execution-1",
                "subSessionId": "sub-execution-1",
            },
        },
        {
            "id": "workspace-turn-end-1",
            "timestamp": "2026-10-26T10:00:09Z",
            "payload": {"type": "turn_end", "executionId": "parent-execution-1"},
        },
    ]
    metadata_path.with_name("messages.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    subexecution_path = (
        metadata_path.parent / "sub-executions" / "sub-execution-1.jsonl"
    )
    subexecution_path.parent.mkdir(parents=True)
    child_events = [
        {
            "id": "child-assistant-1",
            "timestamp": "2026-10-26T10:00:03Z",
            "payload": {
                "type": "assistant",
                "subExecutionId": "sub-execution-1",
                "content": [{"type": "text", "text": "synthetic child answer"}],
            },
        },
        {
            "id": "child-tool-call-1",
            "timestamp": "2026-10-26T10:00:04Z",
            "payload": {
                "type": "tool_call",
                "subExecutionId": "sub-execution-1",
                "toolCallId": "child-call-1",
                "toolName": "synthetic-child-tool",
                "args": {"safe": True},
            },
        },
        {
            "id": "child-tool-result-1",
            "timestamp": "2026-10-26T10:00:05Z",
            "payload": {
                "type": "tool_result",
                "subExecutionId": "sub-execution-1",
                "toolCallId": "child-call-1",
                "content": "synthetic child result",
                "success": True,
            },
        },
    ]
    subexecution_path.write_text(
        "".join(json.dumps(event) + "\n" for event in child_events),
        encoding="utf-8",
    )
    return metadata_path, subexecution_path


def test_normalizer_preserves_model_tokens_and_native_credit_data() -> None:
    """Projects explicit model/token fields and keeps credit units unconverted."""
    metadata = {
        "session_state": {
            "conversation_metadata": {
                "user_turn_metadatas": [
                    {
                        "turnId": "turn-1",
                        "modelId": "synthetic-model",
                        "inputTokenCount": 42,
                        "metering_usage": {"unit": "credit", "value": 0.4},
                    }
                ]
            }
        }
    }
    timeline = normalize.normalize_timeline(_records(), metadata)
    assistant = next(item for item in timeline if item["kind"] == "assistant")
    unknown = next(item for item in timeline if item["kind"] == "future_event")

    assert assistant["model"]["id"] == "synthetic-model"
    assert assistant["usage"] == {
        "input_tokens": 42,
        "output_tokens": 12,
        "reasoning_tokens": 3,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
    }
    assert assistant["reported_cost"] is None
    assert unknown["raw_data"] == {"safe": "preserved"}
    assert (
        next(item for item in timeline if item["kind"] == "tool_call")["tools"][0][
            "output"
        ]
        == "synthetic result"
    )


def test_zero_token_counters_are_preserved_not_reinterpreted() -> None:
    """Keeps source-reported zero distinct from missing counters."""
    timeline = normalize.normalize_timeline(
        [
            {
                "kind": "AssistantMessage",
                "data": {"message_id": "assistant-zero", "inputTokenCount": 0},
            }
        ],
        {},
    )
    assert timeline[0]["usage"]["input_tokens"] == 0
    assert timeline[0]["usage"]["output_tokens"] is None


def test_token_totals_fall_back_to_turn_metadata_when_transcript_has_none() -> None:
    """Uses turn counters to expose consumption absent from assistant records."""
    metadata = {
        "session_id": "session-1",
        "session_state": {
            "conversation_metadata": {
                "user_turn_metadatas": [
                    {"inputTokenCount": 20, "outputTokenCount": 9},
                    {"inputTokenCount": 12, "outputTokenCount": 4},
                ]
            }
        },
    }
    session = {
        "id": "cli:session-1",
        "metadata": metadata,
        "records": [],
        "source": normalize.SOURCE,
        "agent_version": "2.34.1",
        "revision": "fixture",
    }

    normalized = normalize.normalize_session(session)

    assert normalized["usage"]["input_tokens"] == 32
    assert normalized["usage"]["output_tokens"] == 13


def test_discovery_looks_up_the_kiro_cli_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uses Kiro's executable name while keeping its agent identifier stable."""
    looked_up = []
    monkeypatch.setattr(
        discovery.shutil,
        "which",
        lambda name: (
            looked_up.append(name) or "/usr/local/bin/kiro-cli"
            if name == "kiro-cli"
            else None
        ),
    )
    monkeypatch.setattr(discovery, "_read_version", lambda _: "kiro-cli 2.34.1")

    agents = discovery.discover_agents()

    kiro = next(agent for agent in agents if agent.name == "kiro")
    assert "kiro-cli" in looked_up
    assert kiro.adapter is True


def test_collector_imports_updates_and_removes_sessions(tmp_path: Path) -> None:
    """Imports Kiro CLI sessions idempotently and refreshes file changes."""
    sessions_dir = tmp_path / "sessions"
    metadata_path = _write_session(sessions_dir)
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    collector = KiroCollector(KiroSource(sessions_dir, "2.34.1"), storage)

    assert collector.sync() == 1
    assert collector.sync() == 0
    session = storage.session("cli:session-1", normalize.SOURCE, "kiro")
    assert session["model"]["id"] == "synthetic-model"
    assert session["usage"]["input_tokens"] == 42
    assert session["usage"]["output_tokens"] == 12
    assert session["reported_cost"] is None

    records = _records()
    records.append({"version": 1, "kind": "future_event", "data": {"new": True}})
    metadata_path.with_suffix(".jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    assert collector.sync() == 1
    rows = storage.timeline("cli:session-1", (100, 0), normalize.SOURCE, "kiro")[
        "items"
    ]
    timeline = normalize.normalize_timeline_rows(rows)
    assert any(item["kind"] == "future_event" for item in timeline)
    assert (
        next(item for item in timeline if item["kind"] == "assistant")["usage"][
            "input_tokens"
        ]
        == 42
    )

    metadata_path.unlink()
    metadata_path.with_suffix(".jsonl").unlink()
    assert collector.sync() == 0
    assert storage.session("cli:session-1", normalize.SOURCE, "kiro") is None


def test_workspace_layout_is_collected_as_a_distinct_source(tmp_path: Path) -> None:
    """Captures workspace records while retaining their separate provenance."""
    sessions_dir = tmp_path / "cli"
    workspace_dir = tmp_path / "sessions"
    _write_workspace_session(workspace_dir)
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    collector = KiroCollector(
        KiroSource(sessions_dir, "2.35.1", workspace_dir), storage
    )

    assert collector.sync() == 1
    session = storage.session(
        "workspace:workspace-1", normalize.WORKSPACE_SOURCE, "kiro"
    )
    assert session["source"] == normalize.WORKSPACE_SOURCE
    assert session["directory"] == "/synthetic/workspace"
    assert session["model"]["id"] == "synthetic-workspace-model"
    assert session["usage"]["input_tokens"] == 31
    rows = storage.timeline(
        session["id"], (100, 0), normalize.WORKSPACE_SOURCE, "kiro"
    )["items"]
    timeline = normalize.normalize_timeline_rows(rows)
    assistant = next(item for item in timeline if item["kind"] == "assistant")
    assert assistant["model"]["reasoning_model_id"] == "synthetic-reasoning-model"
    tool_call = next(item for item in timeline if item["kind"] == "tool_call")
    assert tool_call["tools"][0]["output"] == "synthetic result"


def test_v3_subexecution_is_imported_and_linked_to_parent_turn(
    tmp_path: Path,
) -> None:
    """Imports child transcript events and preserves parent/turn provenance."""
    sessions_dir = tmp_path / "sessions"
    _, subexecution_path = _write_workspace_subexecution(sessions_dir)
    source = KiroSource(tmp_path / "cli", "kiro-cli 2.37.0", sessions_dir)
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    collector = KiroCollector(source, storage)

    assert collector.sync() == 1
    assert collector.sync() == 0
    assert not any("not a validated version" in warning for warning in source.warnings)

    session = storage.session(
        "workspace:workspace-1", normalize.WORKSPACE_SOURCE, "kiro"
    )
    assert session["message_count"] == 8
    rows = storage.timeline(
        "workspace:workspace-1", (100, 0), normalize.WORKSPACE_SOURCE, "kiro"
    )["items"]
    timeline = normalize.normalize_timeline_rows(rows)
    child_assistant = next(
        item
        for item in timeline
        if item["kind"] == "assistant" and item["id"].startswith("subexecution:")
    )
    assert child_assistant["interaction_id"] == "workspace-user-1"
    assert child_assistant["interaction_source"] == "parent_execution"
    assert (
        child_assistant["source_record"]["_graphen_subexecution"]["parent_execution_id"]
        == "parent-execution-1"
    )

    child_tool = next(
        item
        for item in timeline
        if item["kind"] == "tool_call" and item["id"].startswith("subexecution:")
    )
    assert child_tool["tools"][0]["id"] == "sub-execution-1:child-call-1"
    assert child_tool["tools"][0]["output"] == "synthetic child result"
    assert [item["kind"] for item in timeline].index("assistant") < [
        item["kind"] for item in timeline
    ].index("sub_agent_complete")

    subexecution_path.write_text(
        subexecution_path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "id": "child-future-event-1",
                "timestamp": "2026-10-26T10:00:06Z",
                "payload": {
                    "type": "future_child_event",
                    "subExecutionId": "sub-execution-1",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert collector.sync() == 1

    subexecution_path.write_text(
        subexecution_path.read_text(encoding="utf-8") + "{\n", encoding="utf-8"
    )
    assert collector.sync() == 0
    assert collector.status["state"] == "partial"
    rows = storage.timeline(
        "workspace:workspace-1", (100, 0), normalize.WORKSPACE_SOURCE, "kiro"
    )["items"]
    assert any(
        item["kind"] == "future_child_event"
        for item in normalize.normalize_timeline_rows(rows)
    )


def test_unknown_kiro_version_attempts_structural_collection_with_warning(
    tmp_path: Path,
) -> None:
    """Does not block a future Kiro version when known file contracts match."""
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir)
    source = KiroSource(sessions_dir, "kiro-cli 99.0.0")

    sessions = source.sessions()

    assert len(sessions) == 1
    assert any("not a validated version" in warning for warning in source.warnings)


def test_invalid_partial_jsonl_line_does_not_discard_valid_records(
    tmp_path: Path,
) -> None:
    """Skips a partial line while retaining the other native records."""
    metadata_path = _write_session(tmp_path / "sessions")
    transcript = metadata_path.with_suffix(".jsonl")
    transcript.write_text(
        json.dumps(_records()[0]) + "\n{" + "\n" + json.dumps(_records()[1]) + "\n",
        encoding="utf-8",
    )
    source = KiroSource(metadata_path.parent, "2.34.1")

    session = source.sessions()[0]
    assert len(session["records"]) == 2
    assert source.warnings


def test_kiro_collection_is_available_through_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovers Kiro and serves its normalized timeline and usage through API."""
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir)
    _write_workspace_session(sessions_dir)
    monkeypatch.setattr(
        lifecycle,
        "settings",
        replace(
            lifecycle.settings,
            database_path=tmp_path / "trace.db",
            opencode_database=tmp_path / "missing-opencode.db",
            pi_sessions_dir=tmp_path / "missing-pi",
            kiro_sessions_dir=sessions_dir,
            kiro_workspace_sessions_dir=sessions_dir,
            opencode_url=None,
            opencode_service_file=tmp_path / "missing-service.json",
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "discover_agents",
        lambda: [AgentInstallation("kiro", "/example/kiro", "2.34.1", True)],
    )

    with TestClient(create_app()) as client:
        assert client.get("/api/agents").json()["items"][0]["adapter"] is True
        response = client.post("/api/collection", json={"agent": "kiro"})
        assert response.status_code == 200
        client.portal.call(asyncio.sleep, 0.05)

        session = client.get("/api/sessions/cli:session-1?agent=kiro").json()
        assert session["model"]["id"] == "synthetic-model"
        assert session["usage"]["input_tokens"] == 42
        timeline = client.get("/api/sessions/cli:session-1/timeline?agent=kiro").json()[
            "items"
        ]
        assistant = next(item for item in timeline if item["kind"] == "assistant")
        assert assistant["usage"]["output_tokens"] == 12
        assert assistant["model"]["id"] == "synthetic-model"
        search = client.get(
            "/api/sessions/cli:session-1/search?q=synthetic&agent=kiro"
        ).json()
        assert search["total"] == 2
        usage = client.get("/api/usage?agent=kiro").json()
        assert usage["source"] == "kiro:local-session-files:v1"
        assert usage["usage"]["input_tokens"] == 73
        assert usage["session_count"] == 2
        workspace = client.get("/api/sessions/workspace:workspace-1?agent=kiro").json()
        assert workspace["source"] == normalize.WORKSPACE_SOURCE
        assert "ambiguous" in workspace["normalization_warnings"][0]
        workspace_timeline = client.get(
            "/api/sessions/workspace:workspace-1/timeline?agent=kiro"
        ).json()["items"]
        assert any(item["kind"] == "tool_call" for item in workspace_timeline)
        live = client.get("/api/collection/live?agent=kiro").json()
        assert live["state"] == "unavailable"
        assert live["possible_gap"] is False
