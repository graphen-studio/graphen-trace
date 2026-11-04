"""Read-only reader for Kiro CLI and workspace session files."""

import hashlib
import json
import os
import re
from pathlib import Path

VALIDATED_VERSIONS = ("2.34.1", "2.37.0")


class KiroSource:
    """Reads local Kiro sessions without invoking or modifying the agent."""

    def __init__(
        self,
        sessions_dir: Path,
        version: str | None = None,
        workspace_sessions_dir: Path | None = None,
    ) -> None:
        self.sessions_dir = sessions_dir.expanduser().resolve()
        self.workspace_sessions_dir = (
            workspace_sessions_dir.expanduser().resolve()
            if workspace_sessions_dir is not None
            else self.sessions_dir.parent
        )
        self.version = version or "unknown"
        self.warnings: list[str] = []
        self.capabilities = {
            "sessions": True,
            "messages": True,
            "native_order": False,
            "model_metadata": True,
            "token_usage": True,
            "live_events": False,
            "workspace_sessions": True,
        }
        self._cache: dict[
            Path, tuple[tuple[int, int, int, int], str, dict, list[str], bool]
        ] = {}
        self.snapshot_incomplete = False

    def sessions(self) -> list[dict]:
        """Reads CLI session files and computes content-based revisions."""
        self.warnings = []
        self.snapshot_incomplete = False
        version_match = re.search(r"\b(\d+\.\d+\.\d+)\b", self.version)
        version = version_match.group(1) if version_match else None
        if version not in VALIDATED_VERSIONS:
            self.warnings.append(
                f"Kiro CLI {version or self.version} is not a validated version; "
                "collection will use detected structural contracts"
            )
        if not self.sessions_dir.is_dir() and not self.workspace_sessions_dir.is_dir():
            raise FileNotFoundError("Kiro CLI sessions directory not found")

        metadata_paths = (
            [(path, "cli") for path in sorted(self.sessions_dir.glob("*.json"))]
            if self.sessions_dir.is_dir()
            else []
        )
        metadata_paths.extend(
            (path, "workspace")
            for path in sorted(
                self.workspace_sessions_dir.glob("*/sess_*/session.json")
            )
        )
        valid_paths = {path for path, _ in metadata_paths}
        self._cache = {
            path: cached for path, cached in self._cache.items() if path in valid_paths
        }
        sessions = []
        for metadata_path, layout in metadata_paths:
            session = self._read_session(metadata_path, layout)
            if session is not None:
                sessions.append(session)
        return sessions

    def _read_session(self, metadata_path: Path, layout: str) -> dict | None:
        """Reads one metadata/transcript pair, preserving its native records."""
        transcript_path = (
            metadata_path.with_suffix(".jsonl")
            if layout == "cli"
            else metadata_path.with_name("messages.jsonl")
        )
        try:
            fingerprint = _fingerprint(metadata_path.stat())
            transcript_fingerprint = (
                _fingerprint(transcript_path.stat())
                if transcript_path.exists()
                else None
            )
            subexecution_paths = (
                sorted((metadata_path.parent / "sub-executions").glob("*.jsonl"))
                if layout == "workspace"
                else []
            )
            subexecution_fingerprints = [
                (path.name, _fingerprint(path.stat())) for path in subexecution_paths
            ]
        except OSError as error:
            self.snapshot_incomplete = True
            self.warnings.append(
                f"Could not inspect Kiro session files for {metadata_path.name} "
                f"({type(error).__name__})"
            )
            return None
        cache_key = (
            f"{layout}:{fingerprint}:{transcript_fingerprint}:"
            f"{subexecution_fingerprints}:{self.version}"
        )
        cached = self._cache.get(metadata_path)
        if cached is not None and cached[1] == cache_key:
            self.warnings.extend(cached[3])
            self.snapshot_incomplete |= cached[4]
            return cached[2]

        warning_start = len(self.warnings)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self.snapshot_incomplete = True
            self.warnings.append(
                f"Ignored unreadable Kiro CLI session metadata file "
                f"{metadata_path.name} ({type(error).__name__})"
            )
            return None
        if not isinstance(metadata, dict):
            self.snapshot_incomplete = True
            self.warnings.append(
                f"Ignored Kiro CLI session metadata file {metadata_path.name}: "
                "expected a JSON object"
            )
            return None

        session_id = (
            metadata.get("session_id") if layout == "cli" else metadata.get("id")
        )
        if not isinstance(session_id, str) or not session_id:
            session_id = (
                metadata_path.stem
                if layout == "cli"
                else metadata_path.parent.name.removeprefix("sess_")
            )
            self.warnings.append(
                f"Kiro CLI metadata {metadata_path.name} has no session_id; "
                "using its filename"
            )

        records = []
        session_incomplete = False
        transcript_source = "payload" if layout == "workspace" else "kind"
        if transcript_path.exists():
            records, session_incomplete = self._read_jsonl(
                transcript_path, "transcript"
            )
        else:
            session_incomplete = True
            self.warnings.append(
                f"Kiro CLI transcript is unavailable for {metadata_path.name}"
            )

        subexecutions = []
        for path in subexecution_paths:
            child_records, child_incomplete = self._read_jsonl(path, "sub-execution")
            session_incomplete |= child_incomplete
            subexecutions.append({"id": path.stem, "records": child_records})

        expected_subexecutions = _subexecution_ids(records)
        found_subexecutions = {item["id"] for item in subexecutions}
        missing_subexecutions = expected_subexecutions - found_subexecutions
        if missing_subexecutions:
            session_incomplete = True
            self.warnings.append(
                f"{len(missing_subexecutions)} Kiro sub-execution transcript(s) "
                "referenced by the session are unavailable"
            )
        self.snapshot_incomplete |= session_incomplete

        digest = hashlib.sha256()
        digest.update(self.version.encode("utf-8"))
        digest.update(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode())
        for record in records:
            digest.update(
                json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
            )
        for subexecution in subexecutions:
            digest.update(subexecution["id"].encode("utf-8"))
            for record in subexecution["records"]:
                digest.update(
                    json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
                )
        source = (
            "kiro-cli:session-jsonl:v1"
            if layout == "cli"
            else "kiro-workspace:session-jsonl:v1"
        )
        session = {
            "id": f"{layout}:{session_id}",
            "native_id": session_id,
            "metadata": metadata,
            "records": records,
            "subexecutions": subexecutions,
            "layout": layout,
            "source": source,
            "transcript_envelope": transcript_source,
            "snapshot_incomplete": session_incomplete,
            "agent_version": self.version,
            "revision": f"kiro-cli-jsonl-v1:{digest.hexdigest()}",
        }
        self._cache[metadata_path] = (
            fingerprint,
            cache_key,
            session,
            self.warnings[warning_start:],
            session_incomplete,
        )
        return session

    def _read_jsonl(self, path: Path, description: str) -> tuple[list[dict], bool]:
        """Reads valid JSON object records and flags incomplete snapshots."""
        records = []
        incomplete = False
        try:
            with path.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, start=1):
                    try:
                        envelope = json.loads(line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        incomplete = True
                        self.warnings.append(
                            f"Ignored invalid Kiro {description} JSONL record in "
                            f"{path.name} at line {line_number}"
                        )
                        continue
                    if not isinstance(envelope, dict):
                        incomplete = True
                        self.warnings.append(
                            f"Ignored non-object Kiro {description} JSONL record in "
                            f"{path.name} at line {line_number}"
                        )
                        continue
                    records.append(envelope)
        except (OSError, UnicodeDecodeError) as error:
            incomplete = True
            self.warnings.append(
                f"Could not read Kiro {description} {path.name} "
                f"({type(error).__name__})"
            )
        return records, incomplete


def _fingerprint(stat: os.stat_result) -> tuple[int, int, int, int]:
    """Builds a fast cache key while content hashes provide revision accuracy."""
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _subexecution_ids(records: list[dict]) -> set[str]:
    """Collects child transcript IDs referenced by parent lifecycle events."""
    identifiers = set()
    for record in records:
        payload = record.get("payload")
        if isinstance(payload, dict):
            event_type, data = payload.get("type"), payload
        else:
            event_type, data = record.get("kind"), record.get("data")
        if event_type not in {"sub_agent_start", "subagent_start"} or not isinstance(
            data, dict
        ):
            continue
        identifier = data.get("subSessionId") or data.get("subExecutionId")
        if isinstance(identifier, str) and identifier:
            identifiers.add(identifier)
    return identifiers
