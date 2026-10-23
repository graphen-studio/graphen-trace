"""Agent resource discovery endpoints."""

from pathlib import Path

from fastapi import APIRouter, Request

from graphen_trace.api.schemas.resources import AgentResourceListResponse
from graphen_trace.services.resources import discover_resources

router = APIRouter()


@router.get("/resources", response_model=AgentResourceListResponse)
def list_resources(request: Request) -> dict:
    """Discovers skills on demand without persisting their contents."""
    project_directory = getattr(request.app.state, "project_directory", Path.cwd())
    return {"items": discover_resources(project_directory)}
