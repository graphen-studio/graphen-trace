"""Common API response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health status returned by the service."""

    status: str
    version: str
