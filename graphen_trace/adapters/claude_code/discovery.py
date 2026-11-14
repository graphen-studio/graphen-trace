"""Claude Code adapter metadata and runtime construction."""

from dataclasses import dataclass

from graphen_trace.adapters.base import AdapterRuntime
from graphen_trace.adapters.claude_code.collector import ClaudeCodeCollector
from graphen_trace.adapters.claude_code.source import ClaudeCodeSource
from graphen_trace.config.settings import Settings
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.storage import Storage


@dataclass(frozen=True)
class ClaudeCodeAdapter:
    """Declares passive transcript support, without a version compatibility claim."""

    agent_name: str = "claude"
    capture_sources: tuple[str, ...] = ("local project JSONL transcripts",)
    validated_versions: tuple[str, ...] = ()
    implemented: bool = True

    def supports(self, installation: AgentInstallation) -> bool:
        return installation.name == self.agent_name

    def create_runtime(
        self, installation: AgentInstallation, settings: Settings, storage: Storage
    ) -> AdapterRuntime:
        source = ClaudeCodeSource(settings.claude_projects_dir, installation.version)
        return AdapterRuntime(collector=ClaudeCodeCollector(source, storage))
