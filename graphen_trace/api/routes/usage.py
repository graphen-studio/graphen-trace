"""Observed consumption across all persisted sessions."""

from fastapi import APIRouter, Request

from graphen_trace.api.schemas.usage import UsageSummary

router = APIRouter()


@router.get("/usage", response_model=UsageSummary)
def usage_summary(request: Request) -> dict:
    """Returns native categories without mixing session and message aggregates."""
    return request.app.state.storage.usage()
