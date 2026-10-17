"""Dashboard session endpoints."""

from fastapi import APIRouter

from graphen_trace.api.schemas.sessions import SessionListResponse

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """Returns currently collected sessions."""
    return SessionListResponse(items=[])
