"""
Tests for LORL-9.1 Treaty Engine — State machine for lab agreements.
"""

import json

import pytest

from lorl.core.identity import Identity


from lorl.core.treaty_engine import (
    TreatyEngine,
    TreatyStatus,
    TreatyTransitionError,
)


def _signed(identity, treaty_id, action, actor_id):
    """Sign the canonical action payload the engine verifies."""
    payload = json.dumps(
        {"treaty_id": treaty_id, "action": action, "actor_id": actor_id},
        sort_keys=True,
    ).encode()
    return identity.sign(payload)


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
        responder = Identity.create("lab-002")
        updated = engine.accept(
            treaty, "lab-002",
            signature=_signed(responder, treaty.treaty_id, "accept", "lab-002"),
            responder_identity=responder,
        )
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
        intruder = Identity.create("lab-003")
        with pytest.raises(ValueError, match="Only responder"):
            engine.accept(
                treaty, "lab-003",
                signature=_signed(intruder, treaty.treaty_id, "accept", "lab-003"),
                responder_identity=intruder,
            )

    def test_reject_proposed_treaty(self):
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Research Partnership",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"duration": "6_months"},
        )
        responder = Identity.create("lab-002")
        updated = engine.reject(
            treaty, "lab-002",
            signature=_signed(responder, treaty.treaty_id, "reject", "lab-002"),
            responder_identity=responder,
        )
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
        responder = Identity.create("lab-002")
        treaty = engine.accept(
            treaty, "lab-002",
            signature=_signed(responder, treaty.treaty_id, "accept", "lab-002"),
            responder_identity=responder,
        )
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
        responder = Identity.create("lab-002")
        treaty = engine.accept(
            treaty, "lab-002",
            signature=_signed(responder, treaty.treaty_id, "accept", "lab-002"),
            responder_identity=responder,
        )
        with pytest.raises(TreatyTransitionError):
            engine.accept(
                treaty, "lab-002",
                signature=_signed(responder, treaty.treaty_id, "accept", "lab-002"),
                responder_identity=responder,
            )

    def test_accept_with_foreign_identity_rejected(self):
        """Identity-binding: presenting lab-002's treaty with lab-003's
        identity (even with a VALID signature) must be rejected — you
        cannot authorize someone else's action with your own key."""
        engine = TreatyEngine()
        treaty = engine.propose(
            title="Identity Binding",
            proposer_id="lab-001",
            responder_id="lab-002",
            terms={"share": 0.3},
        )
        impostor = Identity.create("lab-003")
        with pytest.raises(ValueError, match="Identity belongs to"):
            engine.accept(
                treaty, "lab-002",
                signature=_signed(impostor, treaty.treaty_id, "accept", "lab-002"),
                responder_identity=impostor,
            )
        # treaty must be untouched by the failed attempt
        assert treaty.status == TreatyStatus.PROPOSED
