"""
Tests for OPA policy enforcement module (lorl.governance).
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from lorl.api.main import create_app
from lorl.governance.opa_client import OPAClient
from lorl.governance.policy_enforcer import PolicyEnforcer


@pytest.fixture
def opa_client():
    return OPAClient(opa_url="http://localhost:8181")


@pytest.fixture
def policy_enforcer(opa_client):
    return PolicyEnforcer(opa_client=opa_client)


class TestPolicyEnforcerTreatyProposals:
    """Tests for treaty proposal policy checks (a) and (b)."""

    @pytest.mark.asyncio
    async def test_allow_valid_treaty_proposal(self, policy_enforcer):
        """(a) PolicyEnforcer allows valid treaty proposals (terms include revenue_share 0-1, registered actor)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="lab-a",
                responder_id="lab-b",
                terms={"revenue_share": 0.25},
                actor_registered=True,
            )

            assert allowed is True
            assert deny_msgs == []
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["input"]["action_type"] == "treaty_proposal"
            assert call_kwargs["json"]["input"]["actor_registered"] is True
            assert call_kwargs["json"]["input"]["terms"]["revenue_share"] == 0.25

    @pytest.mark.asyncio
    async def test_deny_invalid_treaty_proposal_missing_revenue_share(self, policy_enforcer):
        """(b) PolicyEnforcer denies invalid proposals (missing revenue_share)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "deny": ["Treaty terms must include revenue_share between 0 and 1"],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="lab-a",
                responder_id="lab-b",
                terms={},
                actor_registered=True,
            )

            assert allowed is False
            assert len(deny_msgs) == 1
            assert "revenue_share" in deny_msgs[0]

    @pytest.mark.asyncio
    async def test_deny_invalid_treaty_proposal_unregistered_actor(self, policy_enforcer):
        """(b) PolicyEnforcer denies invalid proposals (unregistered actor)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "deny": ["Actor is not a registered lab"],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="unregistered-lab",
                responder_id="lab-b",
                terms={"revenue_share": 0.5},
                actor_registered=False,
            )

            assert allowed is False
            assert len(deny_msgs) == 1
            assert "registered" in deny_msgs[0]


class TestPolicyEnforcerAgentDecisions:
    """Tests for agent decision policy checks (c) and (d)."""

    @pytest.mark.asyncio
    async def test_allow_high_confidence_agent_decision(self, policy_enforcer):
        """(c) PolicyEnforcer allows high-confidence agent decisions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": True}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_agent_decision(
                agent_type="literature",
                confidence=0.85,
                actor_registered=True,
            )

            assert allowed is True
            assert deny_msgs == []

    @pytest.mark.asyncio
    async def test_deny_low_confidence_agent_decision(self, policy_enforcer):
        """(d) PolicyEnforcer denies low-confidence decisions."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "deny": ["Agent decision confidence below threshold (0.5)"],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_agent_decision(
                agent_type="skeptic",
                confidence=0.2,
                actor_registered=True,
            )

            assert allowed is False
            assert len(deny_msgs) == 1
            assert "confidence" in deny_msgs[0] or "threshold" in deny_msgs[0]


class TestOPAUnavailability:
    """Test OPA connection error / fail open (e)."""

    @pytest.mark.asyncio
    async def test_opa_unavailability_fails_open(self, policy_enforcer, caplog):
        """(e) OPA unavailability fails open (allows with warning)."""
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            with caplog.at_level(logging.WARNING):
                allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                    proposer_id="lab-a",
                    responder_id="lab-b",
                    terms={"revenue_share": 0.5},
                    actor_registered=True,
                )

                assert allowed is True
                assert deny_msgs == []
                assert any("unavailable" in record.message.lower() or "failed" in record.message.lower() for record in caplog.records)


class TestAPIEndpointsOPAEnforcement:
    """Tests for API endpoint behavior with OPA enforcement (f)."""

    def test_propose_treaty_endpoint_returns_403_when_opa_denies(self):
        """(f) API treaty propose endpoint returns 403 when OPA denies."""
        app = create_app()
        client = TestClient(app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "deny": ["Treaty terms must include revenue_share between 0 and 1"],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = client.post("/api/v1/treaties", json={
                "title": "Invalid Treaty",
                "proposer_id": "lab-a",
                "responder_id": "lab-b",
                "terms": {"invalid": "terms"},
            })

            assert response.status_code == 403
            assert "revenue_share" in response.json()["detail"] or "failed" in response.json()["detail"]

    def test_execute_agent_endpoint_returns_403_when_opa_denies(self):
        """(f) API agent execute endpoint returns 403 when OPA denies."""
        app = create_app()
        client = TestClient(app)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": False,
            "deny": ["Agent decision confidence below threshold (0.5)"],
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            response = client.post("/api/v1/agents/execute", json={
                "agent_type": "literature",
                "task": {},
            })

            assert response.status_code == 403
            assert "confidence" in response.json()["detail"] or "failed" in response.json()["detail"]
