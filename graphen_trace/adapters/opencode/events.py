"""OpenCode V2 SSE framing and lossless event envelopes."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx


async def read_frames(lines: AsyncIterator[str]) -> AsyncIterator[dict]:
    """Decodes SSE data frames, ignoring comments and honoring multiline data."""
    data = []
    event_type = "message"
    event_id = None
    async for line in lines:
        if not line:
            if data:
                yield decode_frame(
                    {"data": "\n".join(data), "event": event_type, "id": event_id}
                )
            data = []
            event_type = "message"
            event_id = None
            continue
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "data":
            data.append(value)
        elif field == "event":
            event_type = value
        elif field == "id" and "\x00" not in value:
            event_id = value
    if data:
        raise ValueError("OpenCode event stream ended with an incomplete frame")


def decode_frame(frame: dict) -> dict:
    """Preserves native events and rejects stream failure frames explicitly."""
    if frame["event"] == "effect/http-api/stream/failure":
        raise ValueError(
            "OpenCode SSE reported a stream failure; live events may be missing"
        )

    payload, warnings = _decode_payload(frame["data"])
    event_id, identity_source = _event_identity(payload, warnings)
    kind = payload.get("type")
    if not isinstance(kind, str):
        kind = "unrecognized"
        warnings.append("Unknown event type; original payload preserved")

    data = payload.get("data")
    session_id = data.get("sessionID") if isinstance(data, dict) else None
    session_id = session_id if isinstance(session_id, str) else None
    created = payload.get("created")

    return {
        "id": event_id,
        "kind": kind,
        "session_id": session_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "created_at": created if isinstance(created, (int, float)) else None,
        "raw_data": payload,
        "frame": frame,
        "normalization_warnings": warnings,
        "identity_source": identity_source,
    }


def _decode_payload(raw_data: str) -> tuple[dict, list[str]]:
    """Parses supported JSON encodings and preserves unknown payloads."""
    warnings = []
    try:
        payload = json.loads(raw_data)
        if isinstance(payload, str):
            payload = json.loads(payload)
    except ValueError:
        payload = {"unparsed_payload": raw_data}
        warnings.append("Unknown event encoding; original SSE frame preserved")
    if not isinstance(payload, dict):
        payload = {"unparsed_payload": payload}
        warnings.append("Unknown event payload; original SSE frame preserved")

    return payload, warnings


def _event_identity(payload: dict, warnings: list[str]) -> tuple[str, str]:
    """Uses native event IDs when available and marks generated fallbacks."""
    event_id = payload.get("id")
    identity_source = "native"
    if not isinstance(event_id, str):
        event_id = f"observed_{uuid.uuid4().hex}"
        identity_source = "generated"
        warnings.append("Native event ID unavailable; replay deduplication unavailable")

    return event_id, identity_source


def check_response(response: httpx.Response) -> list[str]:
    """Checks the V2 server identity and rejects HTML SPA fallbacks."""
    if response.status_code != 200:
        raise ValueError(f"OpenCode API returned HTTP {response.status_code}")
    if "application/json" not in response.headers.get("content-type", "").lower():
        raise ValueError("OpenCode API did not return JSON")
    info = response.json()
    version = info.get("version") if isinstance(info, dict) else None
    if not isinstance(version, str) or version.removeprefix("v") != "2.0.32":
        return [
            "Server version is not validated; "
            "stream compatibility is checked per envelope"
        ]
    return []
