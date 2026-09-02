"""
LORL-9.1 Literature Agent — Research and literature review agent.

Analyzes research topics, summarizes findings, and produces structured
literature reviews. In production, this would connect to Ollama/Llama3
for zero-cost inference. For testing, it uses deterministic mock responses.
"""

from __future__ import annotations

from lorl.agents.base_agent import AgentResponse, BaseAgent


class LiteratureAgent(BaseAgent):
    """Research agent that analyzes topics and produces literature summaries."""

    def __init__(self, agent_id: str = "literature-agent"):
        super().__init__(agent_id, "literature")

    async def execute(self, task: dict) -> AgentResponse:
        """Execute a literature research task.

        Expected task keys:
            - topic: The research topic to analyze
            - depth: (optional) Research depth — 'quick' or 'comprehensive'
        """
        topic = task.get("topic", "")
        depth = task.get("depth", "comprehensive")

        if not topic:
            return self._create_response(
                reasoning="No topic provided",
                confidence=0.0,
                data={"error": "missing_topic"},
            )

        # In production, this calls Ollama/Llama3 for zero-cost inference
        # For now, deterministic response based on topic analysis
        reasoning = f"Researched '{topic}' at {depth} depth"
        findings = self._analyze_topic(topic, depth)

        return self._create_response(
            reasoning=reasoning,
            confidence=findings["confidence"],
            data={
                "topic": topic,
                "depth": depth,
                "key_findings": findings["key_findings"],
                "source_count": findings["source_count"],
            },
            recommendations=findings["recommendations"],
        )

    def _analyze_topic(self, topic: str, depth: str) -> dict:
        """Deterministic topic analysis (replaces LLM call for testing)."""
        topic_words = len(topic.split())
        topic_len = len(topic)

        confidence = min(0.5 + (topic_len / 200), 0.95)

        if depth == "quick":
            source_count = max(3, topic_words)
            key_findings = [f"Quick scan of '{topic}'"]
        else:
            source_count = max(10, topic_words * 3)
            key_findings = [
                f"Comprehensive review of '{topic}'",
                f"Identified {source_count} relevant sources",
                "Cross-referenced findings across sources",
            ]

        recommendations = [
            f"Further investigation recommended for: {topic}",
            "Validate findings with peer review",
        ]

        return {
            "confidence": round(confidence, 2),
            "key_findings": key_findings,
            "source_count": source_count,
            "recommendations": recommendations,
        }
