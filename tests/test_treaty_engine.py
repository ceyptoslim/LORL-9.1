"""
Tests for LORL-9.1 Treaty Engine — State machine for lab agreements.
"""

import pytest

from lorl.core.treaty_engine import (
    TreatyEngine,
    TreatyStatus,
    TreatyTransitionError,
)


class TestTreatyEngine:
    def test_propose_creates_treaty(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Collaboration Agreement",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"revenue_share": 0.3},
        )
        assert treaty.status == TreatyStatus.PROPOSED
        assert treaty.title == "Collaboration Agreement"
        assert treaty.terms == {"revenue_share": 0.3}

    def test_accept_proposed_treaty(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Data Sharing",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"data_access": "read_only"},
        )
        updated = engine.accept(treaty, "lab-002")
        assert updated.status == TreatyStatus.ACCEPTED
        assert updated.accepted_at is not None

    def test_accept_wrong_responder_rejected(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Agreement",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"share": 0.5},
        )
        with pytest.raises(ValueError, match="Only responder"):
            engine.accept(treaty, "lab-003")

    def test_reject_proposed_treaty(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Research Partnership",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"duration": "6_months"},
        )
        updated = engine.reject(treaty, "lab-002")
        assert updated.status == TreatyStatus.REJECTED
        assert updated.rejected_at is not None

    def test_expire_accepted_treaty(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Temporary Agreement",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"duration": "1_month"},
        )
        treaty = engine.accept(treaty, "lab-002")
        updated = engine.expire(treaty)
        assert updated.status == TreatyStatus.EXPIRED

    def test_cancel_proposed_treaty_by_proposer(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Cancelled Agreement",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"cancel_reason": "mutual"},
        )
        updated = engine.cancel(treaty, "lab-001")
        assert updated.status == TreatyStatus.CANCELLED

    def test_invalid_transition_rejected_raises_error(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Agreement",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"share": 0.5},
        )
        treaty = engine.accept(treaty, "lab-002")
        with pytest.raises(TreatyTransitionError):
            engine.accept(treaty, "lab-002")
