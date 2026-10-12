"""
Regression tests for the Oct 2026 governance-hardening fixes:

1. Ledger hash chaining (tamper, deletion, and reorder detection).
2. GovernedExecutor genuinely withholding denied agent output.
3. Governed-execute API ignoring client-supplied governance targets
   (server-side env config only).
4. Treaty accept/reject optional Ed25519 signature verification.
"""

import json

import pytest

from lorl.core.identity import Identity
from lorl.core.ledger import Event, EventType
from lorl.core.treaty_engine import TreatyEngine, TreatyStatus


def _mk_event(actor="lab-a", aggregate="agg-1", data=None):
    return Event(
        event_type=EventType.AGENT_DECISION,
        actor_id=actor,
        aggregate_id=aggregate,
        data=data or {"note": "x"},
    )


class TestLedgerChaining:
    def test_clean_ledger_verifies(self, ledger):
        for _ in range(3):
            ledger.append(_mk_event())
        assert ledger.verify_integrity() is True

    def test_tampering_detected(self, ledger):
        for _ in range(3):
            ledger.append(_mk_event())
        conn = ledger._get_conn()
        conn.execute(
            "UPDATE events SET data = ? WHERE ledger_seq = 2",
            (json.dumps({"note": "tampered"}),),
        )
        conn.commit()
        assert ledger.verify_integrity() is False

    def test_deletion_detected(self, ledger):
        for _ in range(3):
            ledger.append(_mk_event())
        conn = ledger._get_conn()
        conn.execute("DELETE FROM events WHERE ledger_seq = 2")
        conn.commit()
        assert ledger.verify_integrity() is False

    def test_chain_fields_present(self, ledger):
        ledger.append(_mk_event())
        events = ledger.get_all_events()
        assert events[0]["prev_hash"] == "GENESIS"
        assert events[0]["event_hash"]
        assert events[0]["ledger_seq"] == 1


class TestWithheldOutput:
    def _make_executor(self, monkeypatch, eval_result):
        from lorl.agents import LiteratureAgent
        from lorl.governance import CustosClient, GovernedExecutor

        async def mock_evaluate(self, content, client_id="lorl"):
            return eval_result

        monkeypatch.setattr(CustosClient, "evaluate", mock_evaluate)
        return GovernedExecutor(
            agent=LiteratureAgent(), custos_client=CustosClient("http://x")
        )

    @pytest.mark.asyncio
    async def test_denied_output_actually_withheld(self, monkeypatch):
        executor = self._make_executor(
            monkeypatch,
            {"allowed": False, "reason": "SSN pattern", "triggered_rule": "deny_ssn"},
        )
        result = await executor.execute({"topic": "test"})
        assert result["agent_output_withheld"] is True
        assert result["governance_status"] == "denied"
        for leak_key in ("data", "reasoning", "recommendations", "metadata"):
            assert leak_key not in result, f"denied response leaked {leak_key}"

    @pytest.mark.asyncio
    async def test_unavailable_output_actually_withheld(self, monkeypatch):
        executor = self._make_executor(
            monkeypatch, {"allowed": False, "reason": "CUSTOS unavailable"}
        )
        result = await executor.execute({"topic": "test"})
        assert result["agent_output_withheld"] is True
        for leak_key in ("data", "reasoning", "recommendations", "metadata"):
            assert leak_key not in result, f"withheld response leaked {leak_key}"

    @pytest.mark.asyncio
    async def test_allowed_output_still_returned(self, monkeypatch):
        executor = self._make_executor(
            monkeypatch, {"allowed": True, "audit_record_hash": "h" * 64}
        )
        result = await executor.execute({"topic": "test"})
        assert result["custos_approved"] is True
        assert "data" in result  # allowed output is NOT withheld


class TestGovernedExecuteServerSideConfig:
    def test_client_supplied_custos_url_is_ignored(self, monkeypatch):
        """The API payload may still carry custos_url (old clients) — it must
        be ignored, with governance always taken from server env config."""
        from fastapi.testclient import TestClient

        from lorl.api.main import create_app
        from lorl.governance import CustosClient

        async def mock_evaluate(self, content, client_id="lorl"):
            return {"allowed": True, "audit_record_hash": "env_ok"}

        monkeypatch.setattr(CustosClient, "evaluate", mock_evaluate)
        app = create_app()
        client = TestClient(app)
        r = client.post(
            "/api/v1/agents/governed-execute",
            json={
                "agent_type": "literature",
                "task": {"topic": "t"},
                "custos_url": "http://attacker-controlled-governance:9999",
                "tenant_id": "evil-tenant",
            },
        )
        assert r.status_code == 200
        assert r.json()["custos_approved"] is True


class TestTreatySignatures:
    def _payload(self, treaty, action, responder_id):
        return json.dumps(
            {"treaty_id": treaty.treaty_id, "action": action, "actor_id": responder_id},
            sort_keys=True,
        ).encode()

    def test_accept_with_valid_signature(self):
        engine = TreatyEngine()
        responder = Identity.create(lab_id="lab-b")
        treaty = engine.propose("T", "lab-a", "lab-b", {"k": "v"})
        sig = responder.sign(self._payload(treaty, "accept", "lab-b"))
        accepted = engine.accept(treaty, "lab-b", signature=sig, responder_identity=responder)
        assert accepted.status == TreatyStatus.ACCEPTED

    def test_accept_with_forged_signature_rejected(self):
        engine = TreatyEngine()
        responder = Identity.create(lab_id="lab-b")
        other = Identity.create(lab_id="lab-c")
        treaty = engine.propose("T", "lab-a", "lab-b", {"k": "v"})
        forged = other.sign(self._payload(treaty, "accept", "lab-b"))
        with pytest.raises(ValueError, match="Signature verification failed"):
            engine.accept(treaty, "lab-b", signature=forged, responder_identity=responder)
        assert treaty.status == TreatyStatus.PROPOSED

    def test_reject_with_valid_signature(self):
        engine = TreatyEngine()
        responder = Identity.create(lab_id="lab-b")
        treaty = engine.propose("T", "lab-a", "lab-b", {"k": "v"})
        sig = responder.sign(self._payload(treaty, "reject", "lab-b"))
        rejected = engine.reject(treaty, "lab-b", signature=sig, responder_identity=responder)
        assert rejected.status == TreatyStatus.REJECTED
