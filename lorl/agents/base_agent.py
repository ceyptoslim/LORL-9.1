"""
LORL-9.1 Base Agent — Abstract interface for all LORL agents.

All agents (Literature, Skeptic, Auditor) implement this interface.
The execute() method takes a task dict and returns an AgentResponse.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentResponse:
    """Standard response from any LORL agent."""

    agent_id: str
    agent_type: str
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reasoning: str = ""
    confidence: float = 0.0
    data: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize response to dict."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "task_id": self.task_id,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "data": self.data,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class BaseAgent(ABC):
    """Abstract base class for all LORL agents."""

    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.execution_count = 0

    @abstractmethod
    async def execute(self, task: dict) -> AgentResponse:
        """Execute the agent's task and return a response."""
        ...

    def _create_response(
        self,
        reasoning: str,
        confidence: float,
        data: Optional[dict] = None,
        recommendations: Optional[list] = None,
    ) -> AgentResponse:
        """Helper to create a standardized response."""
        self.execution_count += 1
        return AgentResponse(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            reasoning=reasoning,
            confidence=confidence,
            data=data or {},
            recommendations=recommendations or [],
        )
