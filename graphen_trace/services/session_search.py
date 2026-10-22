"""Text extraction for searching observed OpenCode prompts and responses."""

import json


def message_text(payload: str, kind: str) -> str:
    """Returns displayed text, excluding tools, reasoning, and metadata."""
    if kind not in {"user", "assistant"}:
        return ""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return ""
    if not isinstance(data, dict):
        return ""
    texts = [data["text"]] if isinstance(data.get("text"), str) else []
    content = data.get("content")
    if isinstance(content, list):
        texts.extend(
            part["text"]
            for part in content
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )
    return "\n".join(texts)


def excerpt(text: str, query: str) -> str:
    """Returns a small preview around the first match without altering storage."""
    position = text.lower().find(query.lower())
    start = max(0, position - 60)
    end = min(len(text), max(start + 240, position + len(query)))
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
