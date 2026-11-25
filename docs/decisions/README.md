# Architecture Decision Records

Short records of product and engineering choices that shape Aegis. Prefer reading these before changing metrics, scoring, AI boundaries, or deployment targets.

## Format

Each ADR uses these sections:

| Section | Purpose |
|---|---|
| **Context** | What problem or choice was on the table |
| **Decision** | What we chose |
| **Status** | `Accepted`, `Proposed`, or `Superseded` |
| **Consequences** | What follows from the choice (including code hooks where relevant) |
| **Alternatives rejected** | Options we considered and why they were dropped |

Keep ADRs short and plain. Link related ADRs. Cross-check `metrics/` and `backend/` when the decision touches implemented behaviour.

## Index

### Product principles

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-005](ADR-005-product-positioning.md) | Product positioning: Client Fragility & Stress Testing | Accepted | 2026-11-22 |
| [ADR-006](ADR-006-no-prediction.md) | Aegis never predicts | Accepted | 2026-11-24 |
| [ADR-007](ADR-007-ai-never-scores.md) | AI never produces scores | Accepted | 2026-11-22 |
| [ADR-008](ADR-008-no-blended-fragility-score.md) | No blended fragility score; four metric groups | Accepted | 2026-11-24 |
| [ADR-009](ADR-009-ruin-hard-red-flag.md) | Ruin is a hard red flag | Accepted | 2026-11-24 |
| [ADR-010](ADR-010-one-file-per-metric.md) | One file per metric | Accepted | 2026-11-23 |
| [ADR-011](ADR-011-stress-ladder.md) | Stress ladder at 10/20/50% | Accepted | 2026-11-24 |
| [ADR-012](ADR-012-target-gcp-platform.md) | Target platform is GCP | Proposed | 2026-11-22 |
| [ADR-013](ADR-013-hormuz-case-study-dropped.md) | Strait of Hormuz case study dropped | Accepted | 2026-11-22 – 2026-11-23 |
| [ADR-015](ADR-015-convexity-distance-to-ruin-not-tested.md) | Convexity from model output; distance to ruin; NOT_TESTED | Accepted | 2026-11-25 |
| [ADR-016](ADR-016-optionality-node-disjoint-maxflow.md) | Optionality counts node-disjoint corridors (Menger / max-flow) | Accepted | 2026-11-25 |
| [ADR-017](ADR-017-local-duckdb-run-records.md) | Local DuckDB for metrics run records; BigQuery later | Accepted | 2026-11-25 |
| [ADR-018](ADR-018-client-packs-and-confidential-data.md) | Per-client packs; confidential data stays out of git | Accepted | 2026-11-25 |

### Eval / CI

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-014](ADR-014-eval-gate-weakness-detection.md) | Eval gate measures weakness detection, not prediction | Accepted | 2026-11-24 |

### Earlier engineering ADRs

| ADR | Title | Status | Date |
|---|---|---|---|
| [ADR-001](ADR-001-local-persistence.md) | SQLite as local persistence backend | Accepted | 2026-11-17 |
| [ADR-002](ADR-002-model-provider-abstraction.md) | Model provider abstraction and output validation | Accepted | 2026-11-17 |
| [ADR-003](ADR-003-async-processing.md) | Genuine asynchronous event processing | Accepted | 2026-11-17 |
| [ADR-004](ADR-004-deployment.md) | Deployment architecture (Cloud Run, Pub/Sub, Firestore) | Accepted | 2026-11-18 |

ADR-001–004 use an earlier section layout (Context / Decision / Rationale / Consequences). New ADRs follow the format above. Where they overlap (especially AI boundaries and GCP), treat the product ADRs as the principle and the engineering ADRs as the current implementation path.
