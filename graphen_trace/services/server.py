"""Local FastAPI service lifecycle."""

import uvicorn

from graphen_trace.api.app import create_app
from graphen_trace.config.settings import settings


def create_server(proxy_enabled: bool = False) -> uvicorn.Server:
    """Creates a Uvicorn server with the selected proxy capability."""
    config = uvicorn.Config(
        create_app(proxy_enabled=proxy_enabled),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    return uvicorn.Server(config)


def run_server(proxy_enabled: bool = False) -> None:
    """Runs the local API until shutdown."""
    create_server(proxy_enabled=proxy_enabled).run()


def serve(proxy_enabled: bool = False) -> None:
    """Starts passive collection and serves the local dashboard."""
    run_server(proxy_enabled=proxy_enabled)
