"""Dashboard session endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from graphen_trace.api.schemas.collection import CollectionStatus
from graphen_trace.api.schemas.sessions import SessionDetail, SessionListResponse
from graphen_trace.api.schemas.timeline import TimelineResponse

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SessionListResponse:
    """Returns currently collected sessions."""

    records = request.app.state.storage.sessions(limit, offset)
    return SessionListResponse(items=records)


@router.get("/collection", response_model=CollectionStatus)
def collection_status(request: Request) -> dict:
    """Reports source availability and the limits of this collection stage."""

    collector = request.app.state.collector
    if collector is None:
        return {
            "state": "not_detected",
            "last_seen": None,
            "detail": "OpenCode not found",
        }
    return collector.status


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_details(session_id: str, request: Request) -> dict:
    """Returns stored session metadata, or 404 when it has not been observed."""

    session = request.app.state.storage.session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
def session_timeline(
    session_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Returns the persisted timeline with full native message content."""

    session_details(session_id, request)
    return request.app.state.storage.timeline(session_id, (limit, offset))
