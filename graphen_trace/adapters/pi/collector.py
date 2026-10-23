"""Incremental session projection for Pi's local JSONL files."""

from datetime import datetime, timezone

from graphen_trace.adapters.pi import normalize
from graphen_trace.adapters.pi.source import PiSource
from graphen_trace.services.storage import Storage

SOURCE = "pi:session-jsonl:v1"
AGENT = "pi"
COVERAGE = "Local Pi session files; live-event coverage is unavailable"


class PiCollector:
    """Imports changed Pi sessions while preserving native message records."""

    agent_name = AGENT

    def __init__(self, source: PiSource, storage: Storage) -> None:
        self.source = source
        self.storage = storage
        self.status = {
            "state": "starting",
            "last_seen": None,
            "detail": COVERAGE,
        }

    def sync(self) -> int:
        """Synchronizes changed session files and removes missing source sessions."""
        sessions = self.source.sessions()
        live_ids = {session["id"] for session in sessions}
        revisions = self.storage.revisions(SOURCE, AGENT)
        records = [
            normalize.normalize_session(session)
            for session in sessions
            if revisions.get(session["id"]) != normalize.revision(session)
        ]
        self.storage.apply(SOURCE, records, live_ids, agent=AGENT)

        warnings = sorted(
            set(
                self.source.warnings
                + self.storage.normalization_warnings(SOURCE, AGENT)
            )
        )
        self.status.update(
            state="partial" if warnings else "collecting",
            last_seen=datetime.now(timezone.utc).isoformat(),
            detail=COVERAGE,
            warnings=warnings,
            version=self.source.version,
            capabilities=self.source.capabilities,
            agent=AGENT,
            source=SOURCE,
        )
        return len(records)
