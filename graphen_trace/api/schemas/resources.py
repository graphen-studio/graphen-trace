"""Agent resource discovery response contracts."""

from typing import Literal

from pydantic import BaseModel


class AgentSupportResponse(BaseModel):
    """An agent that can discover a skill from its location."""

    id: str
    name: str


class AgentResourceResponse(BaseModel):
    """A unique discovered skill or steering document."""

    kind: Literal["skill", "steering"]
    name: str
    description: str
    scope: str
    path: str
    content: str
    agents: list[AgentSupportResponse]


class AgentResourceListResponse(BaseModel):
    """Unique local resources discovered across supported agents."""

    items: list[AgentResourceResponse]
