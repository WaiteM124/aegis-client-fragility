# ADR-004: Deployment Architecture

**Status:** Accepted  
**Date:** 2026-11-18  
**Authors:** Aegis Platform Team

---

## Context

Aegis Global Intelligence is an event-driven platform that processes global news
events, runs client impact assessments, and stores structured intelligence for
dashboard consumption.  The system has two distinct runtime concerns:

1. **API server** — synchronous HTTP endpoints for event ingestion, event queries,
   and dashboard reads.  Latency-sensitive: responds to real-time user actions.

2. **Event processing worker** — asynchronous consumer that runs the full pipeline
   (normalise → classify → retrieve → assess → score) for each ingested event.
   Throughput-bound, not latency-bound; acceptable to process events seconds or
   minutes after submission.

We needed to decide:
- **Where to run** (compute platform)
- **How to split** API vs. worker
- **How events flow** between them
- **How to persist** state at scale
- **How to manage secrets**

---

## Decision 1: Google Cloud Run

**Choice:** Deploy both the API and the worker on **Google Cloud Run** (managed
serverless containers).

**Rationale:**

| Concern | Cloud Run |
|---|---|
| Zero infrastructure management | ✓ — Google manages the runtime |
| Scale-to-zero for worker | ✓ — idle worker costs nothing |
| Automatic HTTPS + load balancing | ✓ — built-in |
| VPC connectivity to Pub/Sub, Firestore | ✓ — native service account auth |
| Deployment via container image | ✓ — aligns with existing Docker workflow |
| Multi-region failover | Supported via traffic splitting |

**Alternatives considered:**

- **GKE / Kubernetes** — more control but significant operational overhead for a
  small team.  Rejected until scale justifies it.
- **Cloud Functions** — per-invocation billing attractive but cold starts and 540s
  timeout limit would constrain assessment pipeline latency for large events.
- **App Engine** — less flexible than Cloud Run for custom runtimes.

---

## Decision 2: Single-container API / Worker split

**Choice:** Two separate Cloud Run *services* with separate container images
(`aegis-backend` and `aegis-worker`).

**Rationale:**

- The API needs **external ingress** and must remain responsive under load.
  Sharing a process with the CPU-intensive assessment pipeline risks head-of-line
  blocking.
- The worker needs **internal-only ingress** (Pub/Sub push) and can scale
  independently of the API.
- Separate images mean separate deployment lifecycles: a model-provider update
  requires only a worker re-deploy without touching the API.
- **Internal ingress** on the worker service reduces the attack surface: it cannot
  be directly reached from the public internet.

**Container images:**

| Image | Entry-point | Ingress |
|---|---|---|
| `aegis-backend` | `uvicorn backend.main:app` | External |
| `aegis-worker` | `python -m backend.worker_main` | Internal |

---

## Decision 3: Pub/Sub for async handoff

**Choice:** Events are published to a **Cloud Pub/Sub topic** (`aegis-events`) by
the API and consumed by the worker via a push or pull subscription.

**Rationale:**

- Decouples API from worker: the API returns `202 Accepted` immediately without
  waiting for the assessment pipeline to complete.
- Pub/Sub provides **at-least-once delivery** with built-in retry and dead-letter
  queue support — matching the platform's existing retry semantics.
- The emulator (`PubSubEmulatorMessageBus`) enables local development without GCP
  credentials.  The same code runs against the real service in production.
- Dead-letter events land in `aegis-events-dlq` for offline triage.

---

## Decision 4: Firestore for serverless persistence

**Choice:** Use **Cloud Firestore** (native mode) as the production persistence
backend (`PERSISTENCE_BACKEND=firestore_emulator` in development,
`firestore` in production).

**Rationale:**

- Firestore is fully managed and **serverless** — no instance sizing or connection
  pooling needed; aligns with Cloud Run's scale-to-zero model.
- Strong consistency for document reads ensures the dashboard always reflects the
  latest assessment state.
- Document-oriented model maps naturally to the domain: one document per event,
  one per assessment, one per risk score.
- The Python SDK is synchronous; `asyncio.to_thread` wraps every call to avoid
  blocking the event loop — a pattern already established by the SQLite adapter.
- **Local development** uses the Firestore emulator
  (`gcr.io/google.com/cloudsdktool/cloud-sdk`) with no live GCP credentials.
- SQLite remains the default for unit/integration tests for speed.

---

## Decision 5: Secret Manager for credentials

**Choice:** All sensitive configuration (API keys, Pub/Sub project IDs) is stored
in **Google Cloud Secret Manager** under a single secret named `aegis-config`.
Values are injected as environment variables via `secretKeyRef` in the Cloud Run
service YAML.

**Rationale:**

- Secrets never appear in source code, container images, or deployment YAMLs.
- Rotation is managed centrally without redeployment.
- IAM binding (`roles/secretmanager.secretAccessor` to the `aegis-sa` service
  account) limits access to Aegis services only.
- Cloud Run's native Secret Manager integration avoids the need for a sidecar or
  init container.

---

## Consequences

- **Positive:** Infrastructure is fully managed; Aegis engineers own only
  application code and container images.
- **Positive:** Worker and API scale independently; a surge in Pub/Sub messages
  does not degrade API response times.
- **Positive:** No credentials in source: secrets live exclusively in Secret
  Manager; local `.env` holds non-sensitive config defaults.
- **Negative:** Firestore's synchronous Python SDK requires `asyncio.to_thread`
  wrapping; a native async Firestore client (gRPC) would be preferred but is not
  yet stable for Python at time of writing.
- **Negative:** Cloud Run cold-starts can add 1–3 s of latency for the worker;
  acceptable for the event-processing use case but would not suit sub-second SLAs.
- **Watch:** If assessment volumes require >5 concurrent workers, consider
  upgrading to GKE with a dedicated node pool for assessment workloads.
