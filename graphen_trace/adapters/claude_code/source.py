"""Read-only snapshots of Claude Code project transcripts."""

import hashlib
import json
from pathlib import Path


class ClaudeCodeSource:
    """Reads project JSONL files without consulting settings or authentication."""

    def __init__(self, projects_dir: Path, version: str | None = None) -> None:
        self.projects_dir = projects_dir.expanduser().resolve()
        self.version = version or "unknown"
        self.warnings: list[str] = []
        self.snapshot_incomplete = False
        self.capabilities = {
            "sessions": True,
            "messages": True,
            "native_order": False,
            "live_events": False,
        }

    def sessions(self) -> list[dict]:
        """Reads fresh snapshots; incomplete files never replace valid projections."""
        self.warnings = []
        self.snapshot_incomplete = False
        if not self.projects_dir.is_dir():
            raise FileNotFoundError("Claude Code projects directory is unavailable")
        try:
            # Only the documented workspace/session layout is ingested.
            paths = []
            for workspace in self.projects_dir.iterdir():
                if workspace.is_symlink():
                    self._warn("Ignored a symbolic link in Claude Code projects")
                    continue
                if not workspace.is_dir():
                    continue
                for path in workspace.iterdir():
                    if path.suffix != ".jsonl":
                        continue
                    if path.is_symlink():
                        self._warn("Ignored a symbolic link in Claude Code projects")
                    elif path.is_file():
                        paths.append(path)
        except OSError:
            self._warn("Claude Code transcript discovery is incomplete")
            return []
        sessions = []
        identities: set[str] = set()
        conflicts: set[str] = set()
        for path in sorted(paths):
            if path.is_symlink() or path.parent.is_symlink():
                self._warn("Ignored a symbolic link in Claude Code projects")
                continue
            session = self._read_session(path)
            if session is None:
                continue
            if session["id"] in identities:
                conflicts.add(session["id"])
                self._warn("Conflicting Claude Code transcript identities")
            identities.add(session["id"])
            sessions.append(session)
        return [session for session in sessions if session["id"] not in conflicts]

    def _warn(self, warning: str) -> None:
        self.snapshot_incomplete = True
        self.warnings.append(warning)

    def _read_session(self, path: Path) -> dict | None:
        records = []
        invalid = False
        digest = hashlib.sha256()
        try:
            before = path.stat()
            with path.open("rb") as stream:
                for line_number, line in enumerate(stream, start=1):
                    digest.update(line)
                    try:
                        record = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        record = None
                    if not isinstance(record, dict):
                        invalid = True
                        self._warn(
                            "Invalid Claude Code transcript record "
                            f"at line {line_number}"
                        )
                        continue
                    records.append(record)
            after = path.stat()
        except OSError:
            self._warn("A Claude Code transcript could not be read")
            return None
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            self._warn("A Claude Code transcript changed during reading")
            return None
        if invalid:
            return None
        identities = {
            record["sessionId"]
            for record in records
            if isinstance(record.get("sessionId"), str) and record["sessionId"]
        }
        if len(identities) != 1:
            self._warn("A Claude Code transcript has no unambiguous session identity")
            return None
        return {
            "id": identities.pop(),
            "records": records,
            "agent_version": self.version,
            "revision": digest.hexdigest() + ":" + self.version,
        }
