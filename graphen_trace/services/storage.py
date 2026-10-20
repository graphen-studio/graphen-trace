"""Persistence of captured OpenCode records in the Graphen SQLite database."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class Storage:
    """Stores normalized sessions and their synchronization revisions together."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Opens and closes a Graphen connection with transaction handling."""

        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Creates or upgrades storage for sessions and complete message records."""

        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)

        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2, 3):
                raise ValueError(f"Unsupported Graphen storage schema: {version}")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS observed_session ("
                "source TEXT NOT NULL, id TEXT NOT NULL, revision TEXT NOT NULL, "
                "data TEXT NOT NULL, PRIMARY KEY (source, id))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS observed_message ("
                "source TEXT NOT NULL, session_id TEXT NOT NULL, id TEXT NOT NULL, "
                "sequence INTEGER NOT NULL, data TEXT NOT NULL, "
                "PRIMARY KEY (source, session_id, id))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS observed_message_order "
                "ON observed_message (source, session_id, sequence, id)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS observed_event ("
                "id TEXT PRIMARY KEY, instance_id TEXT NOT NULL, session_id TEXT, "
                "kind TEXT NOT NULL, observed_at TEXT NOT NULL, data TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS observed_event_session "
                "ON observed_event (session_id, observed_at, id)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS live_connection ("
                "id INTEGER PRIMARY KEY, state TEXT NOT NULL, "
                "observed_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS observed_event_cursor ("
                "aggregate_id TEXT PRIMARY KEY, seq INTEGER NOT NULL)"
            )
            connection.execute("PRAGMA user_version = 3")

    def revisions(self, source: str) -> dict[str, str]:
        """Returns the last committed revision for each source session."""

        with self.connect() as connection:
            return dict(
                connection.execute(
                    "SELECT id, revision FROM observed_session WHERE source = ?",
                    (source,),
                )
            )

    def apply(self, source: str, records: list[dict], live_ids: set[str]) -> None:
        """Commits changed sessions and revisions, reconciling source deletions."""

        with self.connect() as connection:
            for record in records:
                summary = {
                    key: value for key, value in record.items() if key != "timeline"
                }
                connection.execute(
                    "INSERT INTO observed_session VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(source, id) DO UPDATE SET "
                    "revision=excluded.revision, data=excluded.data",
                    (source, record["id"], record["revision"], json.dumps(summary)),
                )
                if record.get("timeline") is not None:
                    connection.execute(
                        "DELETE FROM observed_message "
                        "WHERE source = ? AND session_id = ?",
                        (source, record["id"]),
                    )
                    connection.executemany(
                        "INSERT INTO observed_message VALUES (?, ?, ?, ?, ?)",
                        [
                            (
                                source,
                                record["id"],
                                item["id"],
                                (
                                    item["sequence"]
                                    if item["sequence"] is not None
                                    else position
                                ),
                                json.dumps(item),
                            )
                            for position, item in enumerate(record["timeline"])
                        ],
                    )
            stored = connection.execute(
                "SELECT id FROM observed_session WHERE source = ?",
                (source,),
            ).fetchall()
            connection.executemany(
                "DELETE FROM observed_session WHERE source = ? AND id = ?",
                [(source, row[0]) for row in stored if row[0] not in live_ids],
            )
            connection.execute(
                "DELETE FROM observed_message WHERE source = ? AND session_id NOT IN "
                "(SELECT id FROM observed_session WHERE source = ?)",
                (source, source),
            )

    def sessions(self, limit: int, offset: int) -> list[dict]:
        """Returns sessions ordered by their last source update."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT data FROM observed_session "
                "ORDER BY json_extract(data, '$.updated_at') DESC, id "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def session(self, session_id: str) -> dict | None:
        """Returns a single observed session without querying the agent database."""

        with self.connect() as connection:
            row = connection.execute(
                "SELECT data FROM observed_session WHERE id = ? AND source = ?",
                (session_id, "opencode:sqlite:v2"),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def timeline(self, session_id: str, page: tuple[int, int]) -> dict:
        """Returns a bounded page and count from a consistent Graphen snapshot."""

        limit, offset = page
        with self.connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute(
                "SELECT count(*) FROM observed_message WHERE session_id = ? "
                "AND source = ?",
                (session_id, "opencode:sqlite:v2"),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT data FROM observed_message WHERE session_id = ? AND source = ? "
                "ORDER BY sequence, id LIMIT ? OFFSET ?",
                (session_id, "opencode:sqlite:v2", limit, offset),
            ).fetchall()
        return {"items": [json.loads(row[0]) for row in rows], "total": total}

    def usage(self) -> dict:
        """Aggregates session projections once, without reading message payloads."""

        totals = {
            "session_count": 0,
            "generation_count": 0,
            "usage": {},
            "usage_incomplete": [],
            "reported_cost": None,
            "cost_incomplete": False,
            "source": "opencode:sqlite:v2",
        }
        incomplete = set()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT json_extract(data, '$.usage'), "
                "json_extract(data, '$.usage_incomplete'), "
                "json_extract(data, '$.generation_count'), "
                "json_extract(data, '$.reported_cost'), "
                "json_extract(data, '$.cost_incomplete') FROM observed_session "
                "WHERE source = ?",
                ("opencode:sqlite:v2",),
            )
            for usage, missing, generations, cost, cost_incomplete in rows:
                totals["session_count"] += 1
                if generations is None:
                    totals["generation_count"] = None
                elif totals["generation_count"] is not None:
                    totals["generation_count"] += generations
                incomplete.update(json.loads(missing or "[]"))
                for key, value in json.loads(usage or "{}").items():
                    if isinstance(value, int) and not isinstance(value, bool):
                        totals["usage"][key] = (totals["usage"].get(key) or 0) + value
                if cost is not None:
                    totals["reported_cost"] = (totals["reported_cost"] or 0) + cost
                totals["cost_incomplete"] |= bool(cost_incomplete)
        totals["usage_incomplete"] = sorted(incomplete)
        return totals

    def save_event(self, instance_id: str, event: dict) -> None:
        """Commits an event and its observed durable watermark together."""

        event = {**event, "source": "opencode:sse:v2", "instance_id": instance_id}
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO observed_event VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO NOTHING",
                (
                    event["id"],
                    instance_id,
                    event["session_id"],
                    event["kind"],
                    event["observed_at"],
                    json.dumps(event),
                ),
            )
            durable = event["raw_data"].get("durable")
            if isinstance(durable, dict):
                aggregate, sequence = durable.get("aggregateID"), durable.get("seq")
                if (
                    isinstance(aggregate, str)
                    and isinstance(sequence, int)
                    and not isinstance(sequence, bool)
                    and sequence >= 0
                ):
                    connection.execute(
                        "INSERT INTO observed_event_cursor VALUES (?, ?) "
                        "ON CONFLICT(aggregate_id) DO UPDATE SET "
                        "seq=max(seq, excluded.seq)",
                        (aggregate, sequence),
                    )

    def mark_live(self, state: str) -> None:
        """Persists connection transitions without implying recoverable SSE replay."""

        with self.connect() as connection:
            connection.execute(
                "INSERT INTO live_connection (state, observed_at) VALUES (?, ?)",
                (state, datetime.now(timezone.utc).isoformat()),
            )

    def events(self, session_id: str | None, page: tuple[int, int]) -> dict:
        """Returns events in observation order, separate from message usage."""

        limit, offset = page
        with self.connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute(
                "SELECT count(*) FROM observed_event WHERE (? IS NULL OR session_id=?)",
                (session_id, session_id),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT data FROM observed_event WHERE (? IS NULL OR session_id=?) "
                "ORDER BY observed_at, id LIMIT ? OFFSET ?",
                (session_id, session_id, limit, offset),
            ).fetchall()
        return {"items": [json.loads(row[0]) for row in rows], "total": total}

    def live_history(self) -> list[dict]:
        """Returns recent persisted connection transitions, including prior runs."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT state, observed_at FROM live_connection "
                "ORDER BY id DESC LIMIT 20"
            ).fetchall()
        return [{"state": row[0], "observed_at": row[1]} for row in rows]

    def normalization_warnings(self, source: str) -> list[str]:
        """Returns persistent per-record warnings, including unchanged sessions."""

        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT warning.value FROM observed_session s, "
                "json_each(json_extract(s.data, '$.normalization_warnings')) warning "
                "WHERE s.source = ? ORDER BY warning.value",
                (source,),
            ).fetchall()
        return [row[0] for row in rows]
