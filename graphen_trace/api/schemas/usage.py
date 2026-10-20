"""Token usage response contracts."""

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Usage values with unknown values represented as ``None``."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    source: str | None = None


class UsageSummary(BaseModel):
    """Observed native totals with explicit incomplete-category coverage."""

    session_count: int
    generation_count: int | None
    usage: TokenUsage
    usage_incomplete: list[str] = Field(default_factory=list)
    reported_cost: float | None = None
    cost_incomplete: bool = False
    source: str = "opencode:sqlite:v2"
    agent: str = "opencode"
