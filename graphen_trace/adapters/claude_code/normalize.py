"""Conservative Graphen projections retaining every native transcript record."""

import json
from datetime import datetime, timezone

SOURCE = "claude-code:project-jsonl:v1"
NORMALIZATION_REVISION = "claude-code-normalization-v1"
USAGE_FIELDS = {
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_input_tokens",
    "cache_write_tokens": "cache_creation_input_tokens",
    "reasoning_tokens": None,
}


def timestamp(value: object) -> str | None:
    """Returns UTC timestamps only when the native value is parseable."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def token_usage(message: dict) -> dict:
    """Maps explicit token categories, without deriving totals or reasoning."""
    native = message.get("usage")
    native = native if isinstance(native, dict) else {}
    usage = {}
    for common, field in USAGE_FIELDS.items():
        value = native.get(field)
        usage[common] = (
            value
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0
            else None
        )
    return usage


def content_blocks(record: dict) -> list[dict]:
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return (
        [block for block in content if isinstance(block, dict)]
        if isinstance(content, list)
        else []
    )


def normalize_timeline_rows(rows: list[dict]) -> list[dict]:
    """Projects stored records using their persisted identity and file position."""
    records = [json.loads(row["data"]) for row in rows]
    latest = {
        record["uuid"]: index
        for index, record in enumerate(records)
        if isinstance(record.get("uuid"), str)
    }
    active = [
        not isinstance(record.get("uuid"), str) or latest[record["uuid"]] == index
        for index, record in enumerate(records)
    ]
    results = {}
    calls = {}
    for index, (record, current) in enumerate(zip(records, active)):
        if not current:
            continue
        for block in content_blocks(record):
            if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                calls[block["id"]] = index
            if block.get("type") == "tool_result" and isinstance(
                block.get("tool_use_id"), str
            ):
                results[block["tool_use_id"]] = (record, block)

    timeline = []
    for index, (row, record, current) in enumerate(zip(rows, records, active)):
        message = record.get("message")
        message = message if isinstance(message, dict) else {}
        role = message.get("role")
        kind = role if isinstance(role, str) else record.get("type", "unknown")
        kind = kind if isinstance(kind, str) else "unknown"
        if not current:
            kind = "native-update"
        created_at = timestamp(record.get("timestamp"))
        model = {
            common: message[native]
            for native, common in (("model", "id"), ("provider", "providerID"))
            if isinstance(message.get(native), str)
        }
        item = {
            "id": row["id"],
            "kind": kind,
            "sequence": row["seq"],
            "interaction_id": None,
            "interaction_source": None,
            "created_at": created_at,
            "completed_at": None,
            "model": (model or None) if kind == "assistant" else None,
            "finish": (
                message.get("stop_reason")
                if kind == "assistant" and isinstance(message.get("stop_reason"), str)
                else None
            ),
            "usage": token_usage(message) if kind == "assistant" else None,
            "tools": [],
            "source": SOURCE,
            "raw_data": message if message else {"record": record},
            "source_record": {
                key: value for key, value in record.items() if key != "message"
            },
            "reported_cost": None,
            "normalization_warnings": [],
        }
        for block in content_blocks(record) if current else []:
            if block.get("type") != "tool_use" or not isinstance(block.get("id"), str):
                continue
            if calls[block["id"]] != index:
                continue
            result_record, result = results.get(block["id"], ({}, {}))
            item["tools"].append(
                {
                    "id": block["id"],
                    "name": (
                        block.get("name")
                        if isinstance(block.get("name"), str)
                        else None
                    ),
                    "status": (
                        "error"
                        if result.get("is_error") is True
                        else "completed" if result else None
                    ),
                    "started_at": created_at,
                    "completed_at": timestamp(result_record.get("timestamp")),
                    "duration_ms": None,
                    "exit_code": None,
                    "child_session_id": None,
                    "input": block.get("input"),
                    "output": result.get("content"),
                    "error": (
                        result.get("content")
                        if result.get("is_error") is True
                        else None
                    ),
                    "metadata": {"tool_call": block, "tool_result": result or None},
                }
            )
        timeline.append(item)
    return timeline


def revision(session: dict) -> str:
    return f"{NORMALIZATION_REVISION}:{session['revision']}"


def normalize_session(session: dict) -> dict:
    """Builds summaries without billing, sidechain, or aggregate-cost inference."""
    records = session["records"]
    latest = {
        record["uuid"]: index
        for index, record in enumerate(records)
        if isinstance(record.get("uuid"), str) and record["uuid"]
    }
    fallback_prefix = "record:"
    while any(native_id.startswith(fallback_prefix) for native_id in latest):
        fallback_prefix = f"record:{fallback_prefix}"
    rows = [
        {
            "id": (
                record["uuid"]
                if isinstance(record.get("uuid"), str)
                and latest.get(record["uuid"]) == index
                else f"{fallback_prefix}{index}"
            ),
            "seq": index,
            "type": (
                record["message"].get("role", "unknown")
                if isinstance(record.get("message"), dict)
                else record.get("type", "unknown")
            ),
            "time_created": None,
            "time_updated": None,
            "data": json.dumps(record, ensure_ascii=False),
        }
        for index, record in enumerate(records)
    ]
    timeline = normalize_timeline_rows(rows)
    for row, item in zip(rows, timeline):
        row["type"] = item["kind"]
    # Multiple content records can describe one native assistant message.
    generations = {}
    for item, record in zip(timeline, records):
        message = record.get("message")
        if (
            item["kind"] == "assistant"
            and isinstance(message, dict)
            and message.get("role") == "assistant"
        ):
            message_id = message.get("id")
            identity = message_id if isinstance(message_id, str) else item["id"]
            generations[identity] = item
    usage = dict.fromkeys(USAGE_FIELDS)
    incomplete = []
    for key in USAGE_FIELDS:
        values = [item["usage"][key] for item in generations.values()]
        known = [value for value in values if value is not None]
        usage[key] = sum(known) if known else None
        if not values or len(known) != len(values):
            incomplete.append(key)
    directory = next(
        (
            record["cwd"]
            for record in reversed(records)
            if isinstance(record.get("cwd"), str)
        ),
        None,
    )
    version = next(
        (
            record["version"]
            for record in reversed(records)
            if isinstance(record.get("version"), str)
        ),
        session.get("agent_version", "unknown"),
    )
    return {
        "id": session["id"],
        "agent": "claude",
        "title": None,
        "directory": directory,
        "parent_id": None,
        "version": version,
        "model": next(
            (item["model"] for item in reversed(timeline) if item["model"]), None
        ),
        "updated_at": next(
            (item["created_at"] for item in reversed(timeline) if item["created_at"]),
            None,
        ),
        "message_count": len(timeline),
        "source": SOURCE,
        "usage": usage,
        "usage_incomplete": incomplete,
        "generation_count": len(generations),
        "reported_cost": None,
        "cost_incomplete": True,
        "revision": revision(session),
        "source_record": {"sessionId": session["id"]},
        "timeline": timeline,
        "timeline_records": rows,
        "normalization_warnings": [],
    }
