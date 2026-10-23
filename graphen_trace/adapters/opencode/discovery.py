"""OpenCode installation metadata."""

from dataclasses import dataclass

from graphen_trace.adapters.base import AdapterRuntime
from graphen_trace.adapters.opencode.source import OpenCodeSource
from graphen_trace.config.settings import Settings
from graphen_trace.services.collector import Collector
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.live_collector import LiveCollector
from graphen_trace.services.storage import Storage


@dataclass(frozen=True)
class OpenCodeAdapter:
    """Declares the validated OpenCode capture capability."""

    agent_name: str = "opencode"
    capture_sources: tuple[str, ...] = ("local database", "local API/SSE")
    validated_versions: tuple[str, ...] = ("2.0.32",)
    implemented: bool = True

    def supports(self, installation: AgentInstallation) -> bool:
        """Returns whether an installation belongs to OpenCode."""
        return installation.name == self.agent_name

    def create_runtime(
        self,
        installation: AgentInstallation,
        settings: Settings,
        storage: Storage,
    ) -> AdapterRuntime:
        """Creates SQLite polling and optional live-event collectors."""
        source = OpenCodeSource(settings.opencode_database, installation.version or "")
        return AdapterRuntime(
            collector=Collector(source, storage),
            live_collector=LiveCollector(settings, storage),
        )
