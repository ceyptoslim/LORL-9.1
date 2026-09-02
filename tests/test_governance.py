"""
Tests for LORL-9.1 Governance wiring and CUSTOS-Core integration.

Fail-closed semantics (v0.2.0+): CUSTOS unavailable → DENY, no ungoverned path.
"""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

from lorl.agents import LiteratureAgent
from lorl.api.main import create_app
from lorl.core.ledger import EventLedger, EventType
from lorl.governance import CustosClient, GovernedExecutor

TEST_JWT_SECRET = "test-secret-key-at-least-32-bytes-long!"


# (a) CustosClient creates valid JWT tokens with sub bound to tenant_id
def test_custos_client_creates_valid_jwt():
    client = CustosClient(
        custos_url="http://localhost:8000",
        jwt_secret=TEST_JWT_SECRET,
        tenant_id="tenant-lab-alpha",
    )
    token = client.create_token()
    assert isinstance(token, str)

    decoded = jwt.decode(token, TEST_JWT_SECRET, algorithms=["HS256"])
    # Security: JWT sub claim is bound to tenant_id to prevent cross-tenant access (fixes CUSTOS-CORE audit finding)
    assert decoded["sub"] == "tenant-lab-alpha"
    assert decoded["tenant_id"] == "tenant-lab-alpha"


@pytest.mark.asyncio
async def test_custos_client_connection_failure():
    # Use invalid URL to simulate connection error
    client = CustosClient(
        custos_url="http://invalid-nonexistent-custos-host:9999",
        jwt_secret=TEST_JWT_SECRET,
        tenant_id="tenant-1",
    )
    result = await client.evaluate(content="test data")
    assert result == {"allowed": False, "reason": "CUSTOS unavailable"}


@pytest.mark.asyncio
async def test_custos_client_non_200_response(monkeypatch):
    client = CustosClient(
        custos_url="http://localhost:8000",
        jwt_secret=TEST_JWT_SECRET,
        tenant_id="tenant-1",
    )

    class DummyResponse:
        status_code = 500

    async def mock_post(*args, **kwargs):
        return DummyResponse()

    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)
    result = await client.evaluate(content="test data")
    assert result == {"allowed": False, "reason": "CUSTOS returned HTTP 500"}


# (b) GovernedExecutor records AGENT_DECISION when CUSTOS allows
@pytest.mark.asyncio
async def test_governed_executor_records_agent_decision_when_allowed(monkeypatch):
    ledger = EventLedger("sqlite:///:memory:")
    custos_client = CustosClient("http://localhost:8000", TEST_JWT_SECRET, "tenant-1")

    async def mock_evaluate(content, client_id="lorl"):
        return {"allowed": True, "audit_record_hash": "hash_abc_123"}

    monkeypatch.setattr(custos_client, "evaluate", mock_evaluate)

    agent = LiteratureAgent()
    executor = GovernedExecutor(agent=agent, custos_client=custos_client, ledger=ledger)

    result = await executor.execute({"topic": "AI Safety & Governance"})

    assert result["custos_approved"] is True
    assert result["governance_status"] == "approved"
    assert result["custos_audit_hash"] == "hash_abc_123"

    events = ledger.get_all_events()
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.AGENT_DECISION.value
    assert events[0]["data"]["custos_approved"] is True
    assert events[0]["data"]["custos_audit_hash"] == "hash_abc_123"


# (c) GovernedExecutor records GOVERNANCE_CHECK when CUSTOS denies
@pytest.mark.asyncio
async def test_governed_executor_records_governance_check_when_denied(monkeypatch):
    ledger = EventLedger("sqlite:///:memory:")
    custos_client = CustosClient("http://localhost:8000", TEST_JWT_SECRET, "tenant-1")

    async def mock_evaluate(content, client_id="lorl"):
        return {
            "allowed": False,
            "reason": "Policy violation: high risk domain",
            "triggered_rule": "rule_risk_policy_01",
        }

    monkeypatch.setattr(custos_client, "evaluate", mock_evaluate)

    agent = LiteratureAgent()
    executor = GovernedExecutor(agent=agent, custos_client=custos_client, ledger=ledger)

    result = await executor.execute({"topic": "Prohibited Topic"})

    assert result["custos_approved"] is False
    assert result["governance_status"] == "denied"
    assert result["reason"] == "Policy violation: high risk domain"
    assert result["triggered_rule"] == "rule_risk_policy_01"
    assert result.get("agent_output_withheld") is True

    events = ledger.get_all_events()
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.GOVERNANCE_CHECK.value
    assert events[0]["data"]["custos_approved"] is False
    assert events[0]["data"]["reason"] == "Policy violation: high risk domain"


# (d) GovernedExecutor handles CUSTOS unavailability — FAIL CLOSED (v0.2.0+)
@pytest.mark.asyncio
async def test_governed_executor_handles_custos_unavailability(monkeypatch):
    """CUSTOS unavailable → DENY execution, no ungoverned path."""
    ledger = EventLedger("sqlite:///:memory:")
    custos_client = CustosClient("http://localhost:8000", TEST_JWT_SECRET, "tenant-1")

    async def mock_evaluate(content, client_id="lorl"):
        return {"allowed": False, "reason": "CUSTOS unavailable"}

    monkeypatch.setattr(custos_client, "evaluate", mock_evaluate)

    agent = LiteratureAgent()
    executor = GovernedExecutor(agent=agent, custos_client=custos_client, ledger=ledger)

    result = await executor.execute({"topic": "AI Safety"})

    # Fail-closed: execution is denied, no ungoverned path
    assert result["custos_approved"] is False
    assert result["governance_status"] == "denied"
    assert "CUSTOS unavailable" in result["reason"]
    assert result.get("ungoverned") is not True
    assert result.get("agent_output_withheld") is True

    events = ledger.get_all_events()
    assert len(events) == 1
    assert events[0]["event_type"] == EventType.GOVERNANCE_CHECK.value
    assert events[0]["data"]["custos_approved"] is False
    assert events[0]["data"]["fail_closed"] is True


# (e) The /api/v1/agents/governed-execute endpoint works
class TestGovernedExecutionAPI:
    def test_governed_execute_endpoint_success(self, monkeypatch):
        app = create_app()
        client = TestClient(app)

        async def mock_evaluate(self, content, client_id="lorl"):
            return {"allowed": True, "audit_record_hash": "audit_endpoint_hash"}

        monkeypatch.setattr(CustosClient, "evaluate", mock_evaluate)

        response = client.post(
            "/api/v1/agents/governed-execute",
            json={
                "agent_type": "literature",
                "task": {"topic": "Governance Frameworks"},
                "custos_url": "http://localhost:8000",
                "tenant_id": "tenant-lab-1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "literature"
        assert data["custos_approved"] is True
        assert data["governance_status"] == "approved"
        assert data["custos_audit_hash"] == "audit_endpoint_hash"

    def test_governed_execute_endpoint_denied(self, monkeypatch):
        app = create_app()
        client = TestClient(app)

        async def mock_evaluate(self, content, client_id="lorl"):
            return {
                "allowed": False,
                "reason": "Policy violation",
                "triggered_rule": "rule_01",
            }

        monkeypatch.setattr(CustosClient, "evaluate", mock_evaluate)

        response = client.post(
            "/api/v1/agents/governed-execute",
            json={
                "agent_type": "skeptic",
                "task": {"findings": ["Unverified claim"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "skeptic"
        assert data["custos_approved"] is False
        assert data["governance_status"] == "denied"
        assert data["reason"] == "Policy violation"

    def test_governed_execute_endpoint_custos_unavailable(self, monkeypatch):
        """CUSTOS unavailable via API → execution denied, no ungoverned path."""
        app = create_app()
        client = TestClient(app)

        async def mock_evaluate(self, content, client_id="lorl"):
            return {"allowed": False, "reason": "CUSTOS unavailable"}

        monkeypatch.setattr(CustosClient, "evaluate", mock_evaluate)

        response = client.post(
            "/api/v1/agents/governed-execute",
            json={
                "agent_type": "auditor",
                "task": {
                    "action_type": "treaty",
                    "action_data": {
                        "actor_id": "lab-01",
                        "terms": {"revenue_share": 0.5},
                    },
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_type"] == "auditor"
        assert data["custos_approved"] is False
        assert data["governance_status"] == "denied"
        assert "CUSTOS unavailable" in data["reason"]
        assert data.get("ungoverned") is not True
