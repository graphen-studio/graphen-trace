"""Incremental projection of Kiro CLI session files into Graphen storage."""

from datetime import datetime, timezone

from graphen_trace.adapters.kiro import normalize
from graphen_trace.adapters.kiro.source import KiroSource
from graphen_trace.services.storage import Storage

AGENT = "kiro"
COVERAGE = "Local CLI and workspace session files; workspace origin may be CLI or IDE"


class KiroCollector:
    """Imports changed Kiro CLI sessions and reconciles removed source files."""

    agent_name = AGENT

    def __init__(self, source: KiroSource, storage: Storage) -> None:
        self.source = source
        self.storage = storage
        self.status = {
            "state": "starting",
            "last_seen": None,
            "detail": COVERAGE,
        }

    def sync(self) -> int:
        """Applies changed file snapshots and updates collection health."""
        sessions = self.source.sessions()
        sessions_by_source: dict[str, list[dict]] = {}
        for session in sessions:
            if session.get("snapshot_incomplete"):
                continue
            sessions_by_source.setdefault(session["source"], []).append(session)
        changed = 0
        sources = {normalize.SOURCE, normalize.WORKSPACE_SOURCE}
        for source in sources:
            source_sessions = sessions_by_source.get(source, [])
            live_ids = {session["id"] for session in source_sessions}
            revisions = self.storage.revisions(source, AGENT)
            if self.source.snapshot_incomplete:
                live_ids.update(revisions)
            records = [
                normalize.normalize_session(session)
                for session in source_sessions
                if revisions.get(session["id"]) != normalize.revision(session)
            ]
            self.storage.apply(source, records, live_ids, agent=AGENT)
            changed += len(records)
        warnings = sorted(
            set(
                self.source.warnings
                + self.storage.normalization_warnings(normalize.SOURCE, AGENT)
                + self.storage.normalization_warnings(normalize.WORKSPACE_SOURCE, AGENT)
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
            source="kiro:local-session-files:v1",
        )
        return changed
