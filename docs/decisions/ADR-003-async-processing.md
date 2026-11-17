# ADR-003: Genuine Asynchronous Event Processing

**Status:** Accepted  
**Date:** 2026-11-17  
**Checkpoint:** 1

---

## Context

A core requirement is that the system demonstrates **genuine asynchronous event processing** — not a synchronous chain where "submitting" an event immediately triggers an AI call and returns a result.

## Decision

The API and the event processing worker share only:
1. The message bus queue (a topic in `InMemoryMessageBus` / Pub/Sub).
2. The persistence stores (SQLite / Firestore).

They do **not** share any in-process call chain.

**Flow:**

```
HTTP POST /api/v1/events
  → IngestionService.ingest_event()
      → event_store.save_event()           ← DB write
      → message_bus.publish(events_topic)  ← Queue put
  ← 202 Accepted { event_id, correlation_id }

(concurrently, independently)

EventProcessingWorker (asyncio.Task)
  → bus.subscribe(events_subscription)     ← blocking pull loop
      → EventNormaliser.normalise()
      → RuleBasedClassifier.classify()
      → AssessmentService.assess_event()
          → RetrievalService.retrieve()
          → ModelProviderPort.generate()
          → RiskScorer.score()
          → assessment_store.save_*()
      → event_store.update_event_status(ASSESSED)
```

The worker runs as an `asyncio.Task` started at application startup (`worker.start()` in the FastAPI lifespan). The bus consumer loop runs until the task is cancelled at shutdown.

## Local adapter

`InMemoryMessageBus` uses `asyncio.Queue` per topic. `publish()` is a non-blocking `queue.put()`. `subscribe()` is a blocking coroutine that loops until cancelled, dispatching handlers under a semaphore for concurrency control.

## GCP adapter (checkpoint 2)

`PubSubEmulatorBus` / `PubSubBus` will implement the same `MessageBusPort` interface. The worker calls `bus.subscribe()` identically; only the adapter changes.

## Rationale

- The API caller never waits for assessment completion.
- The worker can be scaled independently (multiple workers on the same subscription).
- Failure isolation: an assessment failure does not affect event ingestion.
- The DLQ design (failed events republished to `aegis-events-dlq`) is consistent across local and GCP.

## Consequences

- Event status transitions from `pending` → `normalised` → `classified` → `processing` → `assessed` (or `failed`).
- Callers poll `GET /api/v1/events/{id}` to check processing status.
- The dashboard reflects real-time status from the store, not from the API request path.
- Tests must use polling (`_wait_for_status`) rather than synchronous assertions.
