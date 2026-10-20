"""Contracts for persisted native OpenCode event envelopes."""

from pydantic import BaseModel, Field, JsonValue


class ObservedEvent(BaseModel):
    """An event observed on a single service instance, with full provenance."""

    id: str
    kind: str
    session_id: str | None
    observed_at: str
    created_at: float | None = None
    raw_data: dict[str, JsonValue]
    frame: dict[str, JsonValue]
    instance_id: str
    source: str
    normalization_warnings: list[str] = Field(default_factory=list)
    identity_source: str = "native"


class EventListResponse(BaseModel):
    """Paginated observed events; these are not additional token-usage records."""

    items: list[ObservedEvent]
    total: int


class ConnectionTransition(BaseModel):
    """One locally recorded connection boundary."""

    state: str
    observed_at: str


class LiveStatus(BaseModel):
    """Connection health does not imply historical or cross-instance coverage."""

    state: str
    detail: str
    last_seen: str | None = None
    possible_gap: bool
    history: list[ConnectionTransition] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
