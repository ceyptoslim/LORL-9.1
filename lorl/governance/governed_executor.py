"""
LORL-9.1 Governed Executor — Wrapper that executes agents with CUSTOS-Core policy evaluation.
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import json
from typing import Optional

from lorl.agents.base_agent import BaseAgent
from lorl.core.ledger import Event, EventLedger, EventType
from lorl.governance.custos_client import CustosClient


class GovernedExecutor:
    """Wrapper that executes an agent, evaluates results with CUSTOS, and logs to event ledger."""

    def __init__(
        self,
        agent: BaseAgent,
        custos_client: CustosClient,
        ledger: Optional[EventLedger] = None,
    ):
        self.agent = agent
        self.custos_client = custos_client
        self.ledger = ledger

    async def execute(
        self, task: dict, ledger: Optional[EventLedger] = None
    ) -> dict:
        """Execute the wrapped agent task with CUSTOS policy evaluation."""
        effective_ledger = ledger if ledger is not None else self.ledger

        # 1. Execute agent task
        response = await self.agent.execute(task)
        resp_dict = response.to_dict()

        # 2. Evaluate decision content with CUSTOS
        content_str = (
            json.dumps(response.data)
            if isinstance(response.data, dict)
            else str(response.data)
        )
        eval_result = await self.custos_client.evaluate(
            content=content_str, client_id="lorl"
        )

        is_unavailable = (
            not eval_result.get("allowed", False)
            and eval_result.get("reason") == "CUSTOS unavailable"
        )

        if is_unavailable:
            # Handle CUSTOS unavailability gracefully: flag as ungoverned
            resp_dict["custos_approved"] = False
            resp_dict["ungoverned"] = True
            resp_dict["governance_status"] = "ungoverned"
            resp_dict["reason"] = "CUSTOS unavailable"

            if effective_ledger:
                effective_ledger.append(
                    Event(
                        event_type=EventType.AGENT_DECISION,
                        actor_id=response.agent_id,
                        aggregate_id=response.task_id,
                        data={
                            **resp_dict,
                            "ungoverned": True,
                        },
                    )
                )
            return resp_dict

        if eval_result.get("allowed", False):
            # CUSTOS approved execution
            resp_dict["custos_approved"] = True
            resp_dict["ungoverned"] = False
            resp_dict["governance_status"] = "approved"
            if "audit_record_hash" in eval_result:
                resp_dict["custos_audit_hash"] = eval_result["audit_record_hash"]

            if effective_ledger:
                effective_ledger.append(
                    Event(
                        event_type=EventType.AGENT_DECISION,
                        actor_id=response.agent_id,
                        aggregate_id=response.task_id,
                        data={
                            **resp_dict,
                            "custos_approved": True,
                            "custos_audit_hash": eval_result.get("audit_record_hash"),
                        },
                    )
                )
            return resp_dict

        else:
            # CUSTOS denied execution
            resp_dict["custos_approved"] = False
            resp_dict["ungoverned"] = False
            resp_dict["governance_status"] = "denied"
            resp_dict["reason"] = eval_result.get("reason")
            resp_dict["triggered_rule"] = eval_result.get("triggered_rule")

            if effective_ledger:
                effective_ledger.append(
                    Event(
                        event_type=EventType.GOVERNANCE_CHECK,
                        actor_id=response.agent_id,
                        aggregate_id=response.task_id,
                        data={
                            "custos_approved": False,
                            "reason": eval_result.get("reason"),
                            "triggered_rule": eval_result.get("triggered_rule"),
                        },
                    )
                )
            return resp_dict
