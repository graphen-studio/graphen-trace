"""Contract and collection tests for Pi session JSONL records."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from graphen_trace.adapters.pi import normalize
from graphen_trace.adapters.pi.collector import PiCollector
from graphen_trace.adapters.pi.source import PiSource
from graphen_trace.api import lifecycle
from graphen_trace.api.app import create_app
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


def _session_records() -> list[dict]:
    """Returns a synthetic Pi trace without personal content."""
    return [
        {
            "type": "session",
            "version": 3,
            "id": "pi-session-1",
            "timestamp": "2026-10-20T10:00:00.000Z",
            "cwd": "/example/project",
        },
        {
            "type": "message",
            "id": "user-1",
            "parentId": None,
            "timestamp": "2026-10-20T10:00:01.000Z",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "synthetic prompt"}],
                "timestamp": "2026-10-20T10:00:01.000Z",
            },
        },
        {
            "type": "message",
            "id": "assistant-1",
            "parentId": "user-1",
            "timestamp": "2026-10-20T10:00:02.000Z",
            "message": {
                "role": "assistant",
                "provider": "test-provider",
                "model": "test-model",
                "api": "test-api",
                "content": [
                    {"type": "thinking", "thinking": "synthetic reasoning"},
                    {
                        "type": "toolCall",
                        "id": "call-1",
                        "name": "bash",
                        "arguments": {"command": "true"},
                    },
                ],
                "usage": {
                    "input": 12,
                    "output": 7,
                    "reasoning": 2,
                    "cacheRead": 3,
                    "cacheWrite": 1,
                    "totalTokens": 19,
                    "cost": {"input": 0.1, "output": 0.2, "total": 0.3},
                },
                "stopReason": "toolUse",
                "timestamp": "2026-10-20T10:00:02.000Z",
                "durationMs": 1000,
            },
        },
        {
            "type": "message",
            "id": "tool-result-1",
            "parentId": "assistant-1",
            "timestamp": "2026-10-20T10:00:03.000Z",
            "message": {
                "role": "toolResult",
                "toolCallId": "call-1",
                "toolName": "bash",
                "content": [{"type": "text", "text": "synthetic result"}],
                "isError": False,
                "timestamp": "2026-10-20T10:00:03.000Z",
                "durationMs": 250,
            },
        },
        {
            "type": "message",
            "id": "assistant-2",
            "parentId": "tool-result-1",
            "timestamp": "2026-10-20T10:00:04.000Z",
            "message": {
                "role": "assistant",
                "provider": "test-provider",
                "model": "test-model",
                "content": [{"type": "text", "text": "synthetic answer"}],
                "usage": {
                    "input": 4,
                    "output": 5,
                    "cacheRead": 0,
                    "cacheWrite": 0,
                    "totalTokens": 9,
                    "cost": {"input": 0, "output": 0, "total": 0},
                },
                "stopReason": "stop",
                "timestamp": "2026-10-20T10:00:04.000Z",
            },
        },
        {
            "type": "context_edit",
            "id": "edit-1",
            "parentId": "assistant-2",
            "timestamp": "2026-10-20T10:00:05.000Z",
            "targetId": "old-message",
            "replacement": [],
        },
    ]


def _write_session(directory: Path, records: list[dict]) -> Path:
    """Writes synthetic records as one Pi session JSONL file."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "session.jsonl"
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return path


def test_normalizer_maps_usage_tools_and_native_records() -> None:
    """Maps known Pi concepts and preserves extra native records."""
    records = _session_records()
    timeline = normalize.normalize_timeline(records)
    assistant = next(item for item in timeline if item["id"] == "assistant-1")
    user = next(item for item in timeline if item["id"] == "user-1")
    context_edit = next(item for item in timeline if item["kind"] == "context_edit")

    assert user["raw_data"]["content"][0]["text"] == "synthetic prompt"
    assert assistant["raw_data"]["content"][-1]["type"] == "toolCall"
    assert assistant["model"] == {
        "id": "test-model",
        "providerID": "test-provider",
        "api": "test-api",
    }
    assert assistant["usage"] == {
        "input_tokens": 12,
        "output_tokens": 7,
        "reasoning_tokens": 2,
        "cache_read_tokens": 3,
        "cache_write_tokens": 1,
    }
    assert assistant["reported_cost"] == 0.3
    assert assistant["tools"][0]["id"] == "call-1"
    assert assistant["tools"][0]["status"] == "completed"
    assert assistant["tools"][0]["duration_ms"] == 250
    assert context_edit["source_record"]["replacement"] == []


def test_collector_imports_and_updates_pi_session(tmp_path: Path) -> None:
    """Imports Pi sessions idempotently and refreshes changed JSONL files."""
    sessions_dir = tmp_path / "sessions"
    path = _write_session(sessions_dir, _session_records())
    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    collector = PiCollector(PiSource(sessions_dir, "1.3.0"), storage)

    assert collector.sync() == 1
    assert collector.sync() == 0
    session = storage.session("pi-session-1", "pi:session-jsonl:v1", "pi")
    assert session["agent"] == "pi"
    assert session["version"] == "1.3.0"
    assert session["updated_at"] == "2026-10-20T10:00:05+00:00"
    assert session["generation_count"] == 2
    assert session["usage"]["input_tokens"] == 16
    assert session["reported_cost"] == 0.3

    records = _session_records()
    records.append(
        {
            "type": "model_change",
            "id": "model-change-1",
            "parentId": "assistant-2",
            "timestamp": "2026-10-20T10:00:06.000Z",
            "provider": "other-provider",
            "modelId": "other-model",
        }
    )
    _write_session(sessions_dir, records)
    assert collector.sync() == 1
    assert (
        storage.session("pi-session-1", "pi:session-jsonl:v1", "pi")["message_count"]
        == 6
    )

    path.unlink()
    assert collector.sync() == 0
    assert storage.session("pi-session-1", "pi:session-jsonl:v1", "pi") is None


def test_sessions_are_ordered_by_latest_pi_record(tmp_path: Path) -> None:
    """Lists the most recently active Pi session before older sessions."""
    sessions_dir = tmp_path / "sessions"
    older = _session_records()
    newer = _session_records()
    newer[0]["id"] = "pi-session-newer"
    newer[-1]["timestamp"] = "2026-10-22T12:00:00.000Z"
    _write_session(sessions_dir / "older", older)
    _write_session(sessions_dir / "newer", newer)

    storage = Storage(tmp_path / "graphen.db")
    storage.initialize()
    PiCollector(PiSource(sessions_dir, "1.3.0"), storage).sync()

    sessions = storage.sessions(10, 0, "pi")
    assert [session["id"] for session in sessions] == [
        "pi-session-newer",
        "pi-session-1",
    ]


def test_pi_collection_is_available_through_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Discovers Pi and serves its normalized session timeline via the API."""
    sessions_dir = tmp_path / "sessions"
    _write_session(sessions_dir, _session_records())
    monkeypatch.setattr(
        lifecycle,
        "settings",
        replace(
            lifecycle.settings,
            database_path=tmp_path / "trace.db",
            opencode_database=tmp_path / "missing-opencode.db",
            pi_sessions_dir=sessions_dir,
            opencode_url=None,
            opencode_service_file=tmp_path / "missing-service.json",
        ),
    )
    monkeypatch.setattr(
        lifecycle,
        "discover_agents",
        lambda: [AgentInstallation("pi", "/example/pi", "1.3.0", True)],
    )

    with TestClient(create_app()) as client:
        agents = client.get("/api/agents").json()["items"]
        assert agents[0]["name"] == "pi"
        assert agents[0]["adapter"] is True
        response = client.post("/api/collection", json={"agent": "pi"})
        assert response.status_code == 200
        client.portal.call(asyncio.sleep, 0.05)

        sessions = client.get("/api/sessions?agent=pi").json()["items"]
        assert sessions[0]["id"] == "pi-session-1"
        assert sessions[0]["usage"]["input_tokens"] == 16
        details = client.get("/api/sessions/pi-session-1?agent=pi")
        assert details.status_code == 200
        assert details.json()["agent"] == "pi"
        timeline = client.get("/api/sessions/pi-session-1/timeline?agent=pi").json()[
            "items"
        ]
        assert any(item["kind"] == "context_edit" for item in timeline)
        assert (
            next(item for item in timeline if item["kind"] == "user")["raw_data"][
                "content"
            ][0]["text"]
            == "synthetic prompt"
        )
        assert (
            next(item for item in timeline if item["id"] == "assistant-2")["raw_data"][
                "content"
            ][0]["text"]
            == "synthetic answer"
        )
        assert (
            next(item for item in timeline if item["id"] == "assistant-1")["tools"][0][
                "id"
            ]
            == "call-1"
        )
        usage = client.get("/api/usage?agent=pi").json()
        assert usage["agent"] == "pi"
        assert usage["source"] == "pi:session-jsonl:v1"
        live = client.get("/api/collection/live?agent=pi").json()
        assert live["state"] == "unavailable"
        assert live["possible_gap"] is False
