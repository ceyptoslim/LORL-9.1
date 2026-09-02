# LORL-9.1 ↔ CUSTOS-Core Integration Bridge

## Overview

LORL-9.1 uses CUSTOS-Core as its governance enforcement layer. All agent
decisions, treaty actions, and governance-critical operations pass through
CUSTOS before being committed to the LORL event ledger.

## Integration Points

### 1. Agent Decision Governance

```python
import httpx
from lorl.agents import LiteratureAgent
from lorl.core.ledger import EventLedger, Event, EventType

async def governed_agent_execution(agent, task, ledger, custos_url):
    # Step 1: Agent produces a recommendation
    response = await agent.execute(task)

    # Step 2: Submit to CUSTOS for policy evaluation
    custos_response = httpx.post(
        f"{custos_url}/v1/evaluate",
        json={
            "client_id": "lorl",
            "content": str(response.data),
            "tenant_id": "default"
        }
    )
    result = custos_response.json()

    # Step 3: Only record if CUSTOS allows
    if result["allowed"]:
        ledger.append(Event(
            event_type=EventType.AGENT_DECISION,
            actor_id=response.agent_id,
            aggregate_id=response.task_id,
            data={
                **response.to_dict(),
                "custos_approved": True,
                "custos_audit_hash": result.get("audit_record_hash"),
            }
        ))
        return response
    else:
        # Denied — log the denial but don't record the decision
        ledger.append(Event(
            event_type=EventType.GOVERNANCE_CHECK,
            actor_id=response.agent_id,
            aggregate_id=response.task_id,
            data={
                "custos_approved": False,
                "reason": result.get("reason"),
                "triggered_rule": result.get("triggered_rule"),
            }
        ))
        raise RuntimeError(f"CUSTOS policy denied: {result.get('reason')}")
```

### 2. Execution Enforcement (v1.2.0+)

For stronger enforcement, use CUSTOS's `/v1/execute` endpoint instead of
`/v1/evaluate`. This physically blocks the downstream action:

```python
response = httpx.post(
    f"{custos_url}/v1/execute",
    json={
        "client_id": "lorl",
        "content": str(agent_response.data),
        "target_url": "https://downstream-api.example.com/action",
        "target_method": "POST"
    }
)
# If policy denies, CUSTOS returns 403 and the target is never contacted
```

### 3. Audit Chain Verification

LORL's event ledger and CUSTOS's audit chain can be cross-verified:

```python
# Verify CUSTOS audit chain integrity
custos_audit = httpx.get(f"{custos_url}/v1/audit/verify")

# Verify LORL event ledger integrity
lorl_verified = ledger.verify_integrity()

# Both must be True for full governance compliance
assert custos_audit.json()["verified"] is True
assert lorl_verified is True
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LORL_DB_URL` | `sqlite:///lorl.db` | LORL event ledger database |
| `CUSTOS_URL` | `http://localhost:8000` | CUSTOS-Core API URL |
| `CUSTOS_AUTH_DISABLED` | `0` | Disable JWT auth (dev only) |
| `OPA_URL` | `http://localhost:8181` | OPA policy engine URL |

## Docker Compose Integration

Both services can run together via Docker Compose:

```yaml
services:
  lorl:
    build: .
    environment:
      - LORL_DB_URL=postgresql://lorl:lorl@db:5432/lorl_db
      - CUSTOS_URL=http://custos:8000
    depends_on: [custos, db]

  custos:
    image: custos-core:latest
    ports: ["8000:8000"]
    environment:
      - AUTH_DISABLED=1

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: lorl
      POSTGRES_PASSWORD: lorl
      POSTGRES_DB: lorl_db
```
