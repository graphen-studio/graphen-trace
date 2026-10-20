"""Read-only OpenCode V2 SQLite source."""

import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class UnsupportedSourceError(ValueError):
    """The installed version or database contract has not been validated."""


class OpenCodeSource:
    """Reads the V2 session projection without touching legacy message tables."""

    def __init__(self, path: Path, version: str) -> None:
        self.path = path.resolve()
        match = re.fullmatch(r"(?:opencode\s+)?v?(\d+\.\d+\.\d+)", version.strip())
        self.version = match.group(1) if match else version
        self.warnings: list[str] = []
        self.capabilities: dict[str, bool] = {}
        self.message_columns: set[str] = set()
        self.needs_full_refresh = False

    @contextmanager
    def snapshot(self) -> Iterator[sqlite3.Connection]:
        """Opens a consistent read-only transaction, including active WAL changes."""

        connection = sqlite3.connect(f"{self.path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            self._validate(connection)
            yield connection
        finally:
            connection.close()

    def _validate(self, connection: sqlite3.Connection) -> None:
        """Enables each capability from structural contracts, not exact versions."""

        self.warnings = []
        if self.version != "2.0.32":
            self.warnings.append(
                f"OpenCode {self.version or 'unknown'} is not a validated version; "
                "collection uses the detected structural contracts"
            )

        session_columns = self._columns(connection, "session_v2")
        if "id" not in session_columns:
            raise UnsupportedSourceError(
                "No readable session_v2 identifier; the V2 reader cannot interpret "
                "this dialect. Previously captured data remains available."
            )

        optional = {"title", "directory", "parent_id", "version", "time_updated"}
        missing = optional - session_columns
        if missing:
            self.warnings.append(
                "Unavailable session fields: " + ", ".join(sorted(missing))
            )

        self.message_columns = self._columns(connection, "session_message")
        messages = {"id", "session_id"}.issubset(self.message_columns)
        self.capabilities = {
            "sessions": True,
            "messages": messages,
            "message_payload": messages and "data" in self.message_columns,
            "native_order": messages and "seq" in self.message_columns,
        }
        self.needs_full_refresh = (
            messages and "time_updated" not in self.message_columns
        )
        if not messages:
            self.warnings.append(
                "Message schema unavailable; sessions remain readable. "
                "Previously captured message details may be stale."
            )
        elif not {"data", "type", "seq", "time_created", "time_updated"}.issubset(
            self.message_columns
        ):
            self.warnings.append(
                "Partial message metadata; unknown order/types are not inferred. "
                "Messages without update timestamps are refreshed each cycle."
            )

    def _columns(self, connection: sqlite3.Connection, table: str) -> set[str]:
        """Reads column names using a bound schema query."""

        return {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM pragma_table_info(?)",
                (table,),
            )
        }

    def session_index(self, connection: sqlite3.Connection) -> list[dict]:
        """Reads lightweight revisions, including edits and message deletions."""

        if not self.capabilities["messages"]:
            return [
                {
                    **dict(row),
                    "message_count": None,
                    "message_seq": None,
                    "message_updated": None,
                    "_message_schema": "unavailable",
                }
                for row in connection.execute("SELECT * FROM session_v2 ORDER BY id")
            ]
        sequence = "max(m.seq)" if "seq" in self.message_columns else "NULL"
        updated = (
            "max(m.time_updated)" if "time_updated" in self.message_columns else "NULL"
        )
        rows = connection.execute(
            "SELECT s.*, count(m.id) AS message_count, "
            f"{sequence} AS message_seq, {updated} AS message_updated "
            "FROM session_v2 s LEFT JOIN session_message m ON m.session_id = s.id "
            "GROUP BY s.id ORDER BY s.id"
        ).fetchall()
        return [
            {**dict(row), "_message_schema": ",".join(sorted(self.message_columns))}
            for row in rows
        ]

    def messages(self, connection: sqlite3.Connection, session_id: str) -> list:
        """Reads messages only for a session whose revision has changed."""

        if not self.capabilities["messages"]:
            return []
        order = "seq, id" if "seq" in self.message_columns else "id"
        return [
            dict(row)
            for row in connection.execute(
                f"SELECT * FROM session_message WHERE session_id = ? ORDER BY {order}",
                (session_id,),
            )
        ]
