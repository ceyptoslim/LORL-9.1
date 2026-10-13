"""Native-SQL ledger backend invariants (Oct 2026).

The ledger no longer rewrites placeholders at runtime: each backend
owns its SQL in its own paramstyle. These tests enforce that contract:
paramstyle purity per backend, placeholder-count correctness, and
query-key parity, so nobody can reintroduce a fragile shim silently.
"""

# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)

import pytest

from lorl.core.ledger import Event, EventLedger, EventType
from lorl.core.ledger_backends import PostgresBackend, SQLiteBackend


def _make_event(n=1):
    return Event(
        event_type=EventType.TREATY_ACCEPTED,
        actor_id="lab-a",
        aggregate_id="agg-x",
        data={"n": n},
        timestamp="2026-10-12T00:00:00",
    )


class TestNativeParamstyles:
    def test_sqlite_queries_are_question_mark_native(self):
        for key, sql in SQLiteBackend.QUERIES.items():
            assert "?" in sql or "%s" not in sql, key
            assert "%s" not in sql, (
                f"SQLite query '{key}' contains %%s — SQLite speaks '?' natively"
            )

    def test_postgres_queries_are_percent_native(self):
        for key, sql in PostgresBackend.QUERIES.items():
            assert "?" not in sql, (
                f"Postgres query '{key}' contains '?' — psycopg speaks '%s' natively"
            )

    def test_query_keys_identical_across_backends(self):
        assert set(SQLiteBackend.QUERIES) == set(PostgresBackend.QUERIES), (
            "query key drift between backends — every query must be "
            "authored natively for BOTH backends"
        )

    def test_placeholder_counts_match_call_sites(self):
        """Static proof the placeholder count equals the params each caller
        passes — the class of bug the old runtime replace() masked."""
        expected = {
            "count_aggregate": 1,
            "select_by_aggregate": 1,
            "select_by_aggregate_type": 2,
            "insert_event": 11,
            "backfill_update": 4,
        }
        for key, count in expected.items():
            assert SQLiteBackend.QUERIES[key].count("?") == count, f"sqlite:{key}"
            assert PostgresBackend.QUERIES[key].count("%s") == count, f"pg:{key}"

    def test_missing_query_key_raises_loudly(self):
        with pytest.raises(KeyError, match="missing native SQL"):
            SQLiteBackend("sqlite:///:memory:").q("no_such_query")


class TestBackendSelection:
    def test_postgres_dsn_selects_postgres_backend(self, monkeypatch):
        """Factory routing: a postgresql:// DSN must construct the
        PostgresBackend (proven without opening a real connection)."""
        import lorl.core.ledger as ledger_mod

        seen = {}

        class FakePG(PostgresBackend):
            def connection(self):
                seen["cls"] = FakePG
                raise RuntimeError("stop init here")

        monkeypatch.setattr(ledger_mod, "PostgresBackend", FakePG)
        with pytest.raises(RuntimeError, match="stop init here"):
            EventLedger("postgresql://u:p@localhost:5432/x")
        assert seen.get("cls") is FakePG, "postgres DSN did not route to PostgresBackend"

    def test_postgres_backend_without_psycopg_fails_closed(self):
        backend = PostgresBackend("postgresql://u:p@localhost:5432/x")
        try:
            import psycopg  # noqa: F401
            pytest.skip("psycopg installed — cannot test the failure path")
        except ImportError:
            pass
        with pytest.raises(RuntimeError, match="psycopg not installed"):
            backend.connection()

    def test_unknown_dsn_falls_back_to_in_memory_sqlite(self):
        """Junk DSNs (the old test default) must still yield a working
        in-memory ledger, end to end."""
        ledger = EventLedger("totally-not-a-dsn")
        assert isinstance(ledger._backend, SQLiteBackend)
        ledger.append(_make_event())
        assert ledger.get_event_count() == 1
        assert ledger.verify_integrity() is True

    def test_sqlite_backend_round_trip(self, tmp_path):
        ledger = EventLedger(f"sqlite:///{tmp_path}/l.db")
        for n in range(3):
            ledger.append(_make_event(n))
        events = ledger.get_events("agg-x")
        assert len(events) == 3
        assert [e["sequence"] for e in events] == [0, 1, 2]
        assert ledger.verify_integrity() is True

    def test_tampering_breaks_chain_on_native_backend(self, tmp_path):
        """Sabotage check: mutating a stored event must fail verification
        under the native-SQL backend (no shim to mask it)."""
        ledger = EventLedger(f"sqlite:///{tmp_path}/l.db")
        ledger.append(_make_event())
        ledger.append(_make_event(2))
        conn = ledger._backend.connection()
        conn.execute(
            "UPDATE events SET data = ? WHERE sequence = 1",
            ('{"n": 999}',),
        )
        conn.commit()
        assert ledger.verify_integrity() is False
