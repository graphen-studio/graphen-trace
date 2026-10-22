"""Tests for initial dashboard API routes."""

import json
from dataclasses import replace
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from graphen_trace.adapters.opencode.events import decode_frame
from graphen_trace.api import lifecycle
from graphen_trace.api.app import create_app
from graphen_trace.api.routes import frontend
from graphen_trace.services.discovery import AgentInstallation


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Creates a client for the Graphen Trace API."""
    monkeypatch.setattr(
        lifecycle,
        "settings",
        replace(
            lifecycle.settings,
            database_path=tmp_path / "trace.db",
            opencode_database=tmp_path / "opencode.db",
            opencode_service_file=tmp_path / "missing-service.json",
        ),
    )
    monkeypatch.setattr(lifecycle, "discover_agents", lambda: [])
    with TestClient(create_app()) as api_client:
        yield api_client


def test_health_route_is_served(client: TestClient) -> None:
    """Health route returns service status."""
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/not-implemented").status_code == 404


def test_frontend_is_served(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SPA fallback returns the compiled frontend when present."""
    (tmp_path / "index.html").write_text("<html>Graphen Trace</html>", encoding="utf-8")
    monkeypatch.setattr(frontend, "WEB_ROOT", tmp_path)
    assert client.get("/").text == "<html>Graphen Trace</html>"
    assert client.get("/dashboard/session").status_code == 200
    assert client.get("/v1/models").status_code == 404


def test_proxy_route_is_only_enabled_explicitly() -> None:
    """The proxy feature remains disabled unless explicitly requested."""
    passive_app = create_app()
    proxy_app = create_app(proxy_enabled=True)

    assert not passive_app.state.proxy_enabled
    assert proxy_app.state.proxy_enabled


def test_sessions_and_collection_status(client: TestClient) -> None:
    """Dashboard routes use initialized Graphen storage and expose coverage."""
    assert client.get("/api/sessions").json() == {"items": []}
    assert client.get("/api/sessions?limit=201").status_code == 422
    assert client.get("/api/collection").json()["state"] == "not_started"
    assert client.get("/api/agents").json() == {"items": []}
    consumption = client.get("/api/usage").json()
    assert consumption["session_count"] == 0
    assert consumption["usage"]["input_tokens"] is None


def test_collection_requires_an_installed_supported_agent(client: TestClient) -> None:
    """Unsupported agents are discoverable but cannot start a collector."""
    client.app.state.collection_manager.agents = [
        AgentInstallation("claude", "/example/claude", "1.0", False)
    ]
    assert client.get("/api/agents").json() == {
        "items": [
            {
                "name": "claude",
                "path": "/example/claude",
                "version": "1.0",
                "adapter": False,
            }
        ]
    }
    assert client.post("/api/collection", json={"agent": "claude"}).status_code == 409
    assert client.post("/api/collection", json={"agent": "missing"}).status_code == 404
    assert client.post("/api/collection", json={}).status_code == 422


def test_collection_starts_only_after_explicit_selection(client: TestClient) -> None:
    """Selecting the supported installation starts passive collection."""
    client.app.state.collection_manager.agents = [
        AgentInstallation("opencode", "/example/opencode", "2.0.32", True)
    ]
    response = client.post("/api/collection", json={"agent": "opencode"})
    assert response.status_code == 200
    assert response.json()["agent"] == "opencode"
    assert response.json()["state"] == "starting"


def test_session_details_and_paginated_timeline(client: TestClient) -> None:
    """Session endpoints return validated contracts and distinguish missing IDs."""
    assert client.get("/api/sessions/missing").status_code == 404
    assert client.get("/api/sessions/missing/timeline").status_code == 404
    record = {
        "id": "s1",
        "agent": "opencode",
        "title": "Example",
        "revision": "test",
        "source": "opencode:sqlite:v2",
        "message_count": 2,
        "usage": {},
        "timeline_records": [
            {
                "id": f"m{index}",
                "session_id": "s1",
                "type": "user",
                "seq": index,
                "time_created": index + 100,
                "time_updated": index + 100,
                "data": json.dumps({"text": "complete prompt", "extra": [1, 2, 3]}),
            }
            for index in range(2)
        ],
    }
    client.app.state.storage.apply("opencode:sqlite:v2", [record], {"s1"})
    assert client.get("/api/sessions/s1").json()["title"] == "Example"
    response = client.get("/api/sessions/s1/timeline?limit=1&offset=1").json()
    assert response["total"] == 2
    assert response["items"][0]["id"] == "m1"
    assert response["items"][0]["raw_data"] == {
        "text": "complete prompt",
        "extra": [1, 2, 3],
    }
    assert client.get("/api/sessions/s1/timeline?limit=201").status_code == 422
    assert client.get("/api/sessions/s1/timeline?offset=-1").status_code == 422


def test_usage_aggregates_sessions_beyond_the_default_page(client: TestClient) -> None:
    """Global consumption is not limited by the dashboard session list page."""
    records = [
        {
            "id": f"s{index}",
            "agent": "opencode",
            "source": "opencode:sqlite:v2",
            "revision": "test",
            "message_count": 1,
            "generation_count": 1,
            "usage": {"input_tokens": 10, "cache_read_tokens": 5},
            "usage_incomplete": ["output_tokens"],
            "reported_cost": 0.5,
        }
        for index in range(51)
    ]
    client.app.state.storage.apply(
        "opencode:sqlite:v2",
        records,
        {record["id"] for record in records},
    )
    assert len(client.get("/api/sessions").json()["items"]) == 50
    consumption = client.get("/api/usage").json()
    assert consumption["session_count"] == 51
    assert consumption["usage"]["input_tokens"] == 510
    assert consumption["usage"]["cache_read_tokens"] == 255
    assert consumption["usage"]["output_tokens"] is None
    assert consumption["usage_incomplete"] == ["output_tokens"]
    assert consumption["reported_cost"] == 25.5


def _store_search_session(client: TestClient) -> None:
    messages = [
        {
            "id": f"m{index}",
            "type": "user" if index % 2 == 0 else "assistant",
            "seq": index,
            "data": json.dumps({"text": f"Message {index}"}),
        }
        for index in range(105)
    ]
    messages[0]["data"] = json.dumps({"text": "Search CACHE here"})
    messages[101]["data"] = json.dumps(
        {
            "content": [
                {"type": "text", "text": "Another cache match: 100% [a.*] ação"},
                {"type": "tool", "text": "tool-secret"},
                {"type": "reasoning", "text": "reasoning-secret"},
            ],
            "metadata": "metadata-secret",
        }
    )
    messages[102]["data"] = "malformed JSON"
    messages[103]["data"] = json.dumps({"content": [None, "unknown", {}]})
    record = {
        "id": "search-session",
        "agent": "opencode",
        "source": "opencode:sqlite:v2",
        "revision": "test",
        "message_count": len(messages),
        "usage": {},
        "timeline_records": messages,
    }
    client.app.state.storage.apply("opencode:sqlite:v2", [record], {record["id"]})


def test_latest_timeline_page_preserves_chronological_order(client: TestClient) -> None:
    """Latest resolves a stable page offset without reversing its records."""
    _store_search_session(client)
    response = client.get(
        "/api/sessions/search-session/timeline?latest=true&limit=50"
    ).json()
    assert response["offset"] == 100
    assert response["total"] == 105
    assert [item["id"] for item in response["items"]] == [
        f"m{index}" for index in range(100, 105)
    ]
    first = client.get("/api/sessions/search-session/timeline?offset=0").json()
    assert first["offset"] == 0
    assert first["items"][0]["id"] == "m0"


def test_search_covers_entire_session_and_returns_timeline_positions(
    client: TestClient,
) -> None:
    """Search results span pages and point to the original chronological position."""
    _store_search_session(client)
    path = "/api/sessions/search-session/search"
    response = client.get(path, params={"q": "cache"}).json()
    assert response["total"] == 2
    assert [item["timeline_offset"] for item in response["items"]] == [0, 101]
    assert [item["kind"] for item in response["items"]] == ["user", "assistant"]
    second = client.get(path, params={"q": "cache", "limit": 1, "offset": 1}).json()
    assert second["total"] == 2
    assert second["items"][0]["message_id"] == "m101"
    assert "cache" in second["items"][0]["excerpt"]
    for query in ("tool-secret", "reasoning-secret", "metadata-secret", "m101"):
        assert client.get(path, params={"q": query}).json()["total"] == 0
    for query in ("100%", "[a.*]", "AÇÃO"):
        assert client.get(path, params={"q": query}).json()["total"] == 1
    assert client.get(path, params={"q": "cache", "agent": "pi"}).status_code == 404
    assert client.get(path, params={"q": " "}).status_code == 422
    assert client.get(path, params={"q": "x" * 201}).status_code == 422
    assert client.get(path, params={"q": "cache", "offset": -1}).status_code == 422
    assert (
        client.get("/api/sessions/missing/search", params={"q": "cache"}).status_code
        == 404
    )


def test_event_queries_are_independent_from_session_projection(
    client: TestClient,
) -> None:
    """A permission event is queryable before its session appears in SQLite."""
    payload = {
        "id": "evt_permission",
        "type": "permission.replied",
        "created": 1000,
        "data": {"sessionID": "new-session", "requestID": "r1", "reply": "reject"},
    }
    event = decode_frame({"data": json.dumps(payload), "event": "message", "id": None})
    client.app.state.storage.save_event("instance", event)
    page = client.get("/api/events?session_id=new-session").json()
    assert page["total"] == 1
    assert page["items"][0]["raw_data"] == payload
    assert client.get("/api/events?session_id=other").json()["total"] == 0
    assert client.get("/api/events?limit=201").status_code == 422
    assert client.get("/api/collection/live").json()["possible_gap"]


def test_agent_filter_prevents_native_id_collisions(client: TestClient) -> None:
    """The same native session ID is isolated by the persisted agent flag."""
    records = [
        {
            "id": "same-native-id",
            "agent": agent,
            "title": agent,
            "source": f"{agent}:sqlite:v1",
            "revision": "r1",
            "message_count": 0,
            "usage": {},
        }
        for agent in ("opencode", "pi")
    ]
    client.app.state.storage.apply(
        "opencode:sqlite:v1",
        [records[0]],
        {"same-native-id"},
    )
    client.app.state.storage.apply(
        "pi:sqlite:v1",
        [records[1]],
        {"same-native-id"},
        agent="pi",
    )
    assert (
        client.get("/api/sessions?agent=opencode").json()["items"][0]["title"]
        == "opencode"
    )
    assert client.get("/api/sessions?agent=pi").json()["items"][0]["title"] == "pi"
    assert client.get("/api/sessions?agent=").status_code == 422
    assert client.get("/api/usage?agent=pi").json()["session_count"] == 1
    payload = {
        "id": "same-native-event",
        "type": "session.idle",
        "created": 1,
        "data": {"sessionID": "same-native-id"},
    }
    event = decode_frame({"data": json.dumps(payload), "event": "message", "id": None})
    client.app.state.storage.save_event("opencode-instance", event)
    client.app.state.storage.save_event(
        "pi-instance",
        event,
        source="pi:sse:v1",
        agent="pi",
    )
    assert client.get("/api/events?agent=opencode").json()["total"] == 1
    assert client.get("/api/events?agent=pi&source=pi:sse:v1").json()["total"] == 1
