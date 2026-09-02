# LORL-9.1 — Changelog

All notable changes to this project are documented here. This changelog
follows a transparent "what we built, what we fixed, what we know is still
open" format — no claims beyond what the code and tests demonstrate.

---

## [0.2.0] — Governance Integration & Release Readiness

### Documentation
- Fixed README license badge: was "Apache 2.0", now correctly "AGPL-3.0"
- Added NOTICE.md with dual-license model, trademark notice, and CLA requirement
- Added this CHANGELOG.md

### Version
- Bumped from 0.1.0 → 0.2.0

### Known Limitations
- OPA enforcement fails OPEN (permissive) when OPA server is unavailable.
  CUSTOS-Core fails CLOSED (restrictive). This asymmetry is intentional
  for v0.2.0 — OPA is a best-effort advisory layer; CUSTOS is the
  authoritative enforcement layer. Enterprise tier may align to fail-closed.
- No tags exist prior to this release.
- No PostgreSQL backend (SQLite only).
- No blockchain settlement (architecture target).

---

## [0.1.0] — Event-Sourced Institutional Intelligence OS

### Core
- EventLedger with SHA-256 hash chain and integrity verification (SQLite backend)
- Ed25519 cryptographic identity for labs and agents
- TreatyEngine with state machine: PROPOSED → ACCEPTED/REJECTED → EXPIRED/CANCELLED
- Deterministic agents: Literature Agent, Skeptic Agent, Auditor Agent
- FastAPI surface: /health, /ready, /labs, /treaties, /audit, /agents/execute

### Integrations (merged from feature branches)
- **Ollama/Llama3** (feature/ollama-integration): zero-cost local inference
  with graceful fallback to deterministic mode when Ollama unavailable.
  12 tests covering success, connection error, and timeout fallback paths.
- **CUSTOS-Core governance** (feature/custos-governance): CustosClient calls
  CUSTOS /v1/evaluate with JWT tenant binding. GovernedExecutor wraps agent +
  CUSTOS + ledger. Flags results as 'ungoverned' when CUSTOS is down but
  does NOT block execution — logs to event ledger with ungoverned=True.
  9 tests.
- **OPA/Rego enforcement** (feature/opa-enforcement): PolicyEnforcer calls OPA
  for treaty proposals and agent decisions. OPAClient queries
  /v1/data/lorl/governance/allow. Fails OPEN (permissive) if OPA unavailable.
  12 tests including API endpoint 403 enforcement.

### Infrastructure
- Docker + docker-compose
- CI pipeline (GitHub Actions): ruff, bandit, pip-audit, pytest with coverage
- Rego policy at policies/lorl_governance.rego

### Testing
- 77 tests, 93% coverage
- 8 test files covering: agents, API, governance, identity, ledger,
  ollama integration, OPA enforcement, treaty engine

### License
- AGPL-3.0 (changed from Apache 2.0)
- Trademark notice for LORL-9.1, CUSTOS, CUSTOS-CORE
- CLA required for all contributors
