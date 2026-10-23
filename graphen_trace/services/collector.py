"""Coordinates passive OpenCode collection and reports source coverage."""

from datetime import datetime, timezone

from graphen_trace.adapters.opencode import normalize
from graphen_trace.adapters.opencode.source import OpenCodeSource
from graphen_trace.services.storage import Storage

SOURCE = "opencode:sqlite:v2"
AGENT = "opencode"
COVERAGE = "Full SQLite capture; live-event coverage is reported separately"


class Collector:
    """Imports complete source records alongside normalized session projections."""

    agent_name = AGENT

    def __init__(self, source: OpenCodeSource, storage: Storage) -> None:
        self.source = source
        self.storage = storage
        self.status = {
            "state": "starting",
            "last_seen": None,
            "detail": COVERAGE,
        }

    def sync(self) -> int:
        """Synchronizes one consistent snapshot and commits its revisions."""

        revisions = self.storage.revisions(SOURCE, AGENT)
        records = []
        with self.source.snapshot() as connection:
            sessions = self.source.session_index(connection)
            for session in sessions:
                if not self.source.needs_full_refresh and revisions.get(
                    session["id"]
                ) == normalize.revision(session):
                    continue
                messages = self.source.messages(connection, session["id"])
                records.append(normalize.normalize_session(session, messages))
            self.storage.apply(
                SOURCE, records, {row["id"] for row in sessions}, agent=AGENT
            )

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
