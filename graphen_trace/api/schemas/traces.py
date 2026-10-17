"""Trace and event response contracts."""

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    """One observed event in an agent trace."""

    id: str
    session_id: str
    kind: str
    timestamp: str | None = None
    source: str
    payload: dict[str, object] = Field(default_factory=dict)
