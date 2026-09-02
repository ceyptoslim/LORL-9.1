# LORL-9.1 — Changelog

All notable changes to this project are documented here. This changelog
follows a transparent "what we built, what we fixed, what we know is still
open" format — no claims beyond what the code and tests demonstrate.

---

## [0.2.0] — Fail-Closed Governance & Release Readiness

### Security: OPA and CUSTOS Fail-Closed Alignment
- **OPA client now fails CLOSED** when OPA server is unavailable. Previously
  failed open (returned ALLOW with warning). Now returns DENY. This aligns
  LORL-9.1 with CUSTOS-CORE enforcement semantics.
- **GovernedExecutor no longer has an "ungoverned" path.** When CUSTOS is
  unavailable, execution is DENIED and agent output is withheld. Previously,
  the executor flagged results as "ungoverned" and returned them to the caller.
- **Malformed OPA responses now fail closed.** Non-boolean, missing, or
  structurally unexpected responses are treated as DENY.
- **Security invariant: No authoritative policy decision → no governed execution.**

### Fail-Mode Decision Matrix
| Component      | OPA unavailable | CUSTOS unavailable | Malformed response |
|----------------|-----------------|--------------------|--------------------|
| CUSTOS-CORE    | DENY (fail-closed) | N/A (OPA is its policy engine) | DENY |
| LORL-9.1 OPA   | DENY (fail-closed) | N/A                | DENY |
| LORL-9.1 CUSTOS| N/A             | DENY (fail-closed)  | DENY |
| Agent execution| DENY if OPA denies | DENY if CUSTOS denies/unavailable | DENY |

### Testing
- 18 OPA enforcement tests covering all 6 scenarios:
  1. OPA available + ALLOW → execution proceeds
  2. OPA available + DENY → execution stops
  3. OPA unavailable → execution stops (fail-closed)
  4. OPA malformed response → execution stops (fail-closed)
  5. CUSTOS unavailable → execution stops (fail-closed)
  6. No warning-only authorization path remains
- Governance tests updated to verify fail-closed behavior
- API tests updated with OPA mock fixtures
- 87 tests total, 93% coverage

### Documentation
- Fixed README license badge: was "Apache 2.0", now correctly "AGPL-3.0"
- Added NOTICE.md with dual-license model, trademark notice, and CLA requirement
- Added this CHANGELOG.md

### Infrastructure
- Fixed pyproject.toml build backend: setuptools.backends._legacy → setuptools.build_meta
- Added [tool.setuptools.packages.find] with include=["lorl*"] for proper package discovery
- Fixed Dockerfile: non-root user now has write permissions, default LORL_DB_URL set
- CI pipeline: added pip install -e . step, all 4 jobs green (3 Python versions + Docker)

### Version
- Bumped from 0.1.0 → 0.2.0 (pyproject.toml + lorl/__init__.py)

### Known Limitations
- No PostgreSQL backend (SQLite only).
- No blockchain settlement (architecture target).
- Fail-closed is the recommended default for the CUSTOS security architecture.
  Permissive (fail-open) mode may be appropriate for development or
  non-security-critical deployments.

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
