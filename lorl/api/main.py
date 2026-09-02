"""
LORL-9.1 FastAPI Application — Institutional intelligence OS API.

Endpoints:
    GET  /health              — Service health check
    GET  /ready               — Kubernetes readiness probe
    POST /api/v1/labs         — Register a new lab identity
    GET  /api/v1/labs         — List registered labs
    POST /api/v1/treaties     — Propose a new treaty
    POST /api/v1/treaties/{treaty_id}/accept  — Accept a treaty
    POST /api/v1/treaties/{treaty_id}/reject  — Reject a treaty
    GET  /api/v1/audit        — Retrieve the full event ledger
    POST /api/v1/agents/execute — Execute an agent task
"""
# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.


# Copyright (C) 2024-2026 FroLife Productions
# Licensed under the GNU Affero General Public License v3.0 (AGPL-3.0)
# See LICENSE file for details. Commercial license available upon request.



from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lorl import __version__
from lorl.api import routes
from lorl.core.ledger import EventLedger
from lorl.governance import PolicyEnforcer


def create_app() -> FastAPI:
    """Create and configure the LORL FastAPI application."""
    app = FastAPI(
        title="LORL-9.1",
        description="Event-sourced institutional intelligence OS with Ed25519 identity, "
                     "PostgreSQL ledger, treaty engine, and CUSTOS-Core governance integration.",
        version=__version__,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In-memory state (production uses PostgreSQL-backed ledger)
    ledger = EventLedger(os.environ.get("LORL_DB_URL", "sqlite:///lorl.db"))
    labs: dict[str, dict] = {}
    treaties: dict[str, dict] = {}
    policy_enforcer = PolicyEnforcer()

    # Store references on app state
    app.state.ledger = ledger
    app.state.labs = labs
    app.state.treaties = treaties
    app.state.policy_enforcer = policy_enforcer
    app.state.start_time = datetime.now(timezone.utc)

    # Register routes
    routes.register_routes(app)

    return app


app = create_app()
