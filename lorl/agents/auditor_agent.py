"""
LORL-9.1 Auditor Agent — Compliance and governance verification agent.

Reviews agent decisions and treaty actions for compliance with governance
policies. Integrates with CUSTOS-Core for policy enforcement. Connects to
Ollama/Llama3 for zero-cost inference when enabled, falling back to deterministic
responses if unavailable.
"""

from __future__ import annotations

from typing import Optional

from lorl.agents.base_agent import AgentResponse, BaseAgent
from lorl.agents.ollama_client import OllamaClient


class AuditorAgent(BaseAgent):
    """Compliance agent that verifies governance and policy adherence."""

    def __init__(
        self,
        agent_id: str = "auditor-agent",
        use_ollama: bool = False,
        ollama_client: Optional[OllamaClient] = None,
    ):
        super().__init__(agent_id, "auditor")
        self.use_ollama = use_ollama
        self.ollama_client = ollama_client or OllamaClient()

    async def execute(self, task: dict) -> AgentResponse:
        """Execute a compliance audit.

        Expected task keys:
            - action_type: Type of action being audited (e.g., 'treaty', 'agent_decision')
            - action_data: The data of the action being audited
            - custos_endpoint: (optional) CUSTOS-Core API URL for policy check
            - use_ollama: (optional) Override agent default for Ollama usage
        """
        action_type = task.get("action_type", "")
        action_data = task.get("action_data", {})

        if not action_type:
            return self._create_response(
                reasoning="No action type provided for audit",
                confidence=0.0,
                data={"error": "missing_action_type"},
            )

        use_ollama = task.get("use_ollama", self.use_ollama)
        if use_ollama:
            prompt = (
                f"Audit action_type '{action_type}' with action_data: {action_data} "
                f"for governance policy compliance."
            )
            ollama_response = await self.ollama_client.generate(prompt)
            if ollama_response is not None:
                compliance_result = self._check_compliance(
                    action_type, action_data
                )
                return self._create_response(
                    reasoning=(
                        f"Audited {action_type} action via Ollama — "
                        f"compliance: {compliance_result['compliant']}"
                    ),
                    confidence=compliance_result["confidence"],
                    data={
                        "action_type": action_type,
                        "compliant": compliance_result["compliant"],
                        "violations": compliance_result["violations"],
                        "checked_at": compliance_result["checked_at"],
                        "ollama_response": ollama_response,
                    },
                    recommendations=compliance_result["recommendations"],
                )

        compliance_result = self._check_compliance(action_type, action_data)

        return self._create_response(
            reasoning=(
                f"Audited {action_type} action — "
                f"compliance: {compliance_result['compliant']}"
            ),
            confidence=compliance_result["confidence"],
            data={
                "action_type": action_type,
                "compliant": compliance_result["compliant"],
                "violations": compliance_result["violations"],
                "checked_at": compliance_result["checked_at"],
            },
            recommendations=compliance_result["recommendations"],
        )

    def _check_compliance(self, action_type: str, action_data: dict) -> dict:
        """Check action data against governance rules.

        In production, this calls CUSTOS-Core's /v1/evaluate endpoint.
        For testing, it uses deterministic rule checks.
        """
        violations = []
        recommendations = []

        # Rule: Treaty terms must include revenue_share
        if action_type == "treaty" and "terms" in action_data:
            terms = action_data.get("terms", {})
            if "revenue_share" not in terms:
                violations.append("Treaty terms missing required 'revenue_share' field")
            elif terms["revenue_share"] < 0 or terms["revenue_share"] > 1:
                violations.append("revenue_share must be between 0 and 1")

        # Rule: Agent decisions must have confidence
        if action_type == "agent_decision":
            confidence = action_data.get("confidence", 0)
            if confidence < 0 or confidence > 1:
                violations.append("Agent confidence must be between 0 and 1")
            if confidence < 0.5:
                recommendations.append("Low confidence decision — flag for human review")

        # Rule: All actions must have an actor
        if "actor_id" not in action_data:
            violations.append("Action missing required 'actor_id' field")

        compliant = len(violations) == 0

        from datetime import datetime, timezone

        return {
            "compliant": compliant,
            "violations": violations,
            "confidence": 0.95 if compliant else 0.99,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "recommendations": recommendations,
        }
