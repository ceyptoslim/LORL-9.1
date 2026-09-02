"""
Tests for Ollama/Llama3 integration across LORL agents.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from lorl.agents.auditor_agent import AuditorAgent
from lorl.agents.literature_agent import LiteratureAgent
from lorl.agents.ollama_client import OllamaClient
from lorl.agents.skeptic_agent import SkepticAgent


class TestOllamaClient:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        client = OllamaClient()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Llama3 generated text"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            result = await client.generate("Test prompt")
            assert result == "Llama3 generated text"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_connection_error_fallback(self):
        client = OllamaClient()
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            result = await client.generate("Test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_generate_timeout_fallback(self):
        client = OllamaClient()
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Timed out")
            result = await client.generate("Test prompt")
            assert result is None


class TestLiteratureAgentOllama:
    @pytest.mark.asyncio
    async def test_literature_agent_deterministic_mode(self):
        """(a) Agent works with use_ollama=False (deterministic)."""
        agent = LiteratureAgent("researcher-1", use_ollama=False)
        response = await agent.execute({"topic": "Quantum Computing"})
        assert response.agent_type == "literature"
        assert "Quantum Computing" in response.reasoning
        assert "ollama_response" not in response.data
        assert len(response.data["key_findings"]) > 0

    @pytest.mark.asyncio
    async def test_literature_agent_ollama_unavailable_fallback(self):
        """(b) Agent gracefully falls back when Ollama is unavailable."""
        agent = LiteratureAgent("researcher-1", use_ollama=True)
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            response = await agent.execute({"topic": "Quantum Computing"})
            assert response.agent_type == "literature"
            assert "Quantum Computing" in response.reasoning
            assert "ollama_response" not in response.data
            assert len(response.data["key_findings"]) > 0

    @pytest.mark.asyncio
    async def test_literature_agent_ollama_success(self):
        """(c) Agent uses Ollama response when available."""
        agent = LiteratureAgent("researcher-1", use_ollama=True)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Quantum computing enables exponential speedup."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            response = await agent.execute({"topic": "Quantum Computing"})
            assert response.agent_type == "literature"
            assert "via Ollama" in response.reasoning
            assert (
                response.data["ollama_response"]
                == "Quantum computing enables exponential speedup."
            )
            assert response.data["key_findings"] == [
                "Quantum computing enables exponential speedup."
            ]


class TestSkepticAgentOllama:
    @pytest.mark.asyncio
    async def test_skeptic_agent_deterministic_mode(self):
        """(a) Agent works with use_ollama=False (deterministic)."""
        agent = SkepticAgent("skeptic-1", use_ollama=False)
        response = await agent.execute({
            "findings": ["Always trust deep learning"],
        })
        assert response.agent_type == "skeptic"
        assert "ollama_response" not in response.data
        assert response.data["findings_reviewed"] == 1

    @pytest.mark.asyncio
    async def test_skeptic_agent_ollama_unavailable_fallback(self):
        """(b) Agent gracefully falls back when Ollama is unavailable."""
        agent = SkepticAgent("skeptic-1", use_ollama=True)
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            response = await agent.execute({
                "findings": ["Always trust deep learning"],
            })
            assert response.agent_type == "skeptic"
            assert "ollama_response" not in response.data
            assert response.data["findings_reviewed"] == 1

    @pytest.mark.asyncio
    async def test_skeptic_agent_ollama_success(self):
        """(c) Agent uses Ollama response when available."""
        agent = SkepticAgent("skeptic-1", use_ollama=True)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Sample size is insufficient to support sweeping claim."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            response = await agent.execute({
                "findings": ["Always trust deep learning"],
            })
            assert response.agent_type == "skeptic"
            assert "via Ollama" in response.reasoning
            assert (
                response.data["ollama_response"]
                == "Sample size is insufficient to support sweeping claim."
            )
            assert (
                response.data["critique_points"][0]["issue"]
                == "Sample size is insufficient to support sweeping claim."
            )


class TestAuditorAgentOllama:
    @pytest.mark.asyncio
    async def test_auditor_agent_deterministic_mode(self):
        """(a) Agent works with use_ollama=False (deterministic)."""
        agent = AuditorAgent("auditor-1", use_ollama=False)
        response = await agent.execute({
            "action_type": "treaty",
            "action_data": {
                "actor_id": "lab-001",
                "terms": {"revenue_share": 0.3},
            },
        })
        assert response.agent_type == "auditor"
        assert "ollama_response" not in response.data
        assert response.data["compliant"] is True

    @pytest.mark.asyncio
    async def test_auditor_agent_ollama_unavailable_fallback(self):
        """(b) Agent gracefully falls back when Ollama is unavailable."""
        agent = AuditorAgent("auditor-1", use_ollama=True)
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection refused")
            response = await agent.execute({
                "action_type": "treaty",
                "action_data": {
                    "actor_id": "lab-001",
                    "terms": {"revenue_share": 0.3},
                },
            })
            assert response.agent_type == "auditor"
            assert "ollama_response" not in response.data
            assert response.data["compliant"] is True

    @pytest.mark.asyncio
    async def test_auditor_agent_ollama_success(self):
        """(c) Agent uses Ollama response when available."""
        agent = AuditorAgent("auditor-1", use_ollama=True)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Audit analysis: compliant with policy v1.2."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response
            response = await agent.execute({
                "action_type": "treaty",
                "action_data": {
                    "actor_id": "lab-001",
                    "terms": {"revenue_share": 0.3},
                },
            })
            assert response.agent_type == "auditor"
            assert "via Ollama" in response.reasoning
            assert (
                response.data["ollama_response"]
                == "Audit analysis: compliant with policy v1.2."
            )
            assert response.data["compliant"] is True
