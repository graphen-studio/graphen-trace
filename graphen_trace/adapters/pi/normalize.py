"""Lossless source capture and normalized projections for Pi session records."""

import json
from datetime import datetime, timezone


def _timestamp(value: object) -> str | None:
    """Returns a valid source timestamp in UTC ISO format."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _usage(message: dict) -> dict:
    """Maps Pi usage categories that have direct common equivalents."""
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return {key: None for key in _USAGE_KEYS}
    values = {
        "input_tokens": usage.get("input"),
        "output_tokens": usage.get("output"),
        "reasoning_tokens": usage.get("reasoning"),
        "cache_read_tokens": usage.get("cacheRead"),
        "cache_write_tokens": usage.get("cacheWrite"),
    }
    return {
        key: (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
        for key, value in values.items()
    }


_USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)
NORMALIZATION_REVISION = "pi-normalization-v2"


def _tool_calls(records: list[dict]) -> tuple[dict, dict]:
    """Indexes native tool calls and results without losing either payload."""
    calls = {}
    results = {}
    for record in records:
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if (
                    isinstance(block, dict)
                    and block.get("type") == "toolCall"
                    and isinstance(block.get("id"), str)
                ):
                    calls[block["id"]] = (record, message, block)
        if message.get("role") == "toolResult":
            call_id = message.get("toolCallId")
            if isinstance(call_id, str):
                results[call_id] = (record, message)
    return calls, results


def normalize_timeline(records: list[dict]) -> list[dict]:
    """Normalizes message records in file order and links native tool records."""
    source_records = [record for record in records if record.get("type") != "session"]
    message_records = [
        record
        for record in source_records
        if record.get("type") == "message" and isinstance(record.get("message"), dict)
    ]
    calls, results = _tool_calls(message_records)
    timeline = []
    interaction_id = None
    message_ids = set()
    for sequence, record in enumerate(source_records):
        if record.get("type") != "message" or not isinstance(
            record.get("message"), dict
        ):
            item_id = record.get("id")
            if not isinstance(item_id, str):
                continue
            timeline.append(
                {
                    "id": item_id,
                    "kind": record.get("type", "unknown"),
                    "sequence": sequence,
                    "interaction_id": interaction_id,
                    "interaction_source": "file_order" if interaction_id else None,
                    "created_at": _timestamp(record.get("timestamp")),
                    "completed_at": None,
                    "model": None,
                    "finish": None,
                    "usage": None,
                    "tools": [],
                    "source": "pi:session-jsonl:v1",
                    "raw_data": {"record": record},
                    "raw_payload": None,
                    "source_record": record,
                    "reported_cost": None,
                    "normalization_warnings": [],
                }
            )
            continue
        message = record["message"]
        role = message.get("role")
        message_id = record.get("id")
        if not isinstance(message_id, str):
            continue
        if role == "user":
            interaction_id = message_id
        timestamp = _timestamp(message.get("timestamp") or record.get("timestamp"))
        item = {
            "id": message_id,
            "kind": role if isinstance(role, str) else "unknown",
            "sequence": sequence,
            "interaction_id": interaction_id,
            "interaction_source": "file_order" if interaction_id else None,
            "created_at": timestamp,
            "completed_at": None,
            "model": None,
            "finish": None,
            "usage": None,
            "tools": [],
            "source": "pi:session-jsonl:v1",
            "raw_data": message,
            "raw_payload": None,
            "source_record": {
                key: value for key, value in record.items() if key != "message"
            },
            "reported_cost": None,
            "normalization_warnings": [],
        }
        if role == "assistant":
            item["model"] = {
                common: message[native]
                for native, common in (
                    ("model", "id"),
                    ("provider", "providerID"),
                    ("api", "api"),
                )
                if isinstance(message.get(native), str)
            } or None
            item["finish"] = (
                message.get("stopReason")
                if isinstance(message.get("stopReason"), str)
                else None
            )
            item["usage"] = _usage(message)
            item["completed_at"] = timestamp
            usage = message.get("usage")
            cost = usage.get("cost") if isinstance(usage, dict) else None
            reported = cost.get("total") if isinstance(cost, dict) else None
            if isinstance(reported, (int, float)) and not isinstance(reported, bool):
                item["reported_cost"] = reported
        message_ids.add(message_id)
        timeline.append(item)

    for call_id, (record, message, block) in calls.items():
        result = results.get(call_id)
        destination = record.get("id")
        item = next((entry for entry in timeline if entry["id"] == destination), None)
        if item is None:
            continue
        result_message = result[1] if result else None
        is_error = result_message.get("isError") if result_message else None
        duration = result_message.get("durationMs") if result_message else None
        item["tools"].append(
            {
                "id": call_id,
                "name": (
                    block.get("name") if isinstance(block.get("name"), str) else None
                ),
                "status": (
                    "error"
                    if is_error is True
                    else "completed" if is_error is False else None
                ),
                "started_at": _timestamp(
                    message.get("timestamp") or record.get("timestamp")
                ),
                "completed_at": _timestamp(
                    (result_message or {}).get("timestamp")
                    or (result[0].get("timestamp") if result else None)
                ),
                "duration_ms": (
                    duration
                    if isinstance(duration, (int, float))
                    and not isinstance(duration, bool)
                    else None
                ),
                "exit_code": None,
                "child_session_id": None,
                "input": block.get("arguments"),
                "output": result_message.get("content") if result_message else None,
                "error": result_message.get("details") if is_error is True else None,
                "metadata": {
                    "tool_call": block,
                    "tool_result": result_message,
                },
            }
        )

    return timeline


def normalize_timeline_rows(rows: list[dict]) -> list[dict]:
    """Normalizes stored timeline rows while retaining their global sequence."""
    records = []
    for row in rows:
        try:
            record = json.loads(row["data"])
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
        if isinstance(record, dict):
            records.append((row.get("seq"), record))

    normalized = normalize_timeline([record for _, record in records])
    sequences = {
        item["id"]: sequence for (sequence, _), item in zip(records, normalized)
    }
    for item in normalized:
        item["sequence"] = sequences.get(item["id"], item["sequence"])
    return normalized


def revision(session: dict) -> str:
    """Includes the projection revision so schema changes trigger re-imports."""
    return f"{NORMALIZATION_REVISION}:{session['revision']}"


def normalize_session(session: dict) -> dict:
    """Builds a Graphen session projection from one Pi JSONL file."""
    header = session["header"]
    records = session["records"]
    timeline = normalize_timeline(records)
    generations = [item for item in timeline if item["kind"] == "assistant"]
    usage = dict.fromkeys(_USAGE_KEYS)
    observed = dict.fromkeys(_USAGE_KEYS, 0)
    reported_costs = []
    for generation in generations:
        for key in _USAGE_KEYS:
            value = (generation.get("usage") or {}).get(key)
            if value is not None:
                usage[key] = (usage[key] or 0) + value
                observed[key] += 1
        if generation["reported_cost"] is not None:
            reported_costs.append(generation["reported_cost"])
    incomplete = [key for key, count in observed.items() if count < len(generations)]
    if not generations:
        incomplete = list(_USAGE_KEYS)

    first_model = next(
        (item["model"] for item in reversed(generations) if item["model"]), None
    )
    last_activity = next(
        (
            record.get("timestamp") or (record.get("message") or {}).get("timestamp")
            for record in reversed(records)
            if record.get("type") != "session"
            and (
                isinstance(record.get("timestamp"), str)
                or isinstance((record.get("message") or {}).get("timestamp"), str)
            )
        ),
        None,
    )
    warnings = set()
    expected_messages = sum(
        1
        for record in records
        if record.get("type") == "message"
        and isinstance(record.get("id"), str)
        and isinstance(record.get("message"), dict)
    )
    normalized_messages = sum(
        1 for item in timeline if isinstance(item.get("raw_data", {}).get("role"), str)
    )
    if normalized_messages != expected_messages:
        warnings.add("Some Pi message records could not be normalized")

    return {
        "id": session["id"],
        "agent": "pi",
        "title": None,
        "directory": header.get("cwd") if isinstance(header.get("cwd"), str) else None,
        "parent_id": None,
        "version": session.get("agent_version", "unknown"),
        "model": first_model,
        "updated_at": _timestamp(last_activity),
        "message_count": len(timeline),
        "source": "pi:session-jsonl:v1",
        "usage": usage,
        "usage_incomplete": incomplete,
        "generation_count": len(generations),
        "reported_cost": sum(reported_costs) if reported_costs else None,
        "cost_incomplete": len(reported_costs) < len(generations),
        "revision": revision(session),
        "source_record": header,
        "timeline": timeline,
        "timeline_records": [
            {
                "id": record["id"],
                "seq": index,
                "type": record.get("message", {}).get("role", "unknown"),
                "time_created": None,
                "time_updated": None,
                "data": json.dumps(record, ensure_ascii=False),
            }
            for index, record in enumerate(records)
            if record.get("type") != "session" and isinstance(record.get("id"), str)
        ],
        "normalization_warnings": sorted(warnings),
    }
