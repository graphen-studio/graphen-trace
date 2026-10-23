"""Contracts shared by capture adapters and their runtime factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from graphen_trace.config.settings import Settings
    from graphen_trace.services.discovery import AgentInstallation
    from graphen_trace.services.storage import Storage


class SyncCollector(Protocol):
    """One polling collector managed by the local service."""

    agent_name: str
    status: dict

    def sync(self) -> int:
        """Synchronizes source observations and returns changed sessions."""


class LiveCollector(Protocol):
    """Optional event-stream collector managed alongside session polling."""

    status: dict

    async def run(self) -> None:
        """Runs until cancelled or the source stream ends."""


class CaptureAdapter(Protocol):
    """Describes an installed agent and builds its capture runtime."""

    agent_name: str
    implemented: bool

    def supports(self, installation: AgentInstallation) -> bool:
        """Returns whether an installation is supported by this adapter."""

    def create_runtime(
        self,
        installation: AgentInstallation,
        settings: Settings,
        storage: Storage,
    ) -> AdapterRuntime:
        """Creates the collectors required for one installed agent."""


@dataclass(frozen=True)
class AdapterRuntime:
    """Collecting components created by one adapter factory."""

    collector: SyncCollector
    live_collector: LiveCollector | None = None
