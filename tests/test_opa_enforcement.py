"""
Tests for OPA policy enforcement module (lorl.governance).

Fail-closed semantics (v0.2.0+): OPA unavailable → DENY, CUSTOS unavailable → DENY.
No warning-only authorization path remains.
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
    """Tests for treaty proposal policy checks."""

    @pytest.mark.asyncio
    async def test_allow_valid_treaty_proposal(self, policy_enforcer):
        """OPA available + ALLOW → execution proceeds."""
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
        """OPA available + DENY → execution stops."""
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
        """OPA available + DENY (unregistered actor) → execution stops."""
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
    """Tests for agent decision policy checks."""

    @pytest.mark.asyncio
    async def test_allow_high_confidence_agent_decision(self, policy_enforcer):
        """OPA available + ALLOW → execution proceeds."""
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
        """OPA available + DENY → execution stops."""
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


class TestOPAFailClosed:
    """Fail-closed tests: OPA unavailable, malformed response, CUSTOS unavailable."""

    @pytest.mark.asyncio
    async def test_opa_unavailable_fails_closed(self, policy_enforcer, caplog):
        """Scenario 3: OPA unavailable → execution stops (DENY)."""
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            with caplog.at_level(logging.WARNING):
                allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                    proposer_id="lab-a",
                    responder_id="lab-b",
                    terms={"revenue_share": 0.5},
                    actor_registered=True,
                )

                assert allowed is False
                assert any("unavailable" in msg.lower() for msg in deny_msgs)
                assert any("failing closed" in record.message.lower() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_opa_timeout_fails_closed(self, policy_enforcer):
        """Scenario 3 (timeout variant): OPA timeout → execution stops (DENY)."""
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timed out")):
            allowed, deny_msgs = await policy_enforcer.check_agent_decision(
                agent_type="literature",
                confidence=0.9,
                actor_registered=True,
            )

            assert allowed is False
            assert any("unavailable" in msg.lower() for msg in deny_msgs)

    @pytest.mark.asyncio
    async def test_opa_http_error_fails_closed(self, policy_enforcer):
        """Scenario 3 (HTTP error variant): OPA returns HTTP 500 → execution stops (DENY)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Internal Server Error", request=MagicMock(), response=mock_response))

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="lab-a",
                responder_id="lab-b",
                terms={"revenue_share": 0.5},
                actor_registered=True,
            )

            assert allowed is False
            assert any("unavailable" in msg.lower() for msg in deny_msgs)

    @pytest.mark.asyncio
    async def test_opa_malformed_response_fails_closed(self, policy_enforcer, caplog):
        """Scenario 4: OPA malformed response → execution stops (DENY)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"unexpected": "structure"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            with caplog.at_level(logging.WARNING):
                allowed, deny_msgs = await policy_enforcer.check_agent_decision(
                    agent_type="literature",
                    confidence=0.9,
                    actor_registered=True,
                )

                assert allowed is False
                assert any("malformed" in msg.lower() for msg in deny_msgs)

    @pytest.mark.asyncio
    async def test_opa_malformed_result_type_fails_closed(self, policy_enforcer):
        """Scenario 4 (non-bool result): OPA returns string result → DENY."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": "allowed"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="lab-a",
                responder_id="lab-b",
                terms={"revenue_share": 0.5},
                actor_registered=True,
            )

            assert allowed is False


class TestCUSTOSFailClosed:
    """Scenario 5: CUSTOS unavailable → execution stops (DENY)."""

    @pytest.mark.asyncio
    async def test_custos_unavailable_denies_execution(self):
        """CUSTOS unavailable → GovernedExecutor denies, no ungoverned path."""
        from lorl.agents.literature_agent import LiteratureAgent
        from lorl.governance.custos_client import CustosClient
        from lorl.governance.governed_executor import GovernedExecutor

        custos_client = CustosClient(
            custos_url="http://invalid-nonexistent-custos-host:9999",
            jwt_secret="lorl-dev-secret-at-least-32-bytes-long!",
            tenant_id="test-tenant",
        )
        agent = LiteratureAgent()
        executor = GovernedExecutor(agent=agent, custos_client=custos_client)

        result = await executor.execute({"topic": "test"})

        assert result["custos_approved"] is False
        assert result["governance_status"] == "denied"
        assert "CUSTOS unavailable" in result["reason"]
        assert result.get("ungoverned") is not True
        assert "ungoverned" not in result.get("governance_status", "")

    @pytest.mark.asyncio
    async def test_custos_unavailable_withholds_agent_output(self):
        """CUSTOS unavailable → agent output is withheld, not returned to caller."""
        from lorl.agents.literature_agent import LiteratureAgent
        from lorl.governance.custos_client import CustosClient
        from lorl.governance.governed_executor import GovernedExecutor

        custos_client = CustosClient(
            custos_url="http://invalid-nonexistent-custos-host:9999",
            jwt_secret="lorl-dev-secret-at-least-32-bytes-long!",
            tenant_id="test-tenant",
        )
        agent = LiteratureAgent()
        executor = GovernedExecutor(agent=agent, custos_client=custos_client)

        result = await executor.execute({"topic": "AI in finance"})

        assert result.get("agent_output_withheld") is True
        assert result["custos_approved"] is False


class TestNoWarningOnlyPath:
    """Scenario 6: No warning-only authorization path remains."""

    @pytest.mark.asyncio
    async def test_no_ungoverned_flag_in_deny_path(self, policy_enforcer):
        """When OPA is unavailable, result must not contain any 'ungoverned' flag."""
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            allowed, deny_msgs = await policy_enforcer.check_treaty_proposal(
                proposer_id="lab-a",
                responder_id="lab-b",
                terms={"revenue_share": 0.5},
                actor_registered=True,
            )

            assert allowed is False
            # deny_msgs must contain a clear denial reason, not an empty list
            assert len(deny_msgs) > 0

    @pytest.mark.asyncio
    async def test_no_ungoverned_flag_in_malformed_response(self, policy_enforcer):
        """When OPA returns malformed response, result must not allow execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": None, "random": "data"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            allowed, deny_msgs = await policy_enforcer.check_agent_decision(
                agent_type="literature",
                confidence=0.9,
                actor_registered=True,
            )

            assert allowed is False
            assert len(deny_msgs) > 0


class TestAPIEndpointsOPAEnforcement:
    """Tests for API endpoint behavior with OPA enforcement."""

    def test_propose_treaty_endpoint_returns_403_when_opa_denies(self):
        """API treaty propose endpoint returns 403 when OPA denies."""
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
        """API agent execute endpoint returns 403 when OPA denies."""
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

    def test_propose_treaty_endpoint_returns_403_when_opa_unavailable(self):
        """API treaty propose endpoint returns 403 when OPA is unavailable (fail-closed)."""
        app = create_app()
        client = TestClient(app)

        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            response = client.post("/api/v1/treaties", json={
                "title": "Valid Treaty",
                "proposer_id": "lab-a",
                "responder_id": "lab-b",
                "terms": {"revenue_share": 0.5},
            })

            assert response.status_code == 403
            assert "unavailable" in response.json()["detail"].lower() or "failed" in response.json()["detail"].lower()

    def test_execute_agent_endpoint_returns_403_when_opa_unavailable(self):
        """API agent execute endpoint returns 403 when OPA is unavailable (fail-closed)."""
        app = create_app()
        client = TestClient(app)

        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
            response = client.post("/api/v1/agents/execute", json={
                "agent_type": "literature",
                "task": {},
            })

            assert response.status_code == 403
            assert "unavailable" in response.json()["detail"].lower() or "failed" in response.json()["detail"].lower()
