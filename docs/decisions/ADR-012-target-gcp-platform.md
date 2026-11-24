# ADR-012: Target platform is GCP

**Date:** 2026-11-22

## Context

Aegis needs a production target that fits an event-driven API + worker, structural metrics, retrieval, and a reasoning model behind a port — without locking domain code to one vendor SDK. ADR-004 already chose Cloud Run, Pub/Sub, and Firestore for the current event pipeline. This ADR records the broader product-platform target as the fragility engine matures.

## Decision

**Target platform: GCP**, with this intended shape:

| Concern | Target |
|---|---|
| Compute | Cloud Run |
| Event bus | Pub/Sub |
| Data / search | Postgres with vector search **plus** BM25 (host still open) |
| Infra as code | Terraform |
| Delivery | CI/CD with **eval gates** |
| Observability | Langfuse tracing and cost dashboards |
| Reasoning model | Behind `ModelProviderPort`; initially Gemini via Vertex AI with a **pinned model ID**; reasoning level chosen from evals; cheaper tasks routed to a cheaper model |

## Status

Proposed

## Consequences

- Domain code keeps depending on ports (`backend/shared/ports/`); wire GCP adapters only in DI / worker bootstrap ([ADR-002](ADR-002-model-provider-abstraction.md), [ADR-004](ADR-004-deployment.md)).
- Today: Cloud Run YAML and Pub/Sub / Firestore adapters exist under `infrastructure/` and `backend/persistence/`; local default remains SQLite + in-memory bus + deterministic provider. Terraform and Langfuse are not in the tree yet.
- Postgres + hybrid retrieval supersedes Firestore as the **proposed** system of record for the fragility platform; until this ADR is Accepted, ADR-004's Firestore path remains the implemented Cloud deployment.
- Pin model IDs in config (e.g. `GEMINI_MODEL`); do not silently bump models in feature PRs. Route cheap tasks to a cheaper model once evals justify the split.

## Alternatives rejected

- **AWS / Azure as primary target** — team and existing Cloud Run path are on GCP.
- **Unpinned / automatically latest foundation models** — breaks eval gates and cost control.
- **Model SDKs called from domain services** — violates ports-over-adapters.
