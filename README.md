# Aegis Global Intelligence

**Global Event Intelligence and Client Impact Assessment Platform**

Aegis monitors external events, determines their relevance to clients and active projects, and produces evidence-backed impact assessments through a structured processing pipeline.

---

## Checkpoint 1 — What's here

- Full directory structure and module skeleton
- Pydantic data contracts (`Event`, `Client`, `Project`, `EventClassification`, `ClientExposure`, `ImpactAssessment`, `RiskScore`, `EvidenceReference`)
- Port interfaces for all major subsystems (event store, message bus, model provider, knowledge repository, assessment store)
- Working vertical slice: submit event → publish to in-memory queue → worker processes asynchronously → assessment + risk score persisted
- Deterministic model provider (no API key required)
- BM25 lexical knowledge repository
- SQLite persistence adapters
- Synthetic clients, projects, regional profiles, and industry context
- Unit, integration, and contract tests
- Architecture decision records

---

## Quick start

### Prerequisites

- Python 3.12+
- pip

### Setup

```bash
# Clone / open the project
cd aegis-global-intelligence

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the backend
PYTHONPATH=. python -m backend.main
```

The API is available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Submit a test event

```bash
curl -X POST http://localhost:8000/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "manual",
    "title": "Major oil sanctions imposed on Gulf producer",
    "raw_content": "The international community has imposed sweeping oil sanctions on a major Gulf producer following military escalation. Energy infrastructure is at risk. OPEC meeting called.",
    "event_date": "2026-11-15T00:00:00",
    "affected_regions": ["middle_east"],
    "tags": ["geopolitical", "energy", "sanctions"]
  }'
```

The API returns 202 immediately. The worker processes it asynchronously.

### Check status

```bash
curl http://localhost:8000/api/v1/events/{event_id}
```

Status transitions: `pending → normalised → classified → processing → assessed`

### Dashboard summary

```bash
curl http://localhost:8000/api/v1/dashboard/summary
```

### Health check

```bash
curl http://localhost:8000/health
```

---

## Run tests

```bash
# All tests
PYTHONPATH=. pytest tests/

# Unit tests only
PYTHONPATH=. pytest tests/unit/

# Integration tests
PYTHONPATH=. pytest tests/integration/

# Contract tests
PYTHONPATH=. pytest tests/contract/

# Skip slow evaluation tests
PYTHONPATH=. pytest tests/ -m "not evaluation"
```

---

## Docker

```bash
# Build and run with docker-compose
docker-compose up --build

# With Pub/Sub emulator (opt-in)
docker-compose --profile pubsub up
```

---

## Configuration

All configuration is via environment variables or `.env`. See `.env.example` for the full list.

Key variables:

| Variable | Default | Description |
|---|---|---|
| `MODEL_PROVIDER` | `deterministic` | `deterministic` / `gemini` |
| `GEMINI_API_KEY` | _(unset)_ | Required only for `gemini` provider |
| `MESSAGE_BUS_BACKEND` | `in_memory` | `in_memory` / `pubsub_emulator` |
| `RETRIEVAL_BACKEND` | `lexical` | `lexical` / `bge_m3` |
| `SQLITE_DB_PATH` | `./data/aegis.db` | Local database path |

---

## Architecture

See [`docs/architecture/overview.md`](docs/architecture/overview.md) for the full component map.

Key design principles:
- Services depend on **port interfaces**, not concrete adapters
- The model **never makes business decisions** — risk scores are deterministic
- Event processing is **genuinely asynchronous** — the API and worker share only the queue
- Every assessment retains its **full provenance chain** (source event, evidence, model version)

---

## Repository structure

```
backend/
  api/           FastAPI application, routers, DI container
  ingestion/     Event ingestion service
  event_processing/  Normaliser, classifier, async worker
  assessment/    Impact assessment service
  retrieval/     Evidence retrieval service
  decision_engine/   Deterministic risk scorer
  model_gateway/ DeterministicModelProvider, GeminiModelProvider
  persistence/   SQLite and InMemoryMessageBus adapters
  shared/        Models, ports, config, logging

data/synthetic/  Clients, projects, regional profiles, industry context
docs/
  architecture/  System overview
  decisions/     ADRs 001-003
infrastructure/
  docker/        Dockerfile
  terraform/     GCP infrastructure (checkpoint 4)
tests/
  unit/          Model validation, scorer, classifier, normaliser
  integration/   End-to-end pipeline test
  contract/      Model provider contract tests
  evaluation/    Assessment quality baselines
```

---

## Checkpoints

| # | Scope | Status |
|---|---|---|
| 1 | Repository structure, data contracts, architecture | ✅ Complete |
| 2 | Event ingestion refinement, Pub/Sub emulator | Pending |
| 3 | RAG (BGE-M3), Gemini provider, evaluation | Pending |
| 4 | Dashboard, GCP deployment, Terraform | Pending |
