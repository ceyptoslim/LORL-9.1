"""
Tests for LORL-9.1 Event Ledger — Append-only event sourcing.
"""

from lorl.core.ledger import Event, EventType


class TestEventLedger:
    def test_append_and_retrieve_event(self, ledger):
        event = Event(
            event_id="evt-001",
            event_type=EventType.TREATY_PROPOSED,
            actor_id="lab-001",
            aggregate_id="treaty-abc",
            data={"title": "Collaboration", "terms": {"revenue_share": 0.3}},
        )
        ledger.append(event)
        events = ledger.get_events("treaty-abc")
        assert len(events) == 1
        assert events[0]["event_id"] == "evt-001"
        assert events[0]["event_type"] == "treaty_proposed"
        assert events[0]["data"]["terms"]["revenue_share"] == 0.3

    def test_multiple_events_ordered_by_sequence(self, ledger):
        for i in range(5):
            ledger.append(Event(
                event_id=f"evt-{i}",
                event_type=EventType.AGENT_DECISION,
                actor_id="lab-001",
                aggregate_id="experiment-1",
                data={"iteration": i},
            ))
        events = ledger.get_events("experiment-1")
        assert len(events) == 5
        for i, evt in enumerate(events):
            assert evt["sequence"] == i

    def test_filter_by_event_type(self, ledger):
        ledger.append(Event(
            event_type=EventType.TREATY_PROPOSED,
            actor_id="lab-001",
            aggregate_id="treaty-1",
            data={},
        ))
        ledger.append(Event(
            event_type=EventType.TREATY_ACCEPTED,
            actor_id="lab-002",
            aggregate_id="treaty-1",
            data={},
        ))
        ledger.append(Event(
            event_type=EventType.TREATY_PROPOSED,
            actor_id="lab-003",
            aggregate_id="treaty-2",
            data={},
        ))

        proposed = ledger.get_events("treaty-1", EventType.TREATY_PROPOSED)
        assert len(proposed) == 1
        assert proposed[0]["event_type"] == "treaty_proposed"

    def test_content_hash_consistency(self, ledger):
        event = Event(
            event_type=EventType.LAB_REGISTERED,
            actor_id="lab-001",
            aggregate_id="lab-001",
            data={"name": "Lab Alpha"},
        )
        ledger.append(event)
        events = ledger.get_events("lab-001")
        assert events[0]["content_hash"] == event.content_hash

    def test_verify_integrity_passes_on_clean_ledger(self, ledger):
        for i in range(3):
            ledger.append(Event(
                event_id=f"evt-{i}",
                event_type=EventType.AGENT_DECISION,
                actor_id="lab-001",
                aggregate_id="agg-1",
                data={"i": i},
            ))
        assert ledger.verify_integrity() is True

    def test_get_all_events(self, ledger):
        ledger.append(Event(
            event_id="evt-a",
            event_type=EventType.LAB_REGISTERED,
            actor_id="lab-001",
            aggregate_id="lab-001",
            data={},
        ))
        ledger.append(Event(
            event_id="evt-b",
            event_type=EventType.TREATY_PROPOSED,
            actor_id="lab-001",
            aggregate_id="treaty-1",
            data={},
        ))
        all_events = ledger.get_all_events()
        assert len(all_events) == 2

    def test_get_event_count(self, ledger):
        assert ledger.get_event_count() == 0
        for i in range(10):
            ledger.append(Event(
                event_id=f"evt-{i}",
                event_type=EventType.AGENT_DECISION,
                actor_id="lab-001",
                aggregate_id="agg-1",
                data={"i": i},
            ))
        assert ledger.get_event_count() == 10

    def test_empty_aggregate_returns_empty_list(self, ledger):
        events = ledger.get_events("nonexistent")
        assert events == []
