"""Service startup, background synchronization, and graceful shutdown."""

import asyncio
import logging
import sqlite3
from contextlib import asynccontextmanager, suppress
from typing import AsyncIterator

from fastapi import FastAPI

from graphen_trace.adapters.opencode.source import OpenCodeSource
from graphen_trace.config.settings import settings
from graphen_trace.services.collector import Collector
from graphen_trace.services.discovery import discover_agents
from graphen_trace.services.live_collector import LiveCollector
from graphen_trace.services.storage import Storage

LOGGER = logging.getLogger(__name__)


async def _collect(collector: Collector, stop: asyncio.Event) -> None:
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
                LOGGER.warning("OpenCode collection unavailable: %s", error)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.poll_interval)
        except TimeoutError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initializes storage and starts the selected passive adapter."""

    if settings.database_path.resolve() == settings.opencode_database.resolve():
        raise ValueError("Graphen storage must not use the OpenCode source database")

    storage = Storage(settings.database_path)
    await asyncio.to_thread(storage.initialize)
    app.state.storage = storage

    agents = await asyncio.to_thread(discover_agents)
    installation = next((agent for agent in agents if agent.name == "opencode"), None)

    app.state.collector = None
    app.state.live_collector = None
    stop = asyncio.Event()
    task = None
    live_task = None

    if installation:
        source = OpenCodeSource(settings.opencode_database, installation.version or "")
        app.state.collector = Collector(source, storage)
        task = asyncio.create_task(_collect(app.state.collector, stop))
        app.state.live_collector = LiveCollector(settings, storage)
        live_task = asyncio.create_task(app.state.live_collector.run())

    try:
        yield
    finally:
        stop.set()
        if live_task:
            live_task.cancel()
            with suppress(asyncio.CancelledError):
                await live_task
        if task:
            await task
