"""Kiro CLI adapter registration and runtime construction."""

from dataclasses import dataclass

from graphen_trace.adapters.base import AdapterRuntime
from graphen_trace.adapters.kiro.collector import KiroCollector
from graphen_trace.adapters.kiro.source import VALIDATED_VERSIONS, KiroSource
from graphen_trace.config.settings import Settings
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


@dataclass(frozen=True)
class KiroAdapter:
    """Declares passive capture from locally persisted Kiro CLI sessions."""

    agent_name: str = "kiro"
    capture_sources: tuple[str, ...] = (
        "local Kiro CLI and workspace session JSON/JSONL files",
    )
    validated_versions: tuple[str, ...] = VALIDATED_VERSIONS
    implemented: bool = True

    def supports(self, installation: AgentInstallation) -> bool:
        """Returns whether an installation belongs to Kiro CLI."""
        return installation.name == self.agent_name

    def create_runtime(
        self,
        installation: AgentInstallation,
        settings: Settings,
        storage: Storage,
    ) -> AdapterRuntime:
        """Creates a read-only file collector for the selected Kiro installation."""
        source = KiroSource(
            settings.kiro_sessions_dir,
            installation.version,
            settings.kiro_workspace_sessions_dir,
        )
        return AdapterRuntime(collector=KiroCollector(source, storage))
