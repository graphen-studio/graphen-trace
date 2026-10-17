"""Session response contracts."""

from pydantic import BaseModel


class SessionSummary(BaseModel):
    """Summary metadata for one agent session."""

    id: str
    agent: str
    title: str | None = None
    updated_at: str | None = None


class SessionListResponse(BaseModel):
    """Collection of observed sessions."""

    items: list[SessionSummary]
