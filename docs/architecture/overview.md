# Aegis — Architecture Overview

## Purpose

Aegis is a Global Event Intelligence and Client Impact Assessment platform. It monitors external events, determines their relevance to clients and active projects, and produces evidence-backed impact assessments.

---

## Component map

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI (port 8000)                   │
│  POST /events  GET /events/:id  GET /dashboard/summary       │
└─────────────────────┬───────────────────────────────────────┘
                      │ 202 Accepted
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   Ingestion Service                          │
│  • Idempotency check    • Save event    • Publish to bus     │
└─────────────────────┬───────────────────────────────────────┘
                      │ asyncio.Queue (InMemoryMessageBus)
                      ▼                      or Pub/Sub
┌─────────────────────────────────────────────────────────────┐
│          Event Processing Worker (asyncio.Task)             │
│                                                             │
│  1. Normalise   EventNormaliser          (pure fn)          │
│  2. Classify    RuleBasedClassifier      (deterministic)     │
│  3. Assess      AssessmentService                           │
│       ├─ Client matching  (deterministic keyword/geo)       │
│       ├─ Retrieval        KnowledgeRepositoryPort           │
│       ├─ Model call       ModelProviderPort                 │
│       │   └─ Output validated against AssessmentOutput      │
│       └─ Risk score       RiskScorer    (deterministic)     │
│  4. Persist     EventStore + AssessmentStore                │
└─────────────────────────────────────────────────────────────┘
```

---

## Port/adapter matrix

| Port | Local adapter | GCP adapter (later) |
|---|---|---|
| `EventStorePort` | `SQLiteEventStore` | `FirestoreEventStore` |
| `AssessmentStorePort` | `SQLiteAssessmentStore` | `FirestoreAssessmentStore` |
| `MessageBusPort` | `InMemoryMessageBus` | `PubSubBus` |
| `ModelProviderPort` | `DeterministicModelProvider` | `GeminiModelProvider` / `VertexModelProvider` |
| `KnowledgeRepositoryPort` | `LexicalKnowledgeRepository` | `BGEM3KnowledgeRepository` |

---

## Design rules

1. **Services depend on ports, not adapters.** The Container (`api/dependencies.py`) is the only place concrete adapters are instantiated.
2. **The model never makes business decisions.** Risk score, client matching, and event classification are deterministic. The model generates text that is validated against a schema and cited as evidence.
3. **Every assessment has an evidence chain.** No assessment is persisted without at least attempting retrieval. Evidence references carry source IDs that trace back to indexed documents.
4. **Processing is idempotent.** The `idempotency_key` field on events prevents duplicate processing. SQLite enforces uniqueness at the DB level.
5. **Correlation IDs propagate.** Every log entry in the processing chain carries the originating event's `correlation_id`.

---

## Checkpoints

| # | Scope |
|---|---|
| 1 | Repository structure, data contracts, port interfaces, local adapters, unit/integration tests |
| 2 | Event ingestion refinement, Pub/Sub emulator adapter, expanded test coverage |
| 3 | RAG retrieval (BGE-M3 adapter), Gemini provider, assessment quality evaluation |
| 4 | Frontend dashboard, GCP deployment (Cloud Run, Pub/Sub, Firestore), Terraform |
