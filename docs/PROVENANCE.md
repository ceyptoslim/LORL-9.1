# Treaty Engine — Design Provenance

> This document records the design lineage of the Treaty Engine, separating
> design provenance from shipped implementation, per the project's evidence
> discipline: repository code is the only proof of implementation; design
> documents prove intent only.

## Shipped implementation (repository evidence)

- `lorl/core/treaty_engine.py` — formal agreements between labs governed by a
  deterministic state machine: `PROPOSED → ACCEPTED | REJECTED → EXPIRED |
  CANCELLED`. Invalid transitions raise `TreatyTransitionError` and are
  rejected — a treaty cannot skip states or act outside its lifecycle. Terms
  are structured dicts covering resource sharing, revenue splits, data access,
  and governance rules.
- `tests/test_treaty_engine.py` — 7 dedicated tests, part of the 87-test
  suite shipped in v0.2.0.
- Released in LORL-9.1 v0.2.0 (AGPL-3.0), operating under the fail-closed
  governance model: no authoritative policy decision, no governed execution.

## Design provenance (April 24, 2026 sprint series)

The treaty concept originates in the AEGIS-ABO sprint-design sessions of
April 24, 2026 — a pre-repository design phase documented in session records
(design documents, not code):

- **Sprint 2** — treaties appear in the event model; state-transition
  validation is identified as a hard requirement (a treaty cannot activate
  before it is created), and treaty lifecycle events are separated from
  agent telemetry.
- **Sprint 3 — the origin.** Agent-to-Agent Treaties introduced as
  "structured contracts, not messages": a Treaty Graph (a directed graph of
  obligations with explicit dependencies, cost, and priority), governed by
  the principle of *"bounded negotiation inside treaty constraints with
  deterministic settlement rules — not agent autonomy."*
- **Sprint 4** — the lifecycle is formalized (proposed → active → breached)
  and every optimization proposal is routed through governance rather than
  self-applied.
- **Sprint 5** — capital treaties: no fund movement without a treaty.
- **Sprint 6** — external treaties: every API call becomes a micro-contract;
  "no API response exists outside a treaty context."
- **Sprint 7** — marketplace binding: no agent runs without registry
  certification + treaty binding; API access is treaty-gated.
- **Sprint 8.3** — Cross-Enterprise Treaty Protocol (CETP): scoped, signed
  treaties between sovereign deployments, with federated settlement and
  evidence-backed dispute handling.

## What shipped vs. what remains design

**Shipped:** the core Sprint 3 concept — deterministic, state-machine-governed
agreements between parties, with invalid transitions rejected. This is the
philosophical center of the sprint series: bounded, governed coordination
instead of open agent autonomy.

**Not shipped (design only, future architecture):** the economic
elaborations — treaty graphs with optimization solving, capital-deployment
treaties, API micro-treaties, marketplace certification binding, and
cross-enterprise federation (CETP). None of these may be represented as
deployed functionality.

The design principle carried from the April 2026 sprints into the shipped
architecture: **agreements are structured, deterministic, and enforced —
agents negotiate only inside treaty constraints.**
