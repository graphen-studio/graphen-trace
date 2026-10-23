"""Read-only reader for Pi session JSONL files."""

import hashlib
import json
import os
from pathlib import Path


class PiSource:
    """Reads Pi session records from a local sessions directory."""

    def __init__(self, sessions_dir: Path, version: str | None = None) -> None:
        self.sessions_dir = sessions_dir.expanduser().resolve()
        self.version = version or "unknown"
        self.warnings: list[str] = []
        self.capabilities = {
            "sessions": True,
            "messages": True,
            "native_order": False,
            "live_events": False,
        }
        self._cache: dict[Path, tuple[tuple[int, int, int, int], str, str, str]] = {}

    def sessions(self) -> list[dict]:
        """Reads complete session files and returns source records and revisions."""
        self.warnings = []
        if not self.sessions_dir.is_dir():
            raise FileNotFoundError(
                f"Pi sessions directory not found: {self.sessions_dir}"
            )

        paths = sorted(self.sessions_dir.rglob("*.jsonl"))
        path_set = set(paths)
        self._cache = {
            path: cached for path, cached in self._cache.items() if path in path_set
        }
        sessions = []
        for path in paths:
            session = self._read_session(path)
            if session is not None:
                sessions.append(session)
        return sessions

    def _read_session(self, path: Path) -> dict | None:
        """Reads one JSONL file, retaining every valid native record."""
        fingerprint = _fingerprint(path.stat())
        cached = self._cache.get(path)
        if (
            cached is not None
            and cached[0] == fingerprint
            and cached[1] == self.version
        ):
            return {"id": cached[2], "revision": cached[3]}

        records = []
        digest = hashlib.sha256()
        digest.update(self.version.encode("utf-8"))
        try:
            with path.open("rb") as stream:
                for line_number, raw_line in enumerate(stream, start=1):
                    digest.update(raw_line)
                    try:
                        record = json.loads(raw_line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        self.warnings.append(
                            f"Ignored invalid JSON in Pi session file {path.name} "
                            f"at line {line_number}"
                        )
                        continue
                    if isinstance(record, dict):
                        records.append(record)
        except OSError:
            raise

        header = next(
            (record for record in records if record.get("type") == "session"), None
        )
        if header is None or not isinstance(header.get("id"), str):
            self.warnings.append(
                f"Pi session file {path.name} has no recognizable session header"
            )
            return None

        messages = [record for record in records if record.get("type") == "message"]
        revision = "pi-jsonl-v1:" + digest.hexdigest()
        self._cache[path] = (fingerprint, self.version, header["id"], revision)
        return {
            "id": header["id"],
            "header": header,
            "agent_version": self.version,
            "messages": messages,
            "records": records,
            "path": str(path),
            "revision": revision,
        }


def _fingerprint(stat: os.stat_result) -> tuple[int, int, int, int]:
    """Builds a cheap cache key for unchanged session files."""
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns
