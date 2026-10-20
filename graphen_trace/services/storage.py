"""Compact, agent-scoped persistence for Graphen Trace observations."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class Storage:
    """Stores one canonical native message/event payload per observation."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Opens and closes a short-lived Graphen SQLite connection."""
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Creates the clean schema; legacy databases must be explicitly reset."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path.touch(mode=0o600, exist_ok=True)
        self.path.chmod(0o600)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(
                    "Graphen storage schema is obsolete; remove the local Graphen "
                    "database to start a clean collection"
                )
            connection.executescript(
                "CREATE TABLE IF NOT EXISTS observed_session ("
                "agent TEXT NOT NULL, source TEXT NOT NULL, id TEXT NOT NULL, "
                "revision TEXT NOT NULL, data TEXT NOT NULL, "
                "PRIMARY KEY (agent, source, id));"
                "CREATE TABLE IF NOT EXISTS observed_message ("
                "agent TEXT NOT NULL, source TEXT NOT NULL, session_id TEXT NOT NULL, "
                "id TEXT NOT NULL, sequence INTEGER, kind TEXT, "
                "time_created INTEGER, time_updated INTEGER, data TEXT NOT NULL, "
                "PRIMARY KEY (agent, source, session_id, id));"
                "CREATE INDEX IF NOT EXISTS observed_message_order "
                "ON observed_message (agent, source, session_id, sequence, id);"
                "CREATE TABLE IF NOT EXISTS observed_event ("
                "agent TEXT NOT NULL, source TEXT NOT NULL, id TEXT NOT NULL, "
                "instance_id TEXT NOT NULL, session_id TEXT, kind TEXT NOT NULL, "
                "observed_at TEXT NOT NULL, data TEXT NOT NULL, "
                "PRIMARY KEY (agent, source, id));"
                "CREATE INDEX IF NOT EXISTS observed_event_session "
                "ON observed_event (agent, source, session_id, observed_at, id);"
                "CREATE TABLE IF NOT EXISTS observed_event_cursor ("
                "agent TEXT NOT NULL, source TEXT NOT NULL, "
                "aggregate_id TEXT NOT NULL, "
                "seq INTEGER NOT NULL, PRIMARY KEY (agent, source, aggregate_id));"
                "CREATE TABLE IF NOT EXISTS live_connection ("
                "id INTEGER PRIMARY KEY, agent TEXT NOT NULL, source TEXT NOT NULL, "
                "state TEXT NOT NULL, observed_at TEXT NOT NULL);"
                "PRAGMA user_version = 1;"
            )

    def revisions(self, source: str, agent: str = "opencode") -> dict[str, str]:
        """Returns committed revisions for one agent/source pair."""
        with self.connect() as connection:
            return dict(
                connection.execute(
                    "SELECT id, revision FROM observed_session "
                    "WHERE agent=? AND source=?",
                    (agent, source),
                )
            )

    def apply(
        self,
        source: str,
        records: list[dict],
        live_ids: set[str],
        agent: str = "opencode",
    ) -> None:
        """Stores session projections and original message payloads atomically."""
        with self.connect() as connection:
            for record in records:
                summary = {
                    key: value
                    for key, value in record.items()
                    if key not in {"timeline", "timeline_records"}
                }
                connection.execute(
                    "INSERT INTO observed_session VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(agent, source, id) DO UPDATE SET "
                    "revision=excluded.revision, data=excluded.data",
                    (
                        agent,
                        source,
                        record["id"],
                        record["revision"],
                        json.dumps(summary),
                    ),
                )
                if record.get("timeline_records") is not None:
                    connection.execute(
                        "DELETE FROM observed_message WHERE agent=? AND source=? "
                        "AND session_id=?",
                        (agent, source, record["id"]),
                    )
                    for message in record["timeline_records"]:
                        sequence = message.get("seq")
                        sequence = sequence if isinstance(sequence, int) else None
                        connection.execute(
                            "INSERT INTO observed_message "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                agent,
                                source,
                                record["id"],
                                message["id"],
                                sequence,
                                message.get("type"),
                                message.get("time_created"),
                                message.get("time_updated"),
                                _payload(message.get("data")),
                            ),
                        )
            existing = connection.execute(
                "SELECT id FROM observed_session WHERE agent=? AND source=?",
                (agent, source),
            ).fetchall()
            removed = [(row[0],) for row in existing if row[0] not in live_ids]
            connection.executemany(
                "DELETE FROM observed_message "
                "WHERE agent=? AND source=? AND session_id=?",
                [(agent, source, row[0]) for row in removed],
            )
            connection.executemany(
                "DELETE FROM observed_session WHERE agent=? AND source=? AND id=?",
                [(agent, source, row[0]) for row in removed],
            )

    def sessions(
        self,
        limit: int,
        offset: int,
        agent: str | None = "opencode",
        source: str | None = None,
    ) -> list[dict]:
        """Lists sessions filtered by agent and capture source."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT data FROM observed_session WHERE (? IS NULL OR agent=?) "
                "AND (? IS NULL OR source=?) "
                "ORDER BY json_extract(data, '$.updated_at') DESC, id LIMIT ? OFFSET ?",
                (agent, agent, source, source, limit, offset),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def session(
        self,
        session_id: str,
        source: str = "opencode:sqlite:v2",
        agent: str = "opencode",
    ) -> dict | None:
        """Looks up a session in its explicit agent/source namespace."""
        with self.connect() as connection:
            row = connection.execute(
                "SELECT data FROM observed_session WHERE agent=? AND source=? AND id=?",
                (agent, source, session_id),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def timeline(
        self,
        session_id: str,
        page: tuple[int, int],
        source: str = "opencode:sqlite:v2",
        agent: str = "opencode",
    ) -> dict:
        """Returns compact source rows; normalization happens at the API boundary."""
        limit, offset = page
        with self.connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute(
                "SELECT count(*) FROM observed_message "
                "WHERE agent=? AND source=? AND session_id=?",
                (agent, source, session_id),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT id, sequence, kind, time_created, time_updated, data "
                "FROM observed_message WHERE agent=? AND source=? AND session_id=? "
                "ORDER BY sequence, id LIMIT ? OFFSET ?",
                (agent, source, session_id, limit, offset),
            ).fetchall()
        return {
            "items": [
                dict(
                    zip(
                        ("id", "seq", "type", "time_created", "time_updated", "data"),
                        row,
                    )
                )
                for row in rows
            ],
            "total": total,
        }

    def usage(self, agent: str = "opencode") -> dict:
        """Aggregates session summaries for one agent, not list pagination."""
        totals = {
            "session_count": 0,
            "generation_count": 0,
            "usage": {},
            "usage_incomplete": [],
            "reported_cost": None,
            "cost_incomplete": False,
            "agent": agent,
            "source": f"{agent}:sqlite",
        }
        incomplete = set()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT data FROM observed_session WHERE agent=? AND source LIKE ?",
                (agent, f"{agent}:%sqlite%"),
            )
            for (payload,) in rows:
                record = json.loads(payload)
                totals["session_count"] += 1
                count = record.get("generation_count")
                if count is None:
                    totals["generation_count"] = None
                elif totals["generation_count"] is not None:
                    totals["generation_count"] += count
                incomplete.update(record.get("usage_incomplete", []))
                for key, value in record.get("usage", {}).items():
                    if isinstance(value, int) and not isinstance(value, bool):
                        totals["usage"][key] = (totals["usage"].get(key) or 0) + value
                cost = record.get("reported_cost")
                if cost is not None:
                    totals["reported_cost"] = (totals["reported_cost"] or 0) + cost
                totals["cost_incomplete"] |= bool(record.get("cost_incomplete"))
        totals["usage_incomplete"] = sorted(incomplete)
        return totals

    def save_event(
        self,
        instance_id: str,
        event: dict,
        source: str = "opencode:sse:v2",
        agent: str = "opencode",
    ) -> None:
        """Stores a single event payload, scoped so IDs cannot collide across agents."""
        payload = event.get("raw_data", {})
        stored = {
            "raw_data": payload,
            "created_at": event.get("created_at"),
            "normalization_warnings": event.get("normalization_warnings", []),
            "identity_source": event.get("identity_source", "native"),
        }
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO observed_event VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(agent, source, id) DO NOTHING",
                (
                    agent,
                    source,
                    event["id"],
                    instance_id,
                    event.get("session_id"),
                    event["kind"],
                    event["observed_at"],
                    json.dumps(stored),
                ),
            )
            durable = payload.get("durable") if isinstance(payload, dict) else None
            if isinstance(durable, dict):
                aggregate, sequence = durable.get("aggregateID"), durable.get("seq")
                if (
                    isinstance(aggregate, str)
                    and isinstance(sequence, int)
                    and not isinstance(sequence, bool)
                ):
                    connection.execute(
                        "INSERT INTO observed_event_cursor VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(agent, source, aggregate_id) DO UPDATE SET "
                        "seq=max(seq, excluded.seq)",
                        (agent, source, aggregate, sequence),
                    )

    def mark_live(
        self,
        state: str,
        source: str = "opencode:sse:v2",
        agent: str = "opencode",
    ) -> None:
        """Stores SSE connection health per agent and source."""
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO live_connection (agent, source, state, observed_at) "
                "VALUES (?, ?, ?, ?)",
                (agent, source, state, datetime.now(timezone.utc).isoformat()),
            )

    def events(
        self,
        session_id: str | None,
        page: tuple[int, int],
        source: str = "opencode:sse:v2",
        agent: str = "opencode",
    ) -> dict:
        """Returns one agent/source's events without storing a duplicate SSE frame."""
        limit, offset = page
        with self.connect() as connection:
            connection.execute("BEGIN")
            total = connection.execute(
                "SELECT count(*) FROM observed_event WHERE agent=? AND source=? "
                "AND (? IS NULL OR session_id=?)",
                (agent, source, session_id, session_id),
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT id, instance_id, session_id, kind, observed_at, data "
                "FROM observed_event WHERE agent=? AND source=? "
                "AND (? IS NULL OR session_id=?) "
                "ORDER BY observed_at, id LIMIT ? OFFSET ?",
                (agent, source, session_id, session_id, limit, offset),
            ).fetchall()
        items = [
            {
                "id": row[0],
                "instance_id": row[1],
                "session_id": row[2],
                "kind": row[3],
                "observed_at": row[4],
                **json.loads(row[5]),
                "agent": agent,
                "source": source,
            }
            for row in rows
        ]
        return {"items": items, "total": total}

    def live_history(
        self,
        source: str = "opencode:sse:v2",
        agent: str = "opencode",
    ) -> list[dict]:
        """Returns the selected source's recent connection transitions."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT state, observed_at, agent, source FROM live_connection "
                "WHERE agent=? AND source=? ORDER BY id DESC LIMIT 20",
                (agent, source),
            ).fetchall()
        return [
            {"state": row[0], "observed_at": row[1], "agent": row[2], "source": row[3]}
            for row in rows
        ]

    def normalization_warnings(self, source: str, agent: str = "opencode") -> list[str]:
        """Returns warnings only from one agent's selected source."""
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT warning.value FROM observed_session s, "
                "json_each(json_extract(s.data, '$.normalization_warnings')) warning "
                "WHERE s.agent=? AND s.source=? ORDER BY warning.value",
                (agent, source),
            ).fetchall()
        return [row[0] for row in rows]


def _payload(value: object) -> str:
    """Stores only the original message payload, once, in its native JSON form."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
