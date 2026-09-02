# LORL-9.1 Licensing

## Open Source Core — AGPL-3.0

LORL-9.1 is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0).

This means:
- ✅ You can use, modify, and distribute the code
- ✅ You can deploy it internally
- ❌ If you deploy it as a **network service** (SaaS, API, cloud), you MUST open-source all modifications
- ❌ You cannot rebrand and sell it as a closed-source product

### Why AGPL-3.0?

AGPL-3.0 closes the "SaaS loophole" that Apache 2.0 and MIT leave open.
Without AGPL, a competitor could fork this repo, build a hosted service,
and never contribute back. With AGPL, anyone who deploys as a service
must share their changes with the community.

### Commercial License

For organizations that want to use LORL-9.1 without AGPL obligations
(no open-sourcing required), a commercial license is available.

Contact: FroLife Productions

---

## What's Open Source (AGPL-3.0)

- Core event ledger (EventLedger with SHA-256 hash chain)
- Ed25519 cryptographic identity module
- Treaty engine (propose, accept, reject, expire, cancel)
- Deterministic agents (Literature, Skeptic, Auditor)
- Ollama/Llama3 integration with graceful fallback
- CUSTOS-Core governance client
- OPA/Rego policy enforcement
- FastAPI surface (/health, /ready, /labs, /treaties, /audit, /agents/*)
- SQLite backend
- Docker + docker-compose

## Future Commercial / Enterprise Tier

- PostgreSQL event ledger backend
- Multi-lab federation
- Blockchain treaty settlement (Solana/Base)
- ZK-proof attestation layer
- Hosted managed service
- Enterprise support and SLA

---

## Trademark Notice

"LORL-9.1", "CUSTOS", and "CUSTOS-CORE" are brand names of
FroLife Productions. Use of these names in derivative works or
hosted services requires written permission.

---

## Contributor License Agreement

All contributors must sign the CLA before their PRs can be merged.
This ensures FroLife Productions retains the right to offer a
commercial license without being blocked by third-party copyright claims.

Use [cla-assistant.io](https://cla-assistant.io) or contact FroLife Productions directly.
