"""Agent resource discovery response contracts."""

from pydantic import BaseModel


class AgentSupportResponse(BaseModel):
    """An agent that can discover a skill from its location."""

    id: str
    name: str


class AgentSkillResponse(BaseModel):
    """A unique discovered skill and the agents that support it."""

    name: str
    description: str
    scope: str
    path: str
    content: str
    agents: list[AgentSupportResponse]


class AgentResourceListResponse(BaseModel):
    """Unique local resources discovered across supported agents."""

    items: list[AgentSkillResponse]
