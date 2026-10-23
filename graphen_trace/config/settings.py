"""Runtime settings for the local Graphen Trace service."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Local network and provider proxy settings."""

    host: str = os.getenv("GRAPHEN_TRACE_HOST", "127.0.0.1")
    port: int = int(os.getenv("GRAPHEN_TRACE_PORT", "8765"))
    openai_upstream: str = os.getenv(
        "GRAPHEN_TRACE_OPENAI_UPSTREAM", "https://api.openai.com"
    )
    database_path: Path = Path(
        os.getenv(
            "GRAPHEN_TRACE_DATABASE",
            str(
                Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
                / "graphen-trace"
                / "trace.db"
            ),
        )
    ).expanduser()
    opencode_database: Path = Path(
        os.getenv(
            "GRAPHEN_TRACE_OPENCODE_DATABASE",
            str(
                Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share"))
                / "opencode"
                / "opencode.db"
            ),
        )
    ).expanduser()
    pi_sessions_dir: Path = Path(
        os.getenv(
            "GRAPHEN_TRACE_PI_SESSIONS_DIR",
            os.getenv(
                "PI_CODING_AGENT_SESSION_DIR",
                str(Path.home() / ".pi" / "agent" / "sessions"),
            ),
        )
    ).expanduser()
    poll_interval: float = 1.0
    opencode_service_file: Path = Path(
        os.getenv(
            "GRAPHEN_TRACE_OPENCODE_SERVICE_FILE",
            str(
                Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local/state"))
                / "opencode"
                / "service.json"
            ),
        )
    ).expanduser()
    opencode_url: str | None = os.getenv("GRAPHEN_TRACE_OPENCODE_URL")
    opencode_password: str | None = field(
        default=os.getenv("GRAPHEN_TRACE_OPENCODE_PASSWORD"),
        repr=False,
    )


settings = Settings()
