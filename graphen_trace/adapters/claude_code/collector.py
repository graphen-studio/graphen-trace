"""Incremental projection of passive Claude Code snapshots."""

from datetime import datetime, timezone

from graphen_trace.adapters.claude_code import normalize
from graphen_trace.adapters.claude_code.source import ClaudeCodeSource
from graphen_trace.services.storage import Storage

COVERAGE = "Persisted local Claude Code transcripts; no live-event capture"


class ClaudeCodeCollector:
    """Imports complete snapshots and retains valid data during source failures."""

    agent_name = "claude"

    def __init__(self, source: ClaudeCodeSource, storage: Storage) -> None:
        self.source = source
        self.storage = storage
        self.status = {"state": "starting", "last_seen": None, "detail": COVERAGE}

    def sync(self) -> int:
        sessions = self.source.sessions()
        revisions = self.storage.revisions(normalize.SOURCE, self.agent_name)
        live_ids = {session["id"] for session in sessions}
        if self.source.snapshot_incomplete:
            live_ids.update(revisions)
        records = [
            normalize.normalize_session(session)
            for session in sessions
            if revisions.get(session["id"]) != normalize.revision(session)
        ]
        self.storage.apply(normalize.SOURCE, records, live_ids, agent=self.agent_name)
        warnings = sorted(set(self.source.warnings))
        self.status.update(
            state="partial" if warnings else "collecting",
            last_seen=datetime.now(timezone.utc).isoformat(),
            detail=COVERAGE,
            warnings=warnings,
            version=self.source.version,
            capabilities=self.source.capabilities,
            agent=self.agent_name,
            source=normalize.SOURCE,
        )
        return len(records)
