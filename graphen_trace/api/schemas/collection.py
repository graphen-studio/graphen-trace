"""Passive collector status contract."""

from typing import Literal

from pydantic import BaseModel, Field


class CollectionStatus(BaseModel):
    """Source synchronization state and declared coverage."""

    state: Literal[
        "not_started",
        "starting",
        "collecting",
        "partial",
        "unavailable",
        "not_detected",
    ]
    agent: str | None = None
    source: str | None = None
    last_seen: str | None = None
    detail: str
    warnings: list[str] = Field(default_factory=list)
    version: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)
