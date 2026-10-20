"""FastAPI application factory."""

from fastapi import FastAPI

from graphen_trace.api.lifecycle import lifespan
from graphen_trace.api.routes import events, frontend, health
from graphen_trace.api.routes import proxy as proxy_routes
from graphen_trace.api.routes import sessions, usage


def create_app(proxy_enabled: bool = False) -> FastAPI:
    """Creates the FastAPI application and registers its routes."""

    app = FastAPI(title="Graphen Trace", lifespan=lifespan)

    app.state.proxy_enabled = proxy_enabled
    app.include_router(health.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(usage.router, prefix="/api")

    if proxy_enabled:
        app.include_router(proxy_routes.router, prefix="/v1")

    app.include_router(frontend.router)

    return app
