"""Lossless native-record capture and Graphen projections for Kiro CLI."""

import json
import re
from datetime import datetime, timezone

SOURCE = "kiro-cli:session-jsonl:v1"
WORKSPACE_SOURCE = "kiro-workspace:session-jsonl:v1"
NORMALIZATION_REVISION = "kiro-normalization-v2"
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)

TOKEN_ALIASES = {
    "input_tokens": {
        "inputtoken",
        "inputtokens",
        "inputtokencount",
        "inputtokenscount",
    },
    "output_tokens": {
        "outputtoken",
        "outputtokens",
        "outputtokencount",
        "outputtokenscount",
    },
    "reasoning_tokens": {
        "reasoningtoken",
        "reasoningtokens",
        "reasoningtokencount",
    },
    "cache_read_tokens": {
        "cachereadtoken",
        "cachereadtokens",
        "cachereadinputtoken",
        "cachereadinputtokens",
        "cachereadinputtokencount",
    },
    "cache_write_tokens": {
        "cachewritetoken",
        "cachewritetokens",
        "cachewriteinputtoken",
        "cachewriteinputtokens",
        "cachewriteinputtokencount",
    },
}


def normalize_timestamp(value: object) -> str | None:
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


def normalize_key(value: str) -> str:
    """Normalizes token field names for explicit alias matching."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def token_usage(value: object) -> dict:
    """Finds explicitly named token counters without interpreting credit fields."""
    found = dict.fromkeys(USAGE_KEYS)

    def visit(item: object) -> None:
        if isinstance(item, dict):
            for name, child in item.items():
                if isinstance(name, str):
                    normalized = normalize_key(name)
                    for common, aliases in TOKEN_ALIASES.items():
                        if normalized in aliases and valid_count(child):
                            found[common] = child
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return found


def valid_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def extract_model(value: object) -> dict[str, str] | None:
    """Extracts model identifiers explicitly present in native metadata."""
    if not isinstance(value, dict):
        return None
    model: dict[str, str] = {}
    for source_key, target_key in (
        ("effective_model", "id"),
        ("effectiveModel", "id"),
        ("resolved_model", "id"),
        ("resolvedModel", "id"),
        ("provider_model", "id"),
        ("providerModel", "id"),
        ("modelName", "id"),
        ("model_name", "id"),
        ("modelId", "id"),
        ("model_id", "id"),
        ("model", "id"),
        ("provider", "providerID"),
        ("providerId", "providerID"),
        ("provider_id", "providerID"),
        ("reasoningModelId", "reasoning_model_id"),
    ):
        candidate = value.get(source_key)
        if isinstance(candidate, str) and candidate:
            model[target_key] = candidate
    return model or None


def merge_model(*models: dict[str, str] | None) -> dict[str, str] | None:
    """Combines selected, provider, and reasoning-model provenance."""
    combined = {}
    for model in models:
        if model:
            combined.update(model)
    return combined or None


def turn_metadata(metadata: dict) -> list[dict]:
    """Returns native per-turn metadata records when present."""
    state = metadata.get("session_state")
    conversation = (
        state.get("conversation_metadata") if isinstance(state, dict) else None
    )
    turns = (
        conversation.get("user_turn_metadatas")
        if isinstance(conversation, dict)
        else None
    )
    return (
        [turn for turn in turns if isinstance(turn, dict)]
        if isinstance(turns, list)
        else []
    )


def aggregate_turn_usage(turns: list[dict]) -> dict:
    """Sums token counters once per native turn metadata record."""
    totals = dict.fromkeys(USAGE_KEYS)
    for turn in turns:
        values = token_usage(turn)
        for key in USAGE_KEYS:
            if values[key] is not None:
                totals[key] = (totals[key] or 0) + values[key]
    return totals


def aggregate_workspace_usage(records: list[dict]) -> dict:
    """Aggregates explicit token counters from workspace usage summaries."""
    totals = dict.fromkeys(USAGE_KEYS)
    for record in records:
        decoded = record_data(record)
        if decoded is None or decoded[0] != "usage_summary":
            continue
        summaries = decoded[1].get("promptTurnSummaries")
        observations = (
            [token_usage(summary) for summary in summaries]
            if isinstance(summaries, list)
            else [token_usage(decoded[1])]
        )
        for observation in observations:
            for key in USAGE_KEYS:
                if observation[key] is not None:
                    totals[key] = (totals[key] or 0) + observation[key]
    return totals


def count_generations(session: dict, generations: list[dict]) -> int:
    """Counts workspace turns from native IDs instead of assistant subevents."""
    if session.get("layout") != "workspace":
        return len(generations)
    usage_summaries = []
    turn_ids = set()
    for record in session["records"]:
        decoded = record_data(record)
        if decoded is None:
            continue
        kind, data = decoded
        if kind == "usage_summary":
            summaries = data.get("promptTurnSummaries")
            usage_summaries.append(len(summaries) if isinstance(summaries, list) else 1)
        if kind == "assistant":
            identifier = data.get("executionId") or data.get("turnId")
            if isinstance(identifier, str):
                turn_ids.add(identifier)
    if usage_summaries:
        return sum(usage_summaries)
    return len(turn_ids) if turn_ids else len(generations)


def record_data(record: dict) -> tuple[str, dict] | None:
    """Recognizes the CLI envelope while retaining unknown event kinds."""
    kind, data = record.get("kind"), record.get("data")
    if isinstance(kind, str) and isinstance(data, dict):
        return kind, data
    payload = record.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("type"), str):
        return payload["type"], payload
    return None


def interaction_map_by_execution(records: list[dict]) -> dict[str, str]:
    """Links each native turn ID to the preceding user message ID."""
    interactions = {}
    current_interaction = None
    for record in records:
        decoded = record_data(record)
        if decoded is None:
            continue
        kind, data = decoded
        if kind in {"Prompt", "user"}:
            current_interaction = record_id(record, data, len(interactions))
        elif kind == "turn_start":
            execution_id = data.get("executionId") or data.get("execution_id")
            if isinstance(execution_id, str) and current_interaction:
                interactions[execution_id] = current_interaction
    return interactions


def subexecution_parents(records: list[dict]) -> dict[str, str]:
    """Maps child transcript IDs to their native parent execution IDs."""
    parents = {}
    for record in records:
        decoded = record_data(record)
        if decoded is None or decoded[0] not in {"sub_agent_start", "subagent_start"}:
            continue
        data = decoded[1]
        subexecution_id = data.get("subSessionId") or data.get("subExecutionId")
        parent_execution_id = data.get("parentExecutionId") or data.get(
            "parent_execution_id"
        )
        if isinstance(subexecution_id, str) and isinstance(parent_execution_id, str):
            parents[subexecution_id] = parent_execution_id
    return parents


def normalize_timeline(
    records: list[dict],
    metadata: dict,
    source: str = SOURCE,
    parent_interactions: dict[str, str] | None = None,
) -> list[dict]:
    """Projects CLI transcript records in file order and links proven tool IDs."""
    turns = turn_metadata(metadata)
    turn_by_id: dict[str, dict] = {}
    for turn in turns:
        for key in ("turn_id", "turnId", "execution_id", "executionId"):
            value = turn.get(key)
            if isinstance(value, str):
                turn_by_id[value] = turn

    execution_interactions = interaction_map_by_execution(records)
    if parent_interactions:
        execution_interactions.update(parent_interactions)
    tool_results: dict[tuple[str | None, str], tuple[dict, dict]] = {}
    for record in records:
        decoded = record_data(record)
        if decoded and decoded[0] == "tool_result":
            call_id = decoded[1].get("toolCallId")
            if isinstance(call_id, str):
                subexecution = record.get("_graphen_subexecution")
                subexecution_id = (
                    subexecution.get("id") if isinstance(subexecution, dict) else None
                )
                tool_results[(subexecution_id, call_id)] = (record, decoded[1])

    timeline = []
    interaction_id = None
    assistant_count = sum(
        1
        for record in records
        if record_data(record) is not None
        and record_data(record)[0] in {"AssistantMessage", "assistant"}
    )
    for sequence, record in enumerate(records):
        decoded = record_data(record)
        kind, data = decoded if decoded else (record.get("kind", "unknown"), {})
        if kind in {"Prompt", "user"}:
            interaction_id = record_id(record, data, sequence)
        native_id = record_id(record, data, sequence)
        subexecution = record.get("_graphen_subexecution")
        subexecution_id = (
            subexecution.get("id") if isinstance(subexecution, dict) else None
        )
        parent_execution_id = (
            subexecution.get("parent_execution_id")
            if isinstance(subexecution, dict)
            else None
        )
        turn = None
        for key in ("turnId", "turn_id", "executionId", "execution_id"):
            value = data.get(key)
            if isinstance(value, str) and value in turn_by_id:
                turn = turn_by_id[value]
                break
        if (
            turn is None
            and kind in {"AssistantMessage", "assistant"}
            and len(turns) == 1
            and assistant_count == 1
        ):
            turn = turns[0]
        if isinstance(parent_execution_id, str):
            interaction_id = execution_interactions.get(parent_execution_id)

        item_kind = {
            "Prompt": "user",
            "AssistantMessage": "assistant",
            "user": "user",
            "assistant": "assistant",
            "tool_call": "tool_call",
            "tool_result": "tool_result",
        }.get(kind, kind if isinstance(kind, str) else "unknown")
        item = {
            "id": native_id,
            "kind": item_kind,
            "sequence": sequence,
            "interaction_id": interaction_id,
            "interaction_source": (
                "parent_execution"
                if interaction_id and isinstance(parent_execution_id, str)
                else "file_order" if interaction_id else None
            ),
            "created_at": normalize_timestamp(
                record.get("timestamp") or data.get("timestamp")
            ),
            "completed_at": None,
            "model": merge_model(
                extract_model(metadata), extract_model(turn or {}), extract_model(data)
            ),
            "finish": (
                data.get("stopReason")
                if isinstance(data.get("stopReason"), str)
                else None
            ),
            "usage": (
                token_usage(data) if kind in {"AssistantMessage", "assistant"} else None
            ),
            "tools": [],
            "source": source,
            "raw_data": data,
            "source_record": {
                key: value
                for key, value in record.items()
                if key not in {"data", "_graphen_projection"}
            },
            "reported_cost": None,
            "normalization_warnings": [],
        }
        if kind in {"AssistantMessage", "assistant"}:
            if turn:
                turn_usage = token_usage(turn)
                for key in USAGE_KEYS:
                    if item["usage"][key] is None:
                        item["usage"][key] = turn_usage[key]
            item["completed_at"] = item["created_at"]
        if kind == "tool_call":
            call_id = data.get("toolCallId")
            if isinstance(call_id, str):
                result = tool_results.get((subexecution_id, call_id))
                result_record = result[0] if result else None
                result_data = result[1] if result else None
                tool_id = (
                    f"{subexecution_id}:{call_id}"
                    if isinstance(subexecution_id, str)
                    else call_id
                )
                tool = {
                    "id": tool_id,
                    "name": (
                        data.get("toolName")
                        if isinstance(data.get("toolName"), str)
                        else None
                    ),
                    "status": tool_status(data, result_data),
                    "started_at": item["created_at"],
                    "completed_at": normalize_timestamp(
                        (result_data or {}).get("timestamp")
                        or (result_record or {}).get("timestamp")
                    ),
                    "duration_ms": None,
                    "exit_code": None,
                    "child_session_id": None,
                    "input": data.get("args"),
                    "output": result_data.get("content") if result_data else None,
                    "error": None,
                    "metadata": {
                        "tool_call": data,
                        "tool_result": result_data,
                        "_graphen_subexecution": subexecution,
                    },
                }
                item["tools"].append(tool)
        timeline.append(item)
    return timeline


def record_id(record: dict, data: dict, sequence: int) -> str:
    """Returns a stable native ID, with deterministic fallback for id-less rows."""
    for candidate in (data.get("message_id"), record.get("id")):
        if isinstance(candidate, str) and candidate:
            native_id = candidate
            break
    else:
        native_id = f"record-{sequence}"
    subexecution = record.get("_graphen_subexecution")
    subexecution_id = subexecution.get("id") if isinstance(subexecution, dict) else None
    return (
        f"subexecution:{subexecution_id}:{native_id}"
        if isinstance(subexecution_id, str)
        else native_id
    )


def tool_status(call: dict, result: dict | None) -> str | None:
    """Maps only explicit tool success/failure evidence."""
    if result is not None and isinstance(result.get("success"), bool):
        return "completed" if result["success"] else "error"
    status = call.get("status")
    return status if isinstance(status, str) else None


def normalize_timeline_rows(rows: list[dict]) -> list[dict]:
    """Normalizes stored native JSONL rows while retaining global ordering."""
    records = []
    for row in rows:
        try:
            record = json.loads(row["data"])
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
        if isinstance(record, dict):
            records.append((row.get("seq"), record))
    source = (
        WORKSPACE_SOURCE
        if any(isinstance(record.get("payload"), dict) for sequence, record in records)
        else SOURCE
    )
    normalized = normalize_timeline(
        [record for sequence, record in records], {}, source
    )
    sequence_by_id = {}
    stored_projection = {}
    for (sequence, record), item in zip(records, normalized):
        sequence_by_id[item["id"]] = sequence
        stored_projection[item["id"]] = record.get("_graphen_projection")
    for item in normalized:
        item["sequence"] = sequence_by_id.get(item["id"], item["sequence"])
        stored = stored_projection.get(item["id"])
        if isinstance(stored, dict):
            item["model"] = stored.get("model", item["model"])
            item["usage"] = stored.get("usage", item["usage"])
    return normalized


def revision(session: dict) -> str:
    """Includes normalization version so projection changes trigger re-import."""
    return f"{NORMALIZATION_REVISION}:{session['revision']}"


def merge_subexecution_timeline(
    session: dict, parent_timeline: list[dict]
) -> tuple[list[dict], list[str]]:
    """Adds child transcript events and retains their native parent linkage."""
    subexecutions = session.get("subexecutions")
    if not isinstance(subexecutions, list) or not subexecutions:
        return parent_timeline, []

    records = session["records"]
    parent_by_subexecution = subexecution_parents(records)
    parent_interactions = interaction_map_by_execution(records)
    source = session.get("source", SOURCE)
    metadata = session["metadata"]
    child_timeline = []
    warnings = []

    for subexecution in subexecutions:
        if not isinstance(subexecution, dict):
            continue
        subexecution_id = subexecution.get("id")
        child_records = subexecution.get("records")
        if not isinstance(subexecution_id, str) or not isinstance(child_records, list):
            continue
        parent_execution_id = parent_by_subexecution.get(subexecution_id)
        if parent_execution_id is None:
            warnings.append(
                "Kiro sub-execution transcript has no matching parent lifecycle event"
            )
        context = {
            "id": subexecution_id,
            "parent_execution_id": parent_execution_id,
        }
        tagged_records = [
            {**record, "_graphen_subexecution": context}
            for record in child_records
            if isinstance(record, dict)
        ]
        child_timeline.extend(
            normalize_timeline(
                tagged_records,
                metadata,
                source,
                parent_interactions,
            )
        )

    if not child_timeline:
        return parent_timeline, warnings

    timeline = [*parent_timeline, *child_timeline]
    if all(item.get("created_at") for item in timeline):
        timeline.sort(key=lambda item: item["created_at"])
    else:
        warnings.append(
            "Kiro parent and sub-execution events lack complete timestamps; "
            "child events are appended after parent records"
        )
    for sequence, item in enumerate(timeline):
        item["sequence"] = sequence
    return timeline, warnings


def native_timeline_record(item: dict) -> dict:
    """Reconstructs the complete native envelope for durable timeline storage."""
    record = dict(item.get("source_record") or {})
    if "data" not in record and "payload" not in record:
        record["data"] = item.get("raw_data")
    record["_graphen_projection"] = {
        "model": item.get("model"),
        "usage": item.get("usage"),
    }
    return record


def normalize_session(session: dict) -> dict:
    """Builds a session projection from Kiro CLI metadata and transcript records."""
    metadata = session["metadata"]
    source = session.get("source", SOURCE)
    parent_timeline = normalize_timeline(session["records"], metadata, source)
    timeline, subexecution_warnings = merge_subexecution_timeline(
        session, parent_timeline
    )
    generations = [item for item in parent_timeline if item["kind"] == "assistant"]
    generation_count = count_generations(session, generations)
    usage = dict.fromkeys(USAGE_KEYS)
    observed = dict.fromkeys(USAGE_KEYS, 0)
    for generation in generations:
        for key in USAGE_KEYS:
            value = (generation.get("usage") or {}).get(key)
            if value is not None:
                usage[key] = (usage[key] or 0) + value
                observed[key] += 1

    turn_usage = aggregate_turn_usage(turn_metadata(metadata))
    workspace_usage = aggregate_workspace_usage(session["records"])
    for key in USAGE_KEYS:
        if observed[key] == 0 and turn_usage[key] is not None:
            usage[key] = turn_usage[key]
            observed[key] = 1
        if observed[key] == 0 and workspace_usage[key] is not None:
            usage[key] = workspace_usage[key]
            observed[key] = 1

    incomplete = [key for key, count in observed.items() if count < len(generations)]
    if not generations:
        incomplete = list(USAGE_KEYS)
    model = extract_model(metadata)
    if model is None:
        state = metadata.get("session_state")
        model_state = state.get("rts_model_state") if isinstance(state, dict) else None
        model = (
            extract_model(model_state.get("model_info"))
            if isinstance(model_state, dict)
            else None
        )
    if model is None:
        model = next(
            (item["model"] for item in reversed(generations) if item["model"]), None
        )
    if model is None:
        model = next(
            (
                turn_model
                for turn in reversed(turn_metadata(metadata))
                if (turn_model := extract_model(turn)) is not None
            ),
            None,
        )

    timestamps = [
        value
        for value in (
            metadata.get("updated_at"),
            metadata.get("lastModifiedAt"),
            metadata.get("created_at"),
            metadata.get("createdAt"),
        )
        if isinstance(value, str)
    ]
    updated_at = normalize_timestamp(timestamps[0]) if timestamps else None
    warnings = list(subexecution_warnings)
    if (
        metadata.get("schemaVersion") is None
        and metadata.get("dataModelVersion") is None
    ):
        warnings.append("Kiro CLI session schema version is unavailable")
    if session.get("layout") == "workspace":
        warnings.append(
            "Kiro workspace session origin is ambiguous and may include IDE activity"
        )
    if generations and all(
        not any((item.get("usage") or {}).values()) for item in generations
    ):
        warnings.append(
            "Kiro CLI transcript contains no non-zero token counters; "
            "zero values are preserved as reported"
        )

    return {
        "id": session["id"],
        "agent": "kiro",
        "title": (
            metadata.get("title") if isinstance(metadata.get("title"), str) else None
        ),
        "directory": session_directory(metadata),
        "parent_id": None,
        "version": session.get("agent_version", "unknown"),
        "model": model,
        "updated_at": updated_at,
        "message_count": len(timeline),
        "source": source,
        "usage": usage,
        "usage_incomplete": incomplete,
        "generation_count": generation_count,
        "reported_cost": None,
        "cost_incomplete": True,
        "revision": revision(session),
        "source_record": metadata,
        "timeline": timeline,
        "timeline_records": [
            {
                "id": item["id"],
                "seq": item["sequence"],
                "type": item["kind"],
                "time_created": None,
                "time_updated": None,
                "data": json.dumps(native_timeline_record(item), ensure_ascii=False),
            }
            for item in timeline
        ],
        "normalization_warnings": warnings,
    }


def session_directory(metadata: dict) -> str | None:
    """Returns a local workspace path when one is available in metadata."""
    cwd = metadata.get("cwd")
    if isinstance(cwd, str):
        return cwd
    for key in ("workspacePaths", "rootPaths"):
        paths = metadata.get(key)
        if isinstance(paths, list):
            candidate = next((path for path in paths if isinstance(path, str)), None)
            if candidate:
                return candidate
    return None
