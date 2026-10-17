"""OpenCode installation metadata."""

from dataclasses import dataclass

from graphen_trace.services.discovery import AgentInstallation


@dataclass(frozen=True)
class OpenCodeAdapter:
    """Declares the initial OpenCode capture capability."""

    agent_name: str = "opencode"
    capture_sources: tuple[str, ...] = ("local database", "local API/SSE")
    implemented: bool = False

    def supports(self, installation: AgentInstallation) -> bool:
        """Returns whether an installation belongs to OpenCode."""
        return installation.name == self.agent_name
