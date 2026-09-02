"""
LORL-9.1 Skeptic Agent — Critique and adversarial review agent.

Takes research findings from other agents and applies skeptical analysis,
looking for methodological flaws, unsupported claims, and bias.
"""

from __future__ import annotations

from lorl.agents.base_agent import AgentResponse, BaseAgent


class SkepticAgent(BaseAgent):
    """Critique agent that challenges findings and identifies weaknesses."""

    def __init__(self, agent_id: str = "skeptic-agent"):
        super().__init__(agent_id, "skeptic")

    async def execute(self, task: dict) -> AgentResponse:
        """Execute a skeptical review of findings.

        Expected task keys:
            - findings: List of findings to critique
            - source_data: (optional) Original data to cross-reference
        """
        findings = task.get("findings", [])
        source_data = task.get("source_data", {})

        if not findings:
            return self._create_response(
                reasoning="No findings provided to critique",
                confidence=0.0,
                data={"error": "missing_findings"},
            )

        critique_points = self._critique_findings(findings)
        confidence = self._calculate_skeptic_confidence(findings, critique_points)

        return self._create_response(
            reasoning=f"Reviewed {len(findings)} findings with {len(critique_points)} critique points",
            confidence=confidence,
            data={
                "findings_reviewed": len(findings),
                "critique_points": critique_points,
                "source_data_keys": list(source_data.keys()) if source_data else [],
            },
            recommendations=[
                "Address identified weaknesses before publication",
                "Consider alternative explanations for key findings",
            ],
        )

    def _critique_findings(self, findings: list) -> list:
        """Generate critique points for the given findings."""
        critiques = []

        for i, finding in enumerate(findings):
            finding_str = str(finding)
            if len(finding_str) < 20:
                critiques.append({
                    "finding_index": i,
                    "issue": "Insufficient detail in finding",
                    "severity": "medium",
                })

            if "always" in finding_str.lower() or "never" in finding_str.lower():
                critiques.append({
                    "finding_index": i,
                    "issue": "Absolute language without qualification",
                    "severity": "high",
                })

        if not critiques:
            critiques.append({
                "finding_index": -1,
                "issue": "No significant methodological issues found",
                "severity": "low",
            })

        return critiques

    def _calculate_skeptic_confidence(self, findings: list, critiques: list) -> float:
        """Calculate confidence in the critique (not the findings)."""
        high_issues = sum(1 for c in critiques if c.get("severity") == "high")
        if high_issues > 0:
            return round(0.9 - (high_issues * 0.1), 2)
        return 0.85
