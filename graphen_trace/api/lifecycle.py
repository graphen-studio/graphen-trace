"""Service startup, background synchronization, and graceful shutdown."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from graphen_trace.config.settings import settings
from graphen_trace.services.collection_manager import CollectionManager
from graphen_trace.services.discovery import discover_agents
from graphen_trace.services.storage import Storage


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initializes storage and exposes installed agents without collecting."""

    if settings.database_path.resolve() == settings.opencode_database.resolve():
        raise ValueError("Graphen storage must not use the OpenCode source database")

    storage = Storage(settings.database_path)
    await asyncio.to_thread(storage.initialize)
    app.state.storage = storage
    app.state.project_directory = Path.cwd()

    agents = await asyncio.to_thread(discover_agents)
    app.state.collection_manager = CollectionManager(agents, settings, storage)

    try:
        yield
    finally:
        await app.state.collection_manager.stop()
