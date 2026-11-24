# ADR-005: Product positioning — Client Fragility & Stress Testing

**Date:** 2026-11-22

## Context

Early naming framed Aegis as a global event-intelligence product: ingest news, score client impact, surface alerts. That framing pulls the system toward forecasting which events matter. The real product question is structural: given a client's dependency graph, where does fragility live?

## Decision

Position the product as **Aegis: Client Fragility & Stress Testing**.

Aegis models a client's structural dependency graph (suppliers, customers, regions, vendors, systems). Live events act only as **stressors** applied to that graph. They do not define the product's identity or validation criteria.

## Status

Accepted

## Consequences

- Copy, docs, and UI should describe structural fragility and stress testing, not event prediction or "intelligence feeds".
- The event pipeline in `backend/` remains useful: ingest → normalise → classify → assess. Assessments and the deterministic `RiskScorer` are event-impact tooling layered on top of (and distinct from) structural metrics in `metrics/`.
- Older strings such as "Global Event Intelligence" in `backend/shared/config.py` and `docs/architecture/overview.md` are legacy naming; new work should use the Client Fragility & Stress Testing framing.

## Alternatives rejected

- **Global Event Intelligence** — centres the product on events and impact news rather than on the client's structural graph. Rejected because it invites prediction and dilutes the fragility thesis.
