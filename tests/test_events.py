"""Synthetic V2 event and local-service contract tests."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from graphen_trace.adapters.opencode.connection import discover_connection
from graphen_trace.adapters.opencode.events import (
    check_response,
    decode_frame,
    read_frames,
)
from graphen_trace.config.settings import Settings
from graphen_trace.services.live_collector import LiveCollector
from graphen_trace.services.storage import Storage


def native_event(event_id: str = "evt_example") -> dict:
    """Returns a synthetic native envelope with no real credentials or user data."""
    return {
        "id": event_id,
        "type": "session.execution.interrupted",
        "created": 1000,
        "data": {"sessionID": "s1", "reason": "user"},
        "durable": {"aggregateID": "s1", "seq": 3, "version": 1},
    }


def test_sse_parser_preserves_multiline_json_and_ignores_comments() -> None:
    """SSE framing is independent from network chunk boundaries and heartbeats."""

    async def collect():
        async def lines():
            for line in [
                ": heartbeat",
                "",
                "id: transport-id",
                "event: message",
                'data: {"id":"evt_one",',
                'data: "type":"session.execution.interrupted", '
                '"data":{"sessionID":"s1"}}',
                "",
            ]:
                yield line

        return [event async for event in read_frames(lines())]

    events = asyncio.run(collect())
    assert len(events) == 1
    assert events[0]["session_id"] == "s1"
    assert events[0]["frame"]["id"] == "transport-id"
    assert events[0]["kind"] == "session.execution.interrupted"


def test_failure_and_incomplete_frames_are_not_reported_as_success() -> None:
    """Overflow/failure frames and interrupted JSON frames indicate a gap."""
    with pytest.raises(ValueError):
        decode_frame(
            {"data": "[]", "event": "effect/http-api/stream/failure", "id": None}
        )

    async def collect():
        async def lines():
            yield 'data: {"id": "incomplete"'

        return [event async for event in read_frames(lines())]

    with pytest.raises(ValueError, match="incomplete frame"):
        asyncio.run(collect())


def test_unknown_event_shapes_are_preserved_with_warnings() -> None:
    """Unrecognized envelopes are captured without inventing native IDs or types."""
    event = decode_frame(
        {"data": '{"new_field":"full event"}', "event": "message", "id": None}
    )
    assert event["identity_source"] == "generated"
    assert event["kind"] == "unrecognized"
    assert event["raw_data"] == {"new_field": "full event"}
    assert event["normalization_warnings"]
    assert event["id"] != decode_frame(event["frame"])["id"]


@pytest.mark.parametrize(
    "content_type,version", [("text/html", "2.0.32"), ("application/json", "1.18.34")]
)
def test_api_identity_rejects_spa_fallback_and_other_dialects(
    content_type: str,
    version: str,
) -> None:
    """HTTP 200 is insufficient to validate an OpenCode API connection."""
    response = httpx.Response(
        200, headers={"content-type": content_type}, json={"version": version}
    )
    if content_type == "text/html":
        with pytest.raises(ValueError):
            check_response(response)
    else:
        assert check_response(response)


def test_connection_discovery_uses_private_registration_without_exposing_password(
    tmp_path: Path,
) -> None:
    """Only loopback service metadata is used, with authentication kept in memory."""
    registration = tmp_path / "service.json"
    registration.write_text(
        json.dumps(
            {
                "url": "http://127.0.0.1:4096",
                "id": "instance",
                "password": "private-secret",
            }
        )
    )
    settings = replace(
        Settings(),
        opencode_url=None,
        opencode_password=None,
        opencode_service_file=registration,
    )
    connection = discover_connection(settings)
    assert connection.password == "private-secret"
    assert "private-secret" not in repr(connection)
    assert "private-secret" not in repr(settings)
    with pytest.raises(ValueError):
        discover_connection(replace(settings, opencode_url="http://example.com"))


def test_events_are_idempotent_and_do_not_double_count_usage(tmp_path: Path) -> None:
    """Stored live observations have independent provenance and observed cursors."""
    storage = Storage(tmp_path / "trace.db")
    storage.initialize()
    payload = native_event()
    event = decode_frame({"data": json.dumps(payload), "event": "message", "id": None})
    storage.save_event("instance-1", event)
    storage.save_event("instance-2", event)
    page = storage.events("s1", (50, 0))
    assert page["total"] == 1
    assert page["items"][0]["raw_data"] == payload
    assert page["items"][0]["instance_id"] == "instance-1"
    assert storage.events("other", (50, 0))["total"] == 0
    assert storage.usage()["generation_count"] == 0
    with storage.connect() as connection:
        assert (
            connection.execute("SELECT seq FROM observed_event_cursor").fetchone()[0]
            == 3
        )


@pytest.mark.parametrize("version", ["2.0.32", "2.0.33", "3.0.0"])
def test_live_subscription_preserves_events_and_never_persists_authentication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    """The HTTP subscription persists full events, not request credentials."""
    storage = Storage(tmp_path / "trace.db")
    storage.initialize()
    settings = replace(
        Settings(),
        opencode_url="http://127.0.0.1:4096",
        opencode_password="private-secret",
    )
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/info":
            return httpx.Response(200, json={"version": version})
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=f"data: {json.dumps(native_event())}\n\n",
        )

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: client_class(**kwargs, transport=httpx.MockTransport(handler)),
    )
    collector = LiveCollector(settings, storage)
    with pytest.raises(ValueError, match="disconnected"):
        asyncio.run(collector.subscribe())
    assert requests[0].headers.get("authorization", "").startswith("Basic ")
    assert storage.events(None, (50, 0))["total"] == 1
    assert "private-secret" not in json.dumps(storage.events(None, (50, 0)))
    assert collector.status["last_seen"] is not None
    assert collector.status["state"] == (
        "connected" if version == "2.0.32" else "partial"
    )


def test_reconnection_failure_and_shutdown_leave_persisted_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconnect attempts never claim replay, and cancellation records shutdown."""
    storage = Storage(tmp_path / "trace.db")
    storage.initialize()
    collector = LiveCollector(Settings(), storage)
    attempts = []

    async def subscribe():
        attempts.append(True)
        if len(attempts) == 1:
            raise ValueError("Disconnected")
        raise asyncio.CancelledError

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(collector, "subscribe", subscribe)
    monkeypatch.setattr("graphen_trace.services.live_collector.asyncio.sleep", no_sleep)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(collector.run())
    assert len(attempts) == 2
    assert collector.status["possible_gap"]
    assert [item["state"] for item in storage.live_history()] == [
        "stopped",
        "disconnected",
    ]


def test_schema_two_upgrades_without_losing_existing_records(tmp_path: Path) -> None:
    """Live-event tables are additive and survive storage initialization again."""
    storage = Storage(tmp_path / "trace.db")
    storage.initialize()
    event = decode_frame(
        {"data": json.dumps(native_event()), "event": "message", "id": None}
    )
    storage.save_event("instance", event)
    with storage.connect() as connection:
        connection.execute("PRAGMA user_version = 2")
    storage.initialize()
    assert storage.events(None, (50, 0))["total"] == 1
    with storage.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
