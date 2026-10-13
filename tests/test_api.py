"""
Tests for LORL-9.1 API — FastAPI endpoint integration tests.

OPA is mocked to ALLOW for these integration tests. Fail-closed behavior
is tested separately in test_opa_enforcement.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lorl.api.main import create_app


def _mock_opa_allow():
    """Return a mock context manager that makes OPA return ALLOW for all requests."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"result": True}
    return patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response)


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_ready(self, client):
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "event_count" in data


class TestLabRegistration:
    def test_register_lab(self, client):
        response = client.post("/api/v1/labs", json={
            "lab_id": "lab-test-001",
            "name": "Test Lab",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["lab_id"] == "lab-test-001"
        assert len(data["public_key"]) == 64
        assert len(data["identity_hash"]) == 64

    def test_duplicate_lab_registration_fails(self, client):
        client.post("/api/v1/labs", json={"lab_id": "lab-dup", "name": "Lab"})
        response = client.post("/api/v1/labs", json={"lab_id": "lab-dup", "name": "Lab"})
        assert response.status_code == 409

    def test_list_labs(self, client):
        client.post("/api/v1/labs", json={"lab_id": "lab-list-1", "name": "Lab 1"})
        client.post("/api/v1/labs", json={"lab_id": "lab-list-2", "name": "Lab 2"})
        response = client.get("/api/v1/labs")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 2


def _action_sig(client, actor_id, treaty_id, action):
    """Sign a treaty action with the actor's registered identity."""
    import json as _json

    identity = client.app.state.identity_registry.get(actor_id)
    assert identity is not None, f"actor {actor_id} must register first"
    payload = _json.dumps(
        {"treaty_id": treaty_id, "action": action, "actor_id": actor_id},
        sort_keys=True,
    ).encode()
    return identity.sign(payload).hex()


def _register(client, lab_id, name=""):
    resp = client.post("/api/v1/labs", json={"lab_id": lab_id, "name": name})
    assert resp.status_code in (200, 201), resp.text


class TestTreatyAPI:
    def test_propose_treaty(self, client):
        with _mock_opa_allow():
            response = client.post("/api/v1/treaties", json={
                "title": "Collaboration Agreement",
                "proposer_id": "lab-a",
                "responder_id": "lab-b",
                "terms": {"revenue_share": 0.3},
            })
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "proposed"
            assert data["title"] == "Collaboration Agreement"
            assert "treaty_id" in data

    def test_accept_treaty(self, client):
        _register(client, "lab-x")
        _register(client, "lab-y")
        with _mock_opa_allow():
            propose = client.post("/api/v1/treaties", json={
                "title": "Data Sharing",
                "proposer_id": "lab-x",
                "responder_id": "lab-y",
                "terms": {"data_access": "read_only", "revenue_share": 0.5},
            })
            treaty_id = propose.json()["treaty_id"]

        with _mock_opa_allow():
            response = client.post(f"/api/v1/treaties/{treaty_id}/accept", json={
                "actor_id": "lab-y",
                "signature": _action_sig(client, "lab-y", treaty_id, "accept"),
            })
            assert response.status_code == 200
            assert response.json()["status"] == "accepted"

    def test_accept_treaty_forged_signature_rejected(self, client):
        """A tampered signature must be rejected — actor_id alone proves nothing."""
        _register(client, "lab-fx")
        _register(client, "lab-fy")
        with _mock_opa_allow():
            propose = client.post("/api/v1/treaties", json={
                "title": "Forged",
                "proposer_id": "lab-fx",
                "responder_id": "lab-fy",
                "terms": {"revenue_share": 0.1},
            })
            treaty_id = propose.json()["treaty_id"]

        good_sig = _action_sig(client, "lab-fy", treaty_id, "accept")
        sig_bytes = bytes.fromhex(good_sig)
        forged = (bytes([sig_bytes[0] ^ 1]) + sig_bytes[1:]).hex()  # flip one bit
        with _mock_opa_allow():
            response = client.post(f"/api/v1/treaties/{treaty_id}/accept", json={
                "actor_id": "lab-fy",
                "signature": forged,
            })
            assert response.status_code == 403

    def test_accept_treaty_unregistered_actor_rejected(self, client):
        """Fail-closed: no registered identity -> cannot verify -> 403."""
        _register(client, "lab-ux")
        with _mock_opa_allow():
            propose = client.post("/api/v1/treaties", json={
                "title": "Unregistered",
                "proposer_id": "lab-ux",
                "responder_id": "lab-uy",
                "terms": {"revenue_share": 0.1},
            })
            treaty_id = propose.json()["treaty_id"]

        with _mock_opa_allow():
            response = client.post(f"/api/v1/treaties/{treaty_id}/accept", json={
                "actor_id": "lab-uy",
                "signature": "00" * 32,
            })
            assert response.status_code == 403

    def test_accept_treaty_wrong_actor(self, client):
        with _mock_opa_allow():
            propose = client.post("/api/v1/treaties", json={
                "title": "Test",
                "proposer_id": "lab-p",
                "responder_id": "lab-q",
                "terms": {"revenue_share": 0.2},
            })
            treaty_id = propose.json()["treaty_id"]

        _register(client, "lab-z")
        with _mock_opa_allow():
            response = client.post(f"/api/v1/treaties/{treaty_id}/accept", json={
                "actor_id": "lab-z",
                "signature": _action_sig(client, "lab-z", treaty_id, "accept"),
            })
            assert response.status_code == 403

    def test_accept_nonexistent_treaty(self, client):
        _register(client, "lab-1")
        response = client.post("/api/v1/treaties/nonexistent/accept", json={
            "actor_id": "lab-1",
            "signature": _action_sig(client, "lab-1", "nonexistent", "accept"),
        })
        assert response.status_code == 404

    def test_reject_treaty(self, client):
        _register(client, "lab-r1")
        _register(client, "lab-r2")
        with _mock_opa_allow():
            propose = client.post("/api/v1/treaties", json={
                "title": "Rejected",
                "proposer_id": "lab-r1",
                "responder_id": "lab-r2",
                "terms": {"revenue_share": 0.1},
            })
            treaty_id = propose.json()["treaty_id"]

        with _mock_opa_allow():
            response = client.post(f"/api/v1/treaties/{treaty_id}/reject", json={
                "actor_id": "lab-r2",
                "signature": _action_sig(client, "lab-r2", treaty_id, "reject"),
            })
            assert response.status_code == 200
            assert response.json()["status"] == "rejected"

    def test_list_treaties(self, client):
        with _mock_opa_allow():
            client.post("/api/v1/treaties", json={
                "title": "T1",
                "proposer_id": "lab-t1",
                "responder_id": "lab-t2",
                "terms": {"revenue_share": 0.3},
            })
        response = client.get("/api/v1/treaties")
        assert response.status_code == 200
        assert response.json()["count"] >= 1


class TestAuditAPI:
    def test_get_audit_log(self, client):
        client.post("/api/v1/labs", json={"lab_id": "lab-audit", "name": "Audit Lab"})
        response = client.get("/api/v1/audit")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["count"] >= 1
        assert data["integrity_verified"] is True


class TestAgentExecutionAPI:
    def test_execute_literature_agent(self, client):
        with _mock_opa_allow():
            response = client.post("/api/v1/agents/execute", json={
                "agent_type": "literature",
                "task": {"topic": "AI Governance"},
            })
            assert response.status_code == 200
            data = response.json()
            assert data["agent_type"] == "literature"
            assert "reasoning" in data
            assert data["confidence"] > 0

    def test_execute_skeptic_agent(self, client):
        with _mock_opa_allow():
            response = client.post("/api/v1/agents/execute", json={
                "agent_type": "skeptic",
                "task": {"findings": ["Always trust the model", "Some finding"]},
            })
            assert response.status_code == 200
            data = response.json()
            assert data["agent_type"] == "skeptic"
            assert data["data"]["findings_reviewed"] == 2

    def test_execute_auditor_agent(self, client):
        with _mock_opa_allow():
            response = client.post("/api/v1/agents/execute", json={
                "agent_type": "auditor",
                "task": {
                    "action_type": "treaty",
                    "action_data": {
                        "actor_id": "lab-001",
                        "terms": {"revenue_share": 0.3},
                    },
                },
            })
            assert response.status_code == 200
            data = response.json()
            assert data["agent_type"] == "auditor"
            assert data["data"]["compliant"] is True

    def test_execute_invalid_agent_type(self, client):
        response = client.post("/api/v1/agents/execute", json={
            "agent_type": "nonexistent",
            "task": {},
        })
        assert response.status_code == 422
