"""Pi installation metadata."""

from dataclasses import dataclass

from graphen_trace.services.discovery import AgentInstallation


@dataclass(frozen=True)
class PiAdapter:
    """Declares passive Pi session-file capture capability."""

    agent_name: str = "pi"
    capture_sources: tuple[str, ...] = ("local session JSONL files",)
    validated_versions: tuple[str, ...] = ("1.3.0", "1.4.0")
    implemented: bool = True

    def supports(self, installation: AgentInstallation) -> bool:
        """Returns whether an installation belongs to Pi."""
        return installation.name == self.agent_name
