"""Pi installation metadata."""

from dataclasses import dataclass

from graphen_trace.adapters.base import AdapterRuntime
from graphen_trace.adapters.pi.collector import PiCollector
from graphen_trace.adapters.pi.source import PiSource
from graphen_trace.config.settings import Settings
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


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

    def create_runtime(
        self,
        installation: AgentInstallation,
        settings: Settings,
        storage: Storage,
    ) -> AdapterRuntime:
        """Creates a passive collector for Pi's local session files."""
        source = PiSource(settings.pi_sessions_dir, installation.version)
        return AdapterRuntime(collector=PiCollector(source, storage))
