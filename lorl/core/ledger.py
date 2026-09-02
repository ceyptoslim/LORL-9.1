"""
LORL-9.1 Event Ledger — PostgreSQL-backed event sourcing for institutional memory.

Every treaty proposal, acceptance, rejection, agent decision, and governance
action is recorded as an immutable event. Events are append-only and ordered
by sequence number within each aggregate (treaty, lab, etc.).

Supports both SQLite (dev) and PostgreSQL (production) backends.
"""

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
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a database connection."""
        if self._conn is not None:
            return self._conn

        if self.connection_string.startswith("sqlite:///"):
            db_path = self.connection_string.replace("sqlite:///", "")
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        elif self.connection_string.startswith("postgresql://"):
            # For PostgreSQL, use psycopg2
            try:
                import psycopg2
                import psycopg2.extras
                pg_url = self.connection_string
                self._conn = psycopg2.connect(pg_url)
                self._conn.row_factory = None  # psycopg2 uses cursor.fetchall()
            except ImportError:
                raise RuntimeError(
                    "psycopg2 not installed. Install with: pip install psycopg2-binary"
                )
        else:
            # Default to in-memory SQLite for tests
            self._conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row

        return self._conn

    def _init_db(self) -> None:
        """Initialize the events table."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                content_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_aggregate
            ON events(aggregate_id, sequence)
        """)
        conn.commit()

    def append(self, event: Event) -> str:
        """Append an event to the ledger. Returns the event_id."""
        conn = self._get_conn()

        # Get next sequence for this aggregate
        cursor = conn.execute(
            "SELECT COUNT(*) as count FROM events WHERE aggregate_id = ?",
            (event.aggregate_id,),
        )
        row = cursor.fetchone()
        event.sequence = row["count"] if row else 0

        conn.execute(
            """INSERT INTO events
               (event_id, event_type, actor_id, aggregate_id, data, timestamp, sequence, content_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.event_type.value,
                event.actor_id,
                event.aggregate_id,
                json.dumps(event.data),
                event.timestamp,
                event.sequence,
                event.content_hash,
            ),
        )
        conn.commit()
        return event.event_id

    def get_events(
        self, aggregate_id: str, event_type: Optional[EventType] = None
    ) -> list[dict]:
        """Retrieve events for an aggregate, optionally filtered by type."""
        conn = self._get_conn()

        if event_type:
            cursor = conn.execute(
                """SELECT * FROM events
                   WHERE aggregate_id = ? AND event_type = ?
                   ORDER BY sequence ASC""",
                (aggregate_id, event_type.value),
            )
        else:
            cursor = conn.execute(
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
            }
            for row in rows
        ]

    def get_all_events(self) -> list[dict]:
        """Retrieve all events in the ledger."""
        conn = self._get_conn()
        cursor = conn.execute(
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
            }
            for row in rows
        ]

    def verify_integrity(self) -> bool:
        """Verify that all event content hashes are valid (no tampering)."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM events ORDER BY sequence ASC")
        rows = cursor.fetchall()

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
        return True

    def get_event_count(self) -> int:
        """Return total number of events in the ledger."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT COUNT(*) as count FROM events")
        row = cursor.fetchone()
        return row["count"] if row else 0

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
