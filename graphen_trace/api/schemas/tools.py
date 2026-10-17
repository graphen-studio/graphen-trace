"""Tool catalog and execution response contracts."""

from pydantic import BaseModel


class ToolSummary(BaseModel):
    """A tool definition or execution summary."""

    id: str
    name: str
    description: str | None = None
    status: str | None = None
    source: str
