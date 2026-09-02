"""
LORL-9.1 API Routes — All REST endpoint handlers.

Routes are registered on the FastAPI app via register_routes(app).
This keeps the main.py clean and makes routes testable independently.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from lorl import __version__
from lorl.agents import AuditorAgent, LiteratureAgent, SkepticAgent
from lorl.core.identity import Identity
from lorl.core.ledger import Event, EventType
from lorl.core.treaty_engine import TreatyEngine

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class LabRegistration(BaseModel):
    lab_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(default="", max_length=256)


class TreatyProposal(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    proposer_id: str = Field(..., min_length=1)
    responder_id: str = Field(..., min_length=1)
    terms: dict = Field(...)


class TreatyAction(BaseModel):
    actor_id: str = Field(..., min_length=1)


class AgentTask(BaseModel):
    agent_type: str = Field(..., pattern="^(literature|skeptic|auditor)$")
    task: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Route Registration
# ---------------------------------------------------------------------------

def register_routes(app: FastAPI) -> None:
    """Register all API routes on the given FastAPI app."""
    engine = TreatyEngine()

    # --- Health & Readiness ---

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    async def ready():
        ledger = app.state.ledger
        event_count = ledger.get_event_count()
        return {
            "status": "ready",
            "version": __version__,
            "event_count": event_count,
        }

    # --- Lab Registration ---

    @app.post("/api/v1/labs")
    async def register_lab(reg: LabRegistration):
        labs = app.state.labs
        ledger = app.state.ledger

        if reg.lab_id in labs:
            raise HTTPException(409, f"Lab '{reg.lab_id}' already registered")

        identity = Identity.create(reg.lab_id, reg.name)
        lab_data = identity.to_dict()
        labs[reg.lab_id] = lab_data

        event = Event(
            event_type=EventType.LAB_REGISTERED,
            actor_id=reg.lab_id,
            aggregate_id=reg.lab_id,
            data=lab_data,
        )
        ledger.append(event)

        return {"lab_id": reg.lab_id, "public_key": lab_data["public_key"], "identity_hash": lab_data["identity_hash"]}

    @app.get("/api/v1/labs")
    async def list_labs():
        return {"labs": list(app.state.labs.values()), "count": len(app.state.labs)}

    # --- Treaty Management ---

    @app.post("/api/v1/treaties")
    async def propose_treaty(proposal: TreatyProposal):
        treaties = app.state.treaties
        ledger = app.state.ledger

        try:
            treaty = engine.propose(
                title=proposal.title,
                proposer_id=proposal.proposer_id,
                responder_id=proposal.responder_id,
                terms=proposal.terms,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

        treaties[treaty.treaty_id] = treaty
        ledger.append(Event(
            event_type=EventType.TREATY_PROPOSED,
            actor_id=proposal.proposer_id,
            aggregate_id=treaty.treaty_id,
            data=treaty.to_dict(),
        ))

        return treaty.to_dict()

    @app.post("/api/v1/treaties/{treaty_id}/accept")
    async def accept_treaty(treaty_id: str, action: TreatyAction):
        treaties = app.state.treaties
        ledger = app.state.ledger

        if treaty_id not in treaties:
            raise HTTPException(404, f"Treaty '{treaty_id}' not found")

        treaty = treaties[treaty_id]
        try:
            updated = engine.accept(treaty, action.actor_id)
        except ValueError as e:
            raise HTTPException(403, str(e))

        treaties[treaty_id] = updated
        ledger.append(Event(
            event_type=EventType.TREATY_ACCEPTED,
            actor_id=action.actor_id,
            aggregate_id=treaty_id,
            data=updated.to_dict(),
        ))

        return updated.to_dict()

    @app.post("/api/v1/treaties/{treaty_id}/reject")
    async def reject_treaty(treaty_id: str, action: TreatyAction):
        treaties = app.state.treaties
        ledger = app.state.ledger

        if treaty_id not in treaties:
            raise HTTPException(404, f"Treaty '{treaty_id}' not found")

        treaty = treaties[treaty_id]
        try:
            updated = engine.reject(treaty, action.actor_id)
        except ValueError as e:
            raise HTTPException(403, str(e))

        treaties[treaty_id] = updated
        ledger.append(Event(
            event_type=EventType.TREATY_REJECTED,
            actor_id=action.actor_id,
            aggregate_id=treaty_id,
            data=updated.to_dict(),
        ))

        return updated.to_dict()

    @app.get("/api/v1/treaties")
    async def list_treaties(status: Optional[str] = None):
        treaties = app.state.treaties
        result = []
        for tid, t in treaties.items():
            if status is None or t.status.value == status:
                result.append(t.to_dict())
        return {"treaties": result, "count": len(result)}

    # --- Audit / Ledger ---

    @app.get("/api/v1/audit")
    async def get_audit_log():
        ledger = app.state.ledger
        events = ledger.get_all_events()
        verified = ledger.verify_integrity()
        return {
            "events": events,
            "count": len(events),
            "integrity_verified": verified,
        }

    # --- Agent Execution ---

    @app.post("/api/v1/agents/execute")
    async def execute_agent(task: AgentTask):
        if task.agent_type == "literature":
            agent = LiteratureAgent()
        elif task.agent_type == "skeptic":
            agent = SkepticAgent()
        elif task.agent_type == "auditor":
            agent = AuditorAgent()
        else:
            raise HTTPException(400, f"Unknown agent type: {task.agent_type}")

        response = await agent.execute(task.task)

        ledger = app.state.ledger
        ledger.append(Event(
            event_type=EventType.AGENT_DECISION,
            actor_id=response.agent_id,
            aggregate_id=response.task_id,
            data=response.to_dict(),
        ))

        return response.to_dict()
