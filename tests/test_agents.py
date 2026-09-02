"""
Tests for LORL-9.1 Agents — Multi-agent orchestration.
"""

import pytest

from lorl.agents.auditor_agent import AuditorAgent
from lorl.agents.literature_agent import LiteratureAgent
from lorl.agents.skeptic_agent import SkepticAgent


class TestLiteratureAgent:
    @pytest.mark.asyncio
    async def test_execute_with_topic(self):
        agent = LiteratureAgent("researcher-1")
        response = await agent.execute({"topic": "AI Governance"})
        assert response.agent_type == "literature"
        assert "AI Governance" in response.reasoning
        assert 0 < response.confidence <= 1
        assert len(response.data["key_findings"]) > 0
        assert response.data["source_count"] > 0

    @pytest.mark.asyncio
    async def test_execute_without_topic_returns_error(self):
        agent = LiteratureAgent("researcher-1")
        response = await agent.execute({})
        assert response.confidence == 0.0
        assert response.data["error"] == "missing_topic"


class TestSkepticAgent:
    @pytest.mark.asyncio
    async def test_execute_with_findings(self):
        agent = SkepticAgent("skeptic-1")
        response = await agent.execute({
            "findings": ["Always use deep learning", "Some short finding"],
        })
        assert response.agent_type == "skeptic"
        assert response.data["findings_reviewed"] == 2
        assert len(response.data["critique_points"]) > 0

    @pytest.mark.asyncio
    async def test_execute_without_findings_returns_error(self):
        agent = SkepticAgent("skeptic-1")
        response = await agent.execute({})
        assert response.confidence == 0.0
        assert response.data["error"] == "missing_findings"


class TestAuditorAgent:
    @pytest.mark.asyncio
    async def test_compliant_treaty(self):
        agent = AuditorAgent("auditor-1")
        response = await agent.execute({
            "action_type": "treaty",
            "action_data": {
                "actor_id": "lab-001",
                "terms": {"revenue_share": 0.3},
            },
        })
        assert response.agent_type == "auditor"
        assert response.data["compliant"] is True
        assert len(response.data["violations"]) == 0

    @pytest.mark.asyncio
    async def test_noncompliant_treaty_missing_revenue_share(self):
        agent = AuditorAgent("auditor-1")
        response = await agent.execute({
            "action_type": "treaty",
            "action_data": {
                "actor_id": "lab-001",
                "terms": {"other_field": "value"},
            },
        })
        assert response.data["compliant"] is False
        assert any("revenue_share" in v for v in response.data["violations"])
