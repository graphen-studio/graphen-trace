"""Health endpoint."""

from fastapi import APIRouter

from graphen_trace.__version__ import __version__
from graphen_trace.api.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Returns service health and version."""
    return HealthResponse(status="ok", version=__version__)
