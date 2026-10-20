"""Agent discovery and selection contracts."""

from pydantic import BaseModel


class AgentInstallationResponse(BaseModel):
    """An agent found on the local machine and its collection support."""

    name: str
    path: str
    version: str | None
    adapter: bool


class AgentListResponse(BaseModel):
    """Installed agents available to the local dashboard."""

    items: list[AgentInstallationResponse]


class CollectionStartRequest(BaseModel):
    """Requests passive collection for one installed agent."""

    agent: str
