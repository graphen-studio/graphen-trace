"""FastAPI application factory and production frontend serving."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from graphen_trace.api.routes import health
from graphen_trace.api.routes import proxy as proxy_routes
from graphen_trace.api.routes import sessions


def create_app(proxy_enabled: bool = False) -> FastAPI:
    """Creates the dashboard API, optionally including the provider proxy."""
    app = FastAPI(title="Graphen Trace")
    app.state.proxy_enabled = proxy_enabled
    app.include_router(health.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    if proxy_enabled:
        app.include_router(proxy_routes.router, prefix="/v1")

    web_root = Path(__file__).resolve().parents[1] / "web" / "dist"

    @app.get("/{asset_path:path}", include_in_schema=False)
    async def frontend(asset_path: str) -> FileResponse:
        """Serves built frontend assets and the SPA fallback."""
        if asset_path == "api" or asset_path.startswith("api/"):
            raise HTTPException(status_code=404)
        if asset_path == "v1" or asset_path.startswith("v1/"):
            raise HTTPException(status_code=404)
        requested = (web_root / asset_path).resolve()
        if (
            web_root.resolve() not in requested.parents
            and requested != web_root.resolve()
        ):
            raise HTTPException(status_code=404)
        if requested.is_file():
            return FileResponse(requested)
        index = web_root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="Frontend build not found")

    return app
