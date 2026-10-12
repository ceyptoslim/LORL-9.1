"""
LORL-9.1 Event Ledger — PostgreSQL-backed event sourcing for institutional memory.

Every treaty proposal, acceptance, rejection, agent decision, and governance
action is recorded as an immutable event. Events are append-only and ordered
by sequence number within each aggregate (treaty, lab, etc.).

Supports both SQLite (dev) and PostgreSQL (production) backends.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    """Types of events in the LORL system."""

    LAB_REGISTERED = "lab_registered"
    TREATY_PROPOSED = "treaty_proposed"
    TREATY_ACCEPTED = "treaty_accepted"
    TREATY_REJECTED = "treaty_rejected"
    TREATY_EXPIRED = "treaty_expired"
    AGENT_DECISION = "agent_decision"
    GOVERNANCE_CHECK = "governance_check"
    LEDGER_SNAPSHOT = "ledger_snapshot"


@dataclass
class Event:
    """An immutable event in the LORL ledger."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType = EventType.AGENT_DECISION
    actor_id: str = ""
    aggregate_id: str = ""
    data: dict = field(default_factory=dict)
    signature: Optional[bytes] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sequence: int = 0

    def to_dict(self) -> dict:
        """Serialize event to dict for storage."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "actor_id": self.actor_id,
            "aggregate_id": self.aggregate_id,
            "data": self.data,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
        }

    @property
    def content_hash(self) -> str:
        """SHA-256 hash of the event content for integrity verification."""
        raw = json.dumps(
            {
                "event_type": self.event_type.value,
                "actor_id": self.actor_id,
                "aggregate_id": self.aggregate_id,
                "data": self.data,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(raw).hexdigest()


class EventLedger:
    """
    Append-only event ledger backed by SQLite (dev) or PostgreSQL (production).

    Connection string format:
      - SQLite: sqlite:///path/to/lorl.db
      - PostgreSQL: postgresql://user:pass@host:5432/lorl_db
    """

    def __init__(self, connection_string: str = "sqlite:///lorl.db"):
        self.connection_string = connection_string
        self._backend = (
            "postgres" if connection_string.startswith("postgresql://") else "sqlite"
        )
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _run(self, sql: str, params: tuple = ()):
        """Execute SQL with backend-appropriate placeholders.

        This ledger's queries are authored with SQLite-style ``?``
        placeholders; PostgreSQL (psycopg) requires ``%s``. All call sites
        go through this helper so both backends work from one source.
        """
        conn = self._get_conn()
        if self._backend == "postgres":
            sql = sql.replace("?", "%s")
        return conn.execute(sql, params)

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        if self._conn is not None:
            return self._conn

        if self.connection_string.startswith("sqlite:///"):
            db_path = self.connection_string.replace("sqlite:///", "")
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        elif self.connection_string.startswith("postgresql://"):
            # For PostgreSQL, use psycopg 3 — the driver whose connection API
            # (conn.execute, row_factory) this ledger is written against.
            # Fix (Oct 2026 audit): previously imported psycopg2, whose
            # connection object has no .execute() — the PostgreSQL backend
            # crashed on first use.
            try:
                import psycopg
                from psycopg.rows import dict_row
                pg_url = self.connection_string
                self._conn = psycopg.connect(pg_url, row_factory=dict_row)
            except ImportError:
                raise RuntimeError(
                    "psycopg not installed. Install with: pip install 'psycopg[binary]'"
                )
        else:
            # Default to in-memory SQLite for tests
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

        return self._conn

    def _init_db(self) -> None:
        """Initialize the events table."""
        self._run("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                ledger_seq INTEGER NOT NULL DEFAULT 0,
                prev_hash TEXT,
                event_hash TEXT NOT NULL
            )
        """)
        self._run("""
            CREATE INDEX IF NOT EXISTS idx_events_aggregate
            ON events(aggregate_id, sequence)
        """)

        # Migration (Oct 2026): upgrade pre-existing event tables to the
        # chained schema. CREATE TABLE IF NOT EXISTS does not touch an
        # existing table, so add the chain columns explicitly and tolerate
        # the duplicate-column error when they already exist.
        for stmt in (
            "ALTER TABLE events ADD COLUMN ledger_seq INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE events ADD COLUMN prev_hash TEXT",
            "ALTER TABLE events ADD COLUMN event_hash TEXT NOT NULL DEFAULT ''",
        ):
            try:
                self._run(stmt)
            except Exception:
                pass  # column already exists

        # Backfill (Oct 2026): rows written before hash chaining shipped carry
        # event_hash = ''. Without a backfill they fail verify_integrity()
        # forever, and the first post-migration event would chain to an empty
        # string. Re-root the whole chain deterministically (ledger_seq, then
        # timestamp, then event_id) from GENESIS. Recomputing is a no-op for
        # rows whose chain is already valid, so this is idempotent.
        rows = (
            self._run(
                "SELECT event_id, content_hash, event_hash FROM events "
                "ORDER BY ledger_seq ASC, timestamp ASC, event_id ASC"
            )
            .fetchall()
            or []
        )
        if any(not (r["event_hash"] or "") for r in rows):
            prev = "GENESIS"
            seq = 0
            for row in rows:
                chained = hashlib.sha256(
                    f"{prev}:{row['content_hash']}".encode()
                ).hexdigest()
                if row["event_hash"] != chained:
                    self._run(
                        "UPDATE events SET ledger_seq = ?, prev_hash = ?, "
                        "event_hash = ? WHERE event_id = ?",
                        (seq, prev, chained, row["event_id"]),
                    )
                prev = chained
                seq += 1
        self._get_conn().commit()

    def append(self, event: Event) -> str:
        """Append an event to the ledger. Returns the event_id.

        Chain integrity (Oct 2026 fix): each event stores the hash of the
        previous ledger event (``prev_hash``) and a chained ``event_hash``
        computed over (prev_hash, content_hash). Deleting, reordering, or
        editing any event breaks the chain for every later event — the
        per-event ``content_hash`` alone could not detect removal/reordering.
        """

        # Next per-aggregate sequence
        cursor = self._run(
            "SELECT COUNT(*) as count FROM events WHERE aggregate_id = ?",
            (event.aggregate_id,),
        )
        row = cursor.fetchone()
        event.sequence = row["count"] if row else 0

        # Next global ledger position + previous event's chained hash
        cursor = self._run(
            "SELECT COALESCE(MAX(ledger_seq), 0) + 1 AS nxt FROM events"
        )
        ledger_seq = cursor.fetchone()["nxt"]

        cursor = self._run(
            "SELECT event_hash FROM events ORDER BY ledger_seq DESC LIMIT 1"
        )
        prev_row = cursor.fetchone()
        prev_hash = (prev_row["event_hash"] if prev_row else "") or "GENESIS"

        content_hash = event.content_hash
        event_hash = hashlib.sha256(
            f"{prev_hash}:{content_hash}".encode()
        ).hexdigest()

        self._run(
            """INSERT INTO events
               (event_id, event_type, actor_id, aggregate_id, data, timestamp,
                sequence, content_hash, ledger_seq, prev_hash, event_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.event_type.value,
                event.actor_id,
                event.aggregate_id,
                json.dumps(event.data),
                event.timestamp,
                event.sequence,
                content_hash,
                ledger_seq,
                prev_hash,
                event_hash,
            ),
        )
        self._get_conn().commit()
        return event.event_id

    def get_events(
        self, aggregate_id: str, event_type: Optional[EventType] = None
    ) -> list[dict]:
        """Retrieve events for an aggregate, optionally filtered by type."""

        if event_type:
            cursor = self._run(
                """SELECT * FROM events
                   WHERE aggregate_id = ? AND event_type = ?
                   ORDER BY sequence ASC""",
                (aggregate_id, event_type.value),
            )
        else:
            cursor = self._run(
                """SELECT * FROM events
                   WHERE aggregate_id = ?
                   ORDER BY sequence ASC""",
                (aggregate_id,),
            )

        rows = cursor.fetchall()
        return [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "aggregate_id": row["aggregate_id"],
                "data": json.loads(row["data"]),
                "timestamp": row["timestamp"],
                "sequence": row["sequence"],
                "content_hash": row["content_hash"],
                "ledger_seq": row["ledger_seq"],
                "prev_hash": row["prev_hash"],
                "event_hash": row["event_hash"],
            }
            for row in rows
        ]

    def get_all_events(self) -> list[dict]:
        """Retrieve all events in the ledger."""
        cursor = self._run(
            "SELECT * FROM events ORDER BY timestamp ASC"
        )
        rows = cursor.fetchall()
        return [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "actor_id": row["actor_id"],
                "aggregate_id": row["aggregate_id"],
                "data": json.loads(row["data"]),
                "timestamp": row["timestamp"],
                "sequence": row["sequence"],
                "content_hash": row["content_hash"],
                "ledger_seq": row["ledger_seq"],
                "prev_hash": row["prev_hash"],
                "event_hash": row["event_hash"],
            }
            for row in rows
        ]

    def verify_integrity(self) -> bool:
        """Verify the full ledger chain (no tampering, no removal, no reorder).

        Walks events in global ledger order and checks, for each event:
        1. the per-event content hash still matches its stored data;
        2. the stored ``prev_hash`` equals the previous event's chained hash;
        3. the chained ``event_hash`` matches (prev_hash, content_hash).
        Any deletion, reorder, or edit breaks the walk at that point.
        """
        cursor = self._run("SELECT * FROM events ORDER BY ledger_seq ASC")
        rows = cursor.fetchall()

        prev_hash = "GENESIS"
        for row in rows:
            event = Event(
                event_id=row["event_id"],
                event_type=EventType(row["event_type"]),
                actor_id=row["actor_id"],
                aggregate_id=row["aggregate_id"],
                data=json.loads(row["data"]),
                timestamp=row["timestamp"],
                sequence=row["sequence"],
            )
            if event.content_hash != row["content_hash"]:
                return False
            if row["prev_hash"] != prev_hash:
                return False
            expected_hash = hashlib.sha256(
                f"{row['prev_hash']}:{row['content_hash']}".encode()
            ).hexdigest()
            if row["event_hash"] != expected_hash:
                return False
            prev_hash = row["event_hash"]
        return True

    def get_event_count(self) -> int:
        """Return total number of events in the ledger."""
        cursor = self._run("SELECT COUNT(*) as count FROM events")
        row = cursor.fetchone()
        return row["count"] if row else 0

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
