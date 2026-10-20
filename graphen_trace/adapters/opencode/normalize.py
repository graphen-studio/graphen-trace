"""Lossless source capture and normalized projections for the OpenCode V2 dialect."""

import hashlib
import json
from datetime import datetime, timezone


def _mapping(value: object) -> dict:
    """Checks optional source objects without silently accepting a changed format."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Unsupported OpenCode metadata format")
    return value


def model_metadata(data: dict) -> dict[str, str] | None:
    """Copies only recognized model identifiers, never arbitrary provider state."""
    model = _mapping(data.get("model"))
    return {
        key: value
        for key, value in model.items()
        if key in {"id", "providerID", "variant"} and isinstance(value, str)
    } or None


def revision(session: dict) -> str:
    """Builds a revision from the session and message projection watermarks."""
    payload = json.dumps(session, sort_keys=True).encode()
    return "structural-v1:" + hashlib.sha256(payload).hexdigest()


def token_usage(data: dict) -> dict:
    """Extracts native token categories without interpreting absent values as zero."""
    tokens = data.get("tokens") or {}
    if not isinstance(tokens, dict):
        raise ValueError("Unsupported OpenCode token format")
    cache = tokens.get("cache") or {}
    if not isinstance(cache, dict):
        raise ValueError("Unsupported OpenCode cache token format")
    values = {
        "input_tokens": tokens.get("input"),
        "output_tokens": tokens.get("output"),
        "reasoning_tokens": tokens.get("reasoning"),
        "cache_read_tokens": cache.get("read"),
        "cache_write_tokens": cache.get("write"),
    }
    return {
        key: (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
        for key, value in values.items()
    }


def timestamp(value: object) -> str | None:
    """Converts a native millisecond timestamp when the source provides one."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def normalize_tools(data: dict) -> list[dict]:
    """Extracts tool execution state and payloads while preserving native values."""
    tools = {}
    content = data.get("content") or []
    if not isinstance(content, list):
        raise ValueError("Unsupported OpenCode content format")
    for raw_part in content:
        part = _mapping(raw_part)
        if part.get("type") != "tool":
            continue
        state = _mapping(part.get("state"))
        times = _mapping(part.get("time"))
        metadata = _mapping(state.get("metadata"))
        tool_id = part.get("id")
        if not isinstance(tool_id, str) or not tool_id:
            raise ValueError("OpenCode tool execution has no native ID")
        fields = (part.get("name"), state.get("status"), metadata.get("sessionId"))
        if any(value is not None and not isinstance(value, str) for value in fields):
            raise ValueError("Unknown OpenCode tool metadata")
        if metadata.get("exit") is not None and not isinstance(metadata["exit"], int):
            raise ValueError("Unknown OpenCode tool exit code")
        started, completed = times.get("created"), times.get("completed")
        duration = None
        if isinstance(started, (int, float)) and isinstance(completed, (int, float)):
            duration = completed - started if completed >= started else None
        tools[tool_id] = {
            "id": tool_id,
            "name": part.get("name"),
            "status": state.get("status"),
            "started_at": timestamp(started),
            "completed_at": timestamp(completed),
            "duration_ms": duration,
            "exit_code": metadata.get("exit"),
            "child_session_id": metadata.get("sessionId"),
            "input": state.get("input"),
            "output": state.get("content"),
            "error": state.get("error"),
            "metadata": metadata,
        }
    return list(tools.values())


def _message(message: dict) -> dict:
    """Preserves a source record even when individual normalization features fail."""
    warnings = []
    raw = message.get("data")
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        payload = raw
        warnings.append("Message JSON could not be decoded; original payload preserved")
    data = payload if isinstance(payload, dict) else {}
    if not isinstance(payload, dict):
        warnings.append("Unknown message payload; normalized fields are unavailable")
    kind = message.get("type") if isinstance(message.get("type"), str) else "unknown"
    item = {
        "id": message["id"],
        "kind": kind,
        "sequence": message.get("seq") if isinstance(message.get("seq"), int) else None,
        "created_at": timestamp(message.get("time_created")),
        "completed_at": None,
        "model": None,
        "finish": None,
        "usage": None,
        "tools": [],
        "source": "opencode:sqlite:v2",
        "raw_data": data,
        "raw_payload": payload if not isinstance(payload, dict) else None,
        "source_record": {
            key: value for key, value in message.items() if key != "data"
        },
        "reported_cost": None,
        "normalization_warnings": warnings,
    }
    try:
        item["completed_at"] = timestamp(_mapping(data.get("time")).get("completed"))
    except ValueError:
        warnings.append("Unknown message time format")
    if kind == "assistant":
        for key, extractor in (
            ("model", model_metadata),
            ("usage", token_usage),
            ("tools", normalize_tools),
        ):
            try:
                item[key] = extractor(data)
            except (ValueError, TypeError):
                warnings.append(f"Unknown {key} format; original payload preserved")
        item["finish"] = (
            data.get("finish") if isinstance(data.get("finish"), str) else None
        )
        cost = data.get("cost")
        item["reported_cost"] = (
            cost
            if isinstance(cost, (int, float)) and not isinstance(cost, bool)
            else None
        )
    return item


def normalize_timeline(messages: list[dict]) -> list[dict]:
    """Builds an ordered timeline with inferred user-message associations."""
    timeline = []
    interaction_id = None
    ordered = all(isinstance(message.get("seq"), int) for message in messages)
    for message in messages:
        item = _message(message)
        if item["kind"] == "user" and ordered:
            interaction_id = message["id"]
        item.update(
            interaction_id=interaction_id,
            interaction_source="sequence" if interaction_id else None,
        )
        timeline.append(item)
    seen_tools = set()
    for item in reversed(timeline):
        executions = []
        for tool in item["tools"]:
            if tool["id"] not in seen_tools:
                executions.append(tool)
                seen_tools.add(tool["id"])
        item["tools"] = executions
    return timeline


def normalize_session(session: dict, messages: list[dict]) -> dict:
    """Extracts session metadata and non-overlapping native usage categories."""
    usage = {
        name: None
        for name in (
            "input_tokens",
            "output_tokens",
            "reasoning_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
        )
    }
    model = None
    costs = []
    generations = 0
    observations = dict.fromkeys(usage, 0)
    timeline = normalize_timeline(messages)
    for item in timeline:
        if item["kind"] != "assistant":
            continue
        model = item["model"] or model
        generations += 1
        if item["reported_cost"] is not None:
            costs.append(item["reported_cost"])
        values = item["usage"] or {}
        for key, value in values.items():
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                usage[key] = (usage[key] or 0) + value
                observations[key] += 1
    incomplete = [key for key, count in observations.items() if count < generations]
    if session["message_count"] is None or any(
        item["kind"] == "unknown" for item in timeline
    ):
        incomplete = list(usage)
    warnings = {
        warning for item in timeline for warning in item["normalization_warnings"]
    }
    metadata = {}
    for key in ("title", "directory", "parent_id", "version"):
        value = session.get(key)
        metadata[key] = value if isinstance(value, str) else None
        if value is not None and not isinstance(value, str):
            warnings.add(f"Unknown session {key} format; native value preserved")
    return {
        "id": session["id"],
        "agent": "opencode",
        **metadata,
        "model": model,
        "updated_at": timestamp(session.get("time_updated")),
        "message_count": session["message_count"],
        "source": "opencode:sqlite:v2",
        "usage": usage,
        "usage_incomplete": incomplete,
        "generation_count": (
            generations
            if session["message_count"] is not None
            and not any(item["kind"] == "unknown" for item in timeline)
            else None
        ),
        "reported_cost": sum(costs) if costs else None,
        "cost_incomplete": len(costs) < generations or session["message_count"] is None,
        "revision": revision(session),
        "timeline": timeline if session["message_count"] is not None else None,
        "timeline_records": messages if session["message_count"] is not None else None,
        "normalization_warnings": sorted(warnings),
    }
