# LORL-9.1 Architecture

## System Overview

LORL-9.1 is an event-sourced institutional intelligence OS designed for
multi-lab collaboration with cryptographic identity, governance, and
audit trails.

## Components

### Identity Layer (`lorl/core/identity.py`)
- Ed25519 keypair generation for each lab
- Sign/verify for treaties, ledger events, and audit records
- Public key export as raw bytes or hex
- Identity hash for deduplication (SHA-256 of lab_id + public_key)

### Event Ledger (`lorl/core/ledger.py`)
- Append-only event store backed by SQLite (dev) or PostgreSQL (production)
- Event types: lab_registered, treaty_proposed/accepted/rejected/expired, agent_decision, governance_check
- Content hashing (SHA-256) for tamper detection
- Integrity verification via `verify_integrity()`
- Sequence numbers per aggregate for ordered replay

### Treaty Engine (`lorl/core/treaty_engine.py`)
- State machine: PROPOSED → ACCEPTED/REJECTED → EXPIRED/CANCELLED
- Only the responder can accept or reject
- Either party can cancel a proposed or accepted treaty
- Invalid transitions raise `TreatyTransitionError`
- Terms are a flexible dict (e.g., `{"revenue_share": 0.3}`)

### Multi-Agent Orchestration (`lorl/agents/`)
- `BaseAgent` — abstract interface with `execute()` → `AgentResponse`
- `LiteratureAgent` — research and literature review
- `SkepticAgent` — critique and adversarial review
- `AuditorAgent` — compliance verification, integrates with CUSTOS-Core
- All agents use deterministic responses (production: Ollama/Llama3)

### API Layer (`lorl/api/`)
- FastAPI with CORS, health/readiness endpoints
- Lab registration, treaty management, agent execution, audit log
- Pydantic models for request validation

### Governance (`policies/lorl_governance.rego`)
- OPA/Rego policy rules for treaty proposals and agent decisions
- Default deny, explicit allow conditions
- Revenue share validation, confidence thresholds, actor registration checks

## CUSTOS-Core Integration

LORL-9.1 integrates with CUSTOS-Core as the governance enforcement layer:

1. Agent produces a recommendation
2. Recommendation submitted to CUSTOS `/v1/evaluate` for policy check
3. If allowed → recorded in LORL event ledger
4. If denied → blocked, not recorded

This ensures all agent decisions pass through CUSTOS policy enforcement
before becoming part of the institutional record.

## Data Flow

```
Lab Registration → Ed25519 Keypair → Identity Stored
         ↓
Treaty Proposal → TreatyEngine.propose() → Event (TREATY_PROPOSED) → Ledger
         ↓
Treaty Accept → TreatyEngine.accept() → Event (TREATY_ACCEPTED) → Ledger
         ↓
Agent Task → Agent.execute() → AgentResponse
         ↓
CUSTOS /v1/evaluate → allowed? → Event (AGENT_DECISION) → Ledger
         ↓
Audit Query → Ledger.get_all_events() → verify_integrity()
```

## Deployment

- **Development**: SQLite, `docker compose up`
- **Production**: PostgreSQL, Kubernetes, OPA sidecar
- **CI/CD**: GitHub Actions (Python 3.10/3.11/3.12), Docker build check
