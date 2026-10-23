"""Dashboard session endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from graphen_trace.adapters.opencode import normalize
from graphen_trace.adapters.pi import normalize as pi_normalize
from graphen_trace.api.schemas.collection import CollectionStatus
from graphen_trace.api.schemas.sessions import SessionDetail, SessionListResponse
from graphen_trace.api.schemas.timeline import SessionSearchResponse, TimelineResponse

router = APIRouter()


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    agent: str = Query(default="opencode", min_length=1),
    source: str | None = None,
) -> SessionListResponse:
    """Returns currently collected sessions."""

    records = request.app.state.storage.sessions(limit, offset, agent, source)
    return SessionListResponse(items=records)


@router.get("/collection", response_model=CollectionStatus)
def collection_status(request: Request) -> dict:
    """Reports the selected collector or the initial idle state."""

    return request.app.state.collection_manager.status


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_details(
    session_id: str,
    request: Request,
    agent: str = Query(default="opencode", min_length=1),
    source: str | None = Query(default=None, min_length=1),
) -> dict:
    """Returns stored session metadata, or 404 when it has not been observed."""

    source = source or _default_source(agent)
    session = request.app.state.storage.session(session_id, source, agent)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
def session_timeline(
    session_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    agent: str = Query(default="opencode", min_length=1),
    source: str | None = Query(default=None, min_length=1),
    latest: bool = False,
) -> dict:
    """Returns the persisted timeline with full native message content."""

    source = source or _default_source(agent)
    session_details(session_id, request, agent, source)
    page = request.app.state.storage.timeline(
        session_id, (limit, offset), source, agent, latest=latest
    )
    if agent == "opencode":
        page["items"] = normalize.normalize_timeline(page["items"])
        for item in page["items"]:
            item.update(agent=agent, source=source)
    elif agent == "pi":
        page["items"] = pi_normalize.normalize_timeline_rows(page["items"])
        for item in page["items"]:
            item.update(agent=agent, source=source)
    else:
        page["items"] = [
            {**message, "agent": agent, "source": source} for message in page["items"]
        ]
    return page


@router.get("/sessions/{session_id}/search", response_model=SessionSearchResponse)
def search_session(
    session_id: str,
    request: Request,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    agent: str = Query(default="opencode", min_length=1),
    source: str | None = Query(default=None, min_length=1),
) -> dict:
    """Searches literal text in all captured prompts and responses of a session."""
    source = source or _default_source(agent)
    session_details(session_id, request, agent, source)
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search text must not be blank")
    if agent not in {"opencode", "pi"}:
        raise HTTPException(
            status_code=409, detail="Text search not supported for agent"
        )
    return request.app.state.storage.search_messages(
        session_id, query, (limit, offset), source, agent
    )


def _default_source(agent: str) -> str:
    """Returns the first-party source identifier for a selected agent."""
    if agent == "opencode":
        return "opencode:sqlite:v2"
    if agent == "pi":
        return "pi:session-jsonl:v1"
    return f"{agent}:sqlite"
