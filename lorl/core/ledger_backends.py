"""Native-SQL ledger backends (Oct 2026 structural fix).

Previously the ledger authored every query in SQLite's ``?`` paramstyle
and rewrote placeholders at runtime (``sql.replace("?", "%s")``) for
PostgreSQL. A blanket string replace is fragile: any literal ``?`` in a
query (or a future query authored in the wrong style) is silently
corrupted or silently works today and breaks tomorrow.

The structural fix: each backend owns its SQL natively in its own
paramstyle — SQLite backends speak ``?`` and only ``?``, PostgreSQL
backends speak ``%s`` and only ``%s``. There is no runtime rewriting
anywhere. The shared query KEY set is enforced by test so adding a
query to one backend without the other fails loudly.
"""

# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)


SCHEMA_DDL = (
    """
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
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_events_aggregate
    ON events(aggregate_id, sequence)
    """,
)

# Migration statements for pre-existing event tables (both dialects support
# these verbatim; duplicate-column errors are tolerated by the caller).
MIGRATION_DDL = (
    "ALTER TABLE events ADD COLUMN ledger_seq INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE events ADD COLUMN prev_hash TEXT",
    "ALTER TABLE events ADD COLUMN event_hash TEXT NOT NULL DEFAULT ''",
)


class LedgerBackend:
    """Base class for ledger storage backends.

    Subclasses define ``QUERIES``: a mapping of stable query KEYS to SQL
    authored NATIVELY in that backend's paramstyle. No placeholder
    rewriting happens at runtime.
    """

    QUERIES: dict = {}

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn = None

    def connection(self):
        """Lazily open and cache the backend connection."""
        raise NotImplementedError

    def execute(self, sql: str, params: tuple = ()):
        return self.connection().execute(sql, params)

    def q(self, key: str) -> str:
        """Return the native SQL for a query key."""
        try:
            return self.QUERIES[key]
        except KeyError:
            raise KeyError(
                f"{type(self).__name__} is missing native SQL for query "
                f"'{key}' — every query key must be defined per backend"
            ) from None

    def commit(self) -> None:
        if self._conn is not None:
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class SQLiteBackend(LedgerBackend):
    """SQLite backend. All SQL authored natively in ``?`` paramstyle."""

    QUERIES = {
        "count_all": "SELECT COUNT(*) as count FROM events",
        "count_aggregate":
            "SELECT COUNT(*) as count FROM events WHERE aggregate_id = ?",
        "next_ledger_seq":
            "SELECT COALESCE(MAX(ledger_seq), 0) + 1 AS nxt FROM events",
        "last_event_hash":
            "SELECT event_hash FROM events ORDER BY ledger_seq DESC LIMIT 1",
        "insert_event": """
            INSERT INTO events
            (event_id, event_type, actor_id, aggregate_id, data, timestamp,
             sequence, content_hash, ledger_seq, prev_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        "select_by_aggregate": """
            SELECT * FROM events
            WHERE aggregate_id = ?
            ORDER BY sequence ASC""",
        "select_by_aggregate_type": """
            SELECT * FROM events
            WHERE aggregate_id = ? AND event_type = ?
            ORDER BY sequence ASC""",
        "select_all": "SELECT * FROM events ORDER BY timestamp ASC",
        "select_chain_order": """
            SELECT event_id, content_hash, event_hash FROM events
            ORDER BY ledger_seq ASC, timestamp ASC, event_id ASC""",
        "backfill_update": """
            UPDATE events SET ledger_seq = ?, prev_hash = ?,
            event_hash = ? WHERE event_id = ?""",
        "verify_walk": "SELECT * FROM events ORDER BY ledger_seq ASC",
    }

    def connection(self):
        if self._conn is None:
            import sqlite3

            db_path = self.dsn.replace("sqlite:///", "")
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn


class PostgresBackend(LedgerBackend):
    """PostgreSQL backend (psycopg 3). All SQL authored natively in
    ``%s`` paramstyle — matching the driver, never rewritten."""

    QUERIES = {
        "count_all": "SELECT COUNT(*) as count FROM events",
        "count_aggregate":
            "SELECT COUNT(*) as count FROM events WHERE aggregate_id = %s",
        "next_ledger_seq":
            "SELECT COALESCE(MAX(ledger_seq), 0) + 1 AS nxt FROM events",
        "last_event_hash":
            "SELECT event_hash FROM events ORDER BY ledger_seq DESC LIMIT 1",
        "insert_event": """
            INSERT INTO events
            (event_id, event_type, actor_id, aggregate_id, data, timestamp,
             sequence, content_hash, ledger_seq, prev_hash, event_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        "select_by_aggregate": """
            SELECT * FROM events
            WHERE aggregate_id = %s
            ORDER BY sequence ASC""",
        "select_by_aggregate_type": """
            SELECT * FROM events
            WHERE aggregate_id = %s AND event_type = %s
            ORDER BY sequence ASC""",
        "select_all": "SELECT * FROM events ORDER BY timestamp ASC",
        "select_chain_order": """
            SELECT event_id, content_hash, event_hash FROM events
            ORDER BY ledger_seq ASC, timestamp ASC, event_id ASC""",
        "backfill_update": """
            UPDATE events SET ledger_seq = %s, prev_hash = %s,
            event_hash = %s WHERE event_id = %s""",
        "verify_walk": "SELECT * FROM events ORDER BY ledger_seq ASC",
    }

    def connection(self):
        if self._conn is None:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError:
                raise RuntimeError(
                    "psycopg not installed. Install with: pip install 'psycopg[binary]'"
                )
            self._conn = psycopg.connect(self.dsn, row_factory=dict_row)
        return self._conn
