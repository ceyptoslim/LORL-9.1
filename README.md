# LORL-9.1

[![CI](https://github.com/ceyptoslim/LORL-9.1/actions/workflows/ci.yml/badge.svg)](https://github.com/ceyptoslim/LORL-9.1/actions)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-AGPL-3.0-red)](LICENSE)

**LORL-9.1: Event-sourced institutional intelligence OS with Ed25519 cryptographic identity, PostgreSQL ledger, treaty engine, and CUSTOS-Core governance integration.**

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              LORL-9.1 API (FastAPI)           │
│                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Identity  │  │  Ledger  │  │  Treaty  │    │
│  │ (Ed25519) │  │ (Events) │  │  Engine  │    │
│  └──────────┘  └──────────┘  └──────────┘    │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │       Multi-Agent Orchestration          │  │
│  │  ┌──────────┐ ┌────────┐ ┌──────────┐   │  │
│  │  │Literature│ │Skeptic │ │ Auditor  │   │  │
│  │  └──────────┘ └────────┘ └──────────┘   │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  OPA Governance (Rego policies)           │  │
│  └─────────────────────────────────────────┘  │
└───────────────────┬───────────────────────────┘
                    │
                    ▼
         ┌───────────────────┐
         │   CUSTOS-Core      │
         │  (Policy + Audit)  │
         └───────────────────┘
```

## Quickstart

```bash
git clone https://github.com/ceyptoslim/LORL-9.1.git
cd LORL-9.1
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --cov=lorl --cov-fail-under=80
```

### Docker

```bash
docker compose up
# API: http://localhost:8000
# PostgreSQL: localhost:5432
# OPA: localhost:8181
```

## Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/ready` | Readiness probe |
| POST | `/api/v1/labs` | Register a lab (Ed25519 identity) |
| GET | `/api/v1/labs` | List labs |
| POST | `/api/v1/treaties` | Propose a treaty |
| POST | `/api/v1/treaties/{id}/accept` | Accept a treaty |
| POST | `/api/v1/treaties/{id}/reject` | Reject a treaty |
| GET | `/api/v1/treaties` | List treaties |
| GET | `/api/v1/audit` | Full event ledger with integrity check |
| POST | `/api/v1/agents/execute` | Execute an agent task |

## CUSTOS-Core Integration

LORL agents submit decisions to CUSTOS-Core for policy enforcement before
recording them in the ledger:

```python
import httpx

async def governed_execute(agent, task, custos_url="http://custos:8000"):
    rec = await agent.execute(task)

    # Submit to CUSTOS for policy check
    response = httpx.post(
        f"{custos_url}/v1/evaluate",
        json={"client_id": "lorl", "content": str(rec.data)}
    )

    if response.json()["allowed"]:
        ledger.append(rec)  # Record in LORL ledger
        return rec
    else:
        raise RuntimeError(f"Policy denied: {response.json()['reason']}")
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + Uvicorn |
| Identity | Ed25519 (cryptography library) |
| Ledger | PostgreSQL / SQLite event sourcing |
| Treaty Engine | Python state machine |
| Agents | Deterministic (Ollama/Llama3 ready) |
| Governance | OPA / Rego |
| CI/CD | GitHub Actions (Python 3.10/3.11/3.12) |
| Container | Docker + Docker Compose |
| License | AGPL-3.0 |

## License

AGPL-3.0 — see [LICENSE](LICENSE). Commercial licensing available — see [NOTICE.md](NOTICE.md).
