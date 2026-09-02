"""
LORL-9.1 Policy Enforcer — High-level governance policy enforcement wrapper.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

from typing import Any, Optional

from lorl.governance.opa_client import OPAClient


class PolicyEnforcer:
    """Wrapper that checks OPA before allowing treaty operations and agent decisions."""

    def __init__(
        self,
        opa_client: Optional[OPAClient] = None,
        opa_url: str = "http://localhost:8181",
    ) -> None:
        self.opa_client = opa_client or OPAClient(opa_url=opa_url)

    async def check_treaty_proposal(
        self,
        proposer_id: str,
        responder_id: str,
        terms: dict[str, Any],
        actor_registered: bool = True,
    ) -> tuple[bool, list[str]]:
        """Check if a treaty proposal complies with OPA policy."""
        input_data = {
            "action_type": "treaty_proposal",
            "proposer_id": proposer_id,
            "responder_id": responder_id,
            "terms": terms,
            "actor_registered": actor_registered,
        }
        return await self.opa_client.check_policy(input_data)

    async def check_agent_decision(
        self,
        agent_type: str,
        confidence: float = 1.0,
        actor_registered: bool = True,
        custos_allowed: bool = True,
    ) -> tuple[bool, list[str]]:
        """Check if an agent decision complies with OPA policy."""
        input_data = {
            "action_type": "agent_decision",
            "agent_type": agent_type,
            "confidence": confidence,
            "actor_registered": actor_registered,
            "custos_allowed": custos_allowed,
        }
        return await self.opa_client.check_policy(input_data)
