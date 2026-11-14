"""Dashboard session endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from graphen_trace.adapters.claude_code import normalize as claude_normalize
from graphen_trace.adapters.kiro import normalize as kiro_normalize
from graphen_trace.adapters.opencode import normalize
from graphen_trace.adapters.pi import normalize as pi_normalize
from graphen_trace.api.schemas.collection import CollectionStatus
from graphen_trace.api.schemas.sessions import SessionDetail, SessionListResponse
from graphen_trace.api.schemas.timeline import SessionSearchResponse, TimelineResponse

router = APIRouter()
TIMELINE_NORMALIZERS = {
    "opencode": normalize.normalize_timeline,
    "pi": pi_normalize.normalize_timeline_rows,
    "kiro": kiro_normalize.normalize_timeline_rows,
    "claude": claude_normalize.normalize_timeline_rows,
}


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

    if source is None and agent == "kiro":
        session = next(
            (
                candidate
                for candidate_source in (
                    kiro_normalize.SOURCE,
                    kiro_normalize.WORKSPACE_SOURCE,
                )
                if (
                    candidate := request.app.state.storage.session(
                        session_id, candidate_source, agent
                    )
                )
                is not None
            ),
            None,
        )
    else:
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

    session = session_details(session_id, request, agent, source)
    source = source or session["source"]
    if agent == "claude":
        # Tool results and UUID updates may be outside the requested page.
        page = request.app.state.storage.timeline(session_id, (-1, 0), source, agent)
        if latest:
            offset = max(0, (page["total"] - 1) // limit) * limit
        page["offset"] = offset
    else:
        page = request.app.state.storage.timeline(
            session_id, (limit, offset), source, agent, latest=latest
        )

    normalizer = TIMELINE_NORMALIZERS.get(agent)
    if normalizer is not None:
        page["items"] = normalizer(page["items"])
    if agent == "claude":
        page["items"] = page["items"][offset : offset + limit]
    page["items"] = [
        {**item, "agent": agent, "source": source} for item in page["items"]
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
    session = session_details(session_id, request, agent, source)
    source = source or session["source"]
    query = q.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Search text must not be blank")
    if agent not in {"opencode", "pi", "kiro", "claude"}:
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
    if agent == "claude":
        return claude_normalize.SOURCE
    if agent == "kiro":
        return "kiro-cli:session-jsonl:v1"
    return f"{agent}:sqlite"
