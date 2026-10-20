"""Queries for live observations persisted in Graphen storage."""

from fastapi import APIRouter, Query, Request

from graphen_trace.api.schemas.events import EventListResponse, LiveStatus

router = APIRouter()


@router.get("/events", response_model=EventListResponse)
def events(
    request: Request,
    session_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Returns events even when their session is not in the SQLite projection."""
    return request.app.state.storage.events(session_id, (limit, offset))


@router.get("/collection/live", response_model=LiveStatus)
def live_status(request: Request) -> dict:
    """Reports SSE health separately so polling success never hides live gaps."""

    collector = request.app.state.live_collector
    status = (
        collector.status
        if collector
        else {
            "state": "not_detected",
            "detail": "No compatible OpenCode collector",
            "last_seen": None,
            "possible_gap": True,
        }
    )
    return {**status, "history": request.app.state.storage.live_history()}
