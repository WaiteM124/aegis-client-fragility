# ADR-001: SQLite as Local Persistence Backend

**Status:** Accepted  
**Date:** 2026-11-17  
**Checkpoint:** 1

---

## Context

Aegis requires a persistence layer for events, classifications, assessments, and risk scores. For local development and the initial PoC, the choice is between:

1. SQLite with aiosqlite
2. Firestore emulator via Docker

## Decision

Use SQLite as the default persistence backend for local development.

Both `EventStorePort` and `AssessmentStorePort` are abstract interfaces. The SQLite implementation (`SQLiteEventStore`, `SQLiteAssessmentStore`) fulfils those interfaces via concrete adapters. All business logic (services, workers) depends only on the port interfaces.

## Rationale

| Factor | SQLite | Firestore Emulator |
|---|---|---|
| External dependencies | None | Docker required |
| Startup time | < 1s | 5–10s |
| Windows compatibility | First-class | Container networking friction |
| Test isolation | In-process temp file | Emulator shared state |
| Port parity | Interface identical | Interface identical |

SQLite gives zero-dependency local development and fast test cycles. The Firestore adapter can be introduced at checkpoint 4 without touching any service code — only the Container class in `api/dependencies.py` changes.

## Consequences

- Local development requires no Docker.
- Tests use temporary SQLite files (deleted after each test).
- The `SQLiteEventStore` schema supports idempotency key deduplication via a unique index.
- Firestore-specific features (real-time listeners, global transactions) are deferred; the port interface will be extended if needed.
- Concurrency is bounded by aiosqlite's single write connection per store instance; sufficient for a local PoC.
