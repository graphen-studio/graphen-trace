"""Session response contracts."""

from pydantic import BaseModel, Field

from graphen_trace.api.schemas.usage import TokenUsage


class SessionSummary(BaseModel):
    """Summary metadata for one agent session."""

    id: str
    agent: str
    title: str | None = None
    updated_at: str | None = None
    directory: str | None = None
    parent_id: str | None = None
    version: str | None = None
    model: dict[str, str] | None = None
    source: str
    message_count: int | None
    usage: TokenUsage
    usage_incomplete: list[str] = Field(default_factory=list)
    generation_count: int | None = None
    reported_cost: float | None = None
    cost_incomplete: bool = False
    normalization_warnings: list[str] = Field(default_factory=list)


class SessionDetail(SessionSummary):
    """Selected session fields needed to navigate and investigate a trace."""


class SessionListResponse(BaseModel):
    """Collection of observed sessions."""

    items: list[SessionSummary]
