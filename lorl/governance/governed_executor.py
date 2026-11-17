"""
LORL-9.1 Governed Executor — Wrapper that executes agents with CUSTOS-Core policy evaluation.
"""
# Copyright (C) 2024-2026 Tavares Heath Sr. (doing business as FroLife Productions)
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import json
import uuid
from typing import Optional

from lorl.agents.base_agent import BaseAgent
from lorl.core.ledger import Event, EventLedger, EventType
from lorl.governance.custos_client import CustosClient


class GovernedExecutor:
    """Wrapper that executes an agent, evaluates results with CUSTOS, and logs to event ledger.

    Fail-closed semantics (v0.2.0+): if CUSTOS is unavailable, the agent's
    output is DENIED and withheld — no ungoverned output is ever returned.

    Governance model: this is DECISION/OUTPUT governance for side-effect-free
    (read-only research) agents — the agent computes, then CUSTOS evaluates the
    result before it is returned to the caller. It is NOT pre-execution action
    enforcement; side-effectful agents would additionally require a pre-flight
    gate that evaluates the proposed action BEFORE the consequential operation.
    """

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
        """Execute the wrapped agent task with CUSTOS policy evaluation.

        Fail-closed (input and output governance): the task intent is submitted
        to CUSTOS BEFORE the agent is dispatched, and on any refusal — policy
        DENY, unavailable gate, or a rejected request identity — the agent does
        not run at all. After an approved execution the output is checked again
        and is withheld if that check refuses it, but the second check is
        recorded as a post-execution observation: it cannot prevent the action
        that already happened, and the record says so.
        """
        effective_ledger = ledger if ledger is not None else self.ledger

        # 0. Ask first. Nothing is dispatched on a refusal.
        intent = json.dumps(task, sort_keys=True, default=str)
        pre = await self.custos_client.evaluate(content=intent)
        pre_allowed = bool(pre.get("allowed", False))
        pre_failure = pre.get("failure_class")
        pre_unavailable = pre_failure == "UNAVAILABLE" or (
            not pre_allowed and pre.get("reason") == "CUSTOS unavailable"
        )

        if not pre_allowed:
            if pre_unavailable:
                reason = "CUSTOS unavailable — execution denied (fail-closed)"
            elif pre_failure == "IDENTITY":
                reason = (
                    "CUSTOS rejected the request identity — execution denied "
                    "(fail-closed). Check the signing secret and client_id."
                )
            else:
                reason = pre.get("reason")
            refusal = {
                "agent_id": getattr(self.agent, "agent_id", None),
                "agent_type": getattr(self.agent, "agent_type", None),
                "task_id": str(uuid.uuid4()),
                "decision_stage": "pre_execution",
                "agent_executed": False,
                "custos_approved": False,
                "governance_status": "denied",
                "reason": reason,
                "triggered_rule": pre.get("triggered_rule"),
                "failure_class": pre_failure,
                "agent_output_withheld": True,
            }
            if pre_unavailable:
                refusal["fail_closed"] = True
            if effective_ledger:
                effective_ledger.append(
                    Event(
                        event_type=EventType.GOVERNANCE_CHECK,
                        actor_id=refusal["agent_id"],
                        aggregate_id=refusal["task_id"],
                        data={
                            "custos_approved": False,
                            "reason": reason,
                            "triggered_rule": pre.get("triggered_rule"),
                            "failure_class": pre_failure,
                            "decision_stage": "pre_execution",
                            "fail_closed": pre_unavailable,
                            "prevented": True,
                        },
                    )
                )
            return refusal

        # 1. Approved: now the agent may run.
        response = await self.agent.execute(task)
        resp_dict = response.to_dict()

        def _withhold_output(d: dict) -> dict:
            """Strip every output-bearing field from a denied response.

            Fix (Oct 2026 audit): the deny/unavailable paths previously kept
            the full agent output (data, reasoning, recommendations, metadata)
            in the returned dict while merely flagging
            ``agent_output_withheld: True`` — the withheld output was not
            actually withheld. A denied response now carries governance
            metadata only.
            """
            for key in ("data", "reasoning", "recommendations", "metadata"):
                d.pop(key, None)
            return d

        # 2. Evaluate decision content with CUSTOS
        content_str = (
            json.dumps(response.data)
            if isinstance(response.data, dict)
            else str(response.data)
        )
        eval_result = await self.custos_client.evaluate(content=content_str)

        is_unavailable = (
            not eval_result.get("allowed", False)
            and eval_result.get("reason") == "CUSTOS unavailable"
        )

        if is_unavailable:
            # Fail-closed: CUSTOS unavailable → DENY execution
            # No 'ungoverned' path — agent output is not returned
            resp_dict["custos_approved"] = False
            resp_dict["governance_status"] = "denied"
            resp_dict["reason"] = "CUSTOS unavailable — execution denied (fail-closed)"
            resp_dict["agent_output_withheld"] = True
            resp_dict = _withhold_output(resp_dict)

            if effective_ledger:
                effective_ledger.append(
                    Event(
                        event_type=EventType.GOVERNANCE_CHECK,
                        actor_id=response.agent_id,
                        aggregate_id=response.task_id,
                        data={
                            "custos_approved": False,
                            "reason": "CUSTOS unavailable",
                            "fail_closed": True,
                        },
                    )
                )
            return resp_dict

        if eval_result.get("allowed", False):
            # CUSTOS approved execution
            resp_dict["custos_approved"] = True
            resp_dict["governance_status"] = "approved"
            resp_dict["decision_stage"] = "pre_execution"
            resp_dict["custos_post_check_note"] = (
                "Recorded after execution; this check did not prevent the action."
            )
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
            resp_dict["governance_status"] = "denied"
            resp_dict["reason"] = eval_result.get("reason")
            resp_dict["triggered_rule"] = eval_result.get("triggered_rule")
            resp_dict["agent_output_withheld"] = True
            resp_dict = _withhold_output(resp_dict)

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
