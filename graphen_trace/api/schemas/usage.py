"""Token usage response contracts."""

from pydantic import BaseModel


class TokenUsage(BaseModel):
    """Usage values with unknown values represented as ``None``."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    source: str | None = None
