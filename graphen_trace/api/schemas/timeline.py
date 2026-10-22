"""Session timeline response contracts."""

from pydantic import BaseModel, Field, JsonValue

from graphen_trace.api.schemas.usage import TokenUsage


class ToolExecution(BaseModel):
    """Execution metadata and native tool payloads."""

    id: str
    name: str | None = None
    status: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float | None = None
    exit_code: int | None = None
    child_session_id: str | None = None
    input: JsonValue = None
    output: JsonValue = None
    error: JsonValue = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class TimelineItem(BaseModel):
    """A native session message and any observed model/tool metadata."""

    id: str
    kind: str
    sequence: int | None
    interaction_id: str | None = None
    interaction_source: str | None = None
    created_at: str | None = None
    completed_at: str | None = None
    model: dict[str, str] | None = None
    finish: str | None = None
    usage: TokenUsage | None = None
    tools: list[ToolExecution] = Field(default_factory=list)
    source: str
    raw_data: dict[str, JsonValue] = Field(default_factory=dict)
    source_record: dict[str, JsonValue] = Field(default_factory=dict)
    reported_cost: float | None = None
    raw_payload: JsonValue = None
    normalization_warnings: list[str] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    """Paginated timeline in native sequence order."""

    items: list[TimelineItem]
    total: int
    offset: int = 0


class SessionSearchResult(BaseModel):
    """A matching message and its position in the complete timeline."""

    message_id: str
    kind: str
    timeline_offset: int
    excerpt: str


class SessionSearchResponse(BaseModel):
    """Matching messages, paginated independently of the conversation."""

    items: list[SessionSearchResult]
    total: int
