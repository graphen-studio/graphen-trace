"""Runtime selection and lifecycle of passive collection adapters."""

import asyncio
import contextlib
import logging
import sqlite3

from graphen_trace.adapters.opencode.source import OpenCodeSource
from graphen_trace.adapters.pi.collector import PiCollector
from graphen_trace.adapters.pi.source import PiSource
from graphen_trace.adapters.registry import ADAPTERS
from graphen_trace.config.settings import Settings
from graphen_trace.services.collector import Collector
from graphen_trace.services.discovery import AgentInstallation
from graphen_trace.services.live_collector import LiveCollector
from graphen_trace.services.storage import Storage

LOGGER = logging.getLogger(__name__)


class CollectionManager:
    """Starts at most one selected agent collector during a service run."""

    def __init__(
        self,
        agents: list[AgentInstallation],
        settings: Settings,
        storage: Storage,
    ) -> None:
        self.agents = agents
        self.settings = settings
        self.storage = storage
        self.collector: Collector | PiCollector | None = None
        self.live_collector: LiveCollector | None = None
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._live_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> dict:
        """Returns the selected collector status, or an idle status."""

        if self.collector is None:
            return {
                "state": "not_started",
                "agent": None,
                "source": None,
                "last_seen": None,
                "detail": "Select a supported agent to start passive collection",
                "warnings": [],
                "version": None,
                "capabilities": {},
            }
        return {**self.collector.status, "agent": self.collector.agent_name}

    async def start(self, agent_name: str) -> dict:
        """Selects an installed supported agent, switching collectors if needed."""

        async with self._lock:
            installation = next(
                (agent for agent in self.agents if agent.name == agent_name), None
            )
            if installation is None:
                raise LookupError(f"Agent is not installed: {agent_name}")
            if not installation.adapter or agent_name not in ADAPTERS:
                raise ValueError(
                    f"Agent does not have a collection adapter: {agent_name}"
                )

            if self.collector is not None and self.status["agent"] == agent_name:
                return self.status

            await self._stop_selected()

            if agent_name == "opencode":
                source = OpenCodeSource(
                    self.settings.opencode_database, installation.version or ""
                )
                self.collector = Collector(source, self.storage)
                self.live_collector = LiveCollector(self.settings, self.storage)
            elif agent_name == "pi":
                source = PiSource(self.settings.pi_sessions_dir, installation.version)
                self.collector = PiCollector(source, self.storage)
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(
                _collect(self.collector, self._stop, self.settings.poll_interval)
            )
            if self.live_collector is not None:
                self._live_task = asyncio.create_task(self.live_collector.run())
            return self.status

    async def stop(self) -> None:
        """Stops the selected collectors, waiting for their tasks to finish."""

        async with self._lock:
            await self._stop_selected()

    async def _stop_selected(self) -> None:
        self._stop.set()
        if self._live_task is not None:
            self._live_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._live_task
        if self._task is not None:
            await self._task
        self.collector = None
        self.live_collector = None
        self._task = None
        self._live_task = None


async def _collect(
    collector: Collector | PiCollector, stop: asyncio.Event, poll_interval: float
) -> None:
    """Runs bounded polling and keeps source failures visible without stopping API."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(collector.sync)
        except (OSError, ValueError, sqlite3.Error) as error:
            changed = collector.status["state"] != "unavailable" or (
                collector.status["detail"] != str(error)
            )
            collector.status.update(state="unavailable", detail=str(error))
            if changed:
                LOGGER.warning(
                    "%s collection unavailable: %s", collector.agent_name, error
                )
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval)
        except TimeoutError:
            pass
