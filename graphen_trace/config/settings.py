"""Runtime settings for the local Graphen Trace service."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Local network and provider proxy settings."""

    host: str = os.getenv("GRAPHEN_TRACE_HOST", "127.0.0.1")
    port: int = int(os.getenv("GRAPHEN_TRACE_PORT", "8765"))
    openai_upstream: str = os.getenv(
        "GRAPHEN_TRACE_OPENAI_UPSTREAM", "https://api.openai.com"
    )


settings = Settings()
