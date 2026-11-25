# AGENTS.md — Aegis contributor & agent guide

Single source of truth for humans and AI agents (including Cursor) working in this repository.

**Product:** Aegis — Client Fragility & Stress Testing. Finds structural fragility in a client's dependencies (concentration, contagion, convexity, optionality). It does **not** predict events.

**Owner:** Miles Waite (AI systems architect). Portfolio piece heading for production (Terraform, CI/CD with eval gates, observability, cost control, security).

---

## Repository map

| Path | Role |
|---|---|
| `backend/` | FastAPI API, ingestion, async worker, assessment, retrieval, decision engine, model gateway, persistence adapters |
| `backend/api` | FastAPI app, routers (`/health`, `/api/v1/events`, `/api/v1/dashboard`), DI container |
| `backend/ingestion` | Idempotency, persist event, publish to message bus |
| `backend/event_processing` | Normaliser, rule-based classifier, async worker |
| `backend/assessment` | Client matching, retrieval, model call, persist assessment |
| `backend/retrieval` | Evidence retrieval against the knowledge repository |
| `backend/decision_engine` | Deterministic risk scorer (event impact scoring — distinct from fragility metrics) |
| `metrics/` | Deterministic structural-fragility metrics (`compute(graph, scenario) -> MetricResult`); one file per metric; small test graphs under `metrics/examples/`; package tests under `metrics/tests/`; run records (`schemas/run_record.v1.json` / `v2`) and local DuckDB store (`metrics.store`); client-pack helpers (`metrics.client_pack`) |
| `clients/` | Per-client packs (`client.yaml`, `model/`, `sources/`, `maps/`, `runs/`); JSON schemas (`client.v1`, `sources_manifest.v1`, `dependency_graph.v1` with optional financial sections); example ChillCo and Carillion public backtest (source pack + method freeze; no model yet) ([ADR-018](docs/decisions/ADR-018-client-packs-and-confidential-data.md), [ADR-019](docs/decisions/ADR-019-financial-side-model.md), [docs/backtests/carillion-method-freeze.md](docs/backtests/carillion-method-freeze.md)) |
| `backend/model_gateway` | `DeterministicModelProvider` (default) and `GeminiModelProvider` |
| `backend/persistence` | SQLite / Firestore stores; in-memory / Pub/Sub buses; lexical knowledge repository |
| `backend/shared` | Pydantic models, port interfaces, config, structured logging |
| `frontend/` | React + TypeScript + Vite + Tailwind + TanStack Query dashboard |
| `data/synthetic/` | Synthetic clients, projects, regional profiles, industry context |
| `data/evaluation/` | Labelled, adversarial, and held-out evaluation event sets |
| `evals/` | Deterministic metrics eval suite: labelled graphs (`evals/cases/`), runner (`evals/run_evals.py`), `baseline.json` / `results.json` |
| `docs/` | Architecture overview and ADRs ([docs/decisions/](docs/decisions/)) |
| `infrastructure/` | Dockerfiles and Cloud Run service YAML |
| `tests/` | `unit/`, `integration/`, `contract/`, `evaluation/` |
| `.github/workflows/ci.yml` | PR/push CI: ruff + pytest (backend); oxlint + build (frontend); `eval-gate` (metrics evals + offline `-m evaluation`) |

Stack: **Python 3.12+**, FastAPI, Pydantic v2, pytest, ruff; **Node 18+** (CI uses 22) for the dashboard. Local default path needs no cloud credentials (`MODEL_PROVIDER=deterministic`, SQLite, in-memory bus, lexical retrieval).

---

## Product principles (non-negotiable)

1. **No prediction.** Aegis finds structural weaknesses regardless of which shock arrives. Do not add forecasting, event probabilities, fitted tails, or historical-correlation estimates into metrics. Do not use predictive framing in docs, API copy, or UI text (avoid “likely”, “will happen”, “probability of X”).
2. **No blended fragility score.** Never invent a weighted or blended single fragility number across metric groups. Each group reports the **worst** member metric’s red / amber / green status. **Ruin is a hard red flag** — it cannot be averaged away.
3. **AI / LLMs never produce scores.** All numeric scores and status colours come from deterministic, tested Python. LLMs may help with evidence interpretation, profile elicitation, and narrative consequence analysis; model output must validate against a Pydantic schema or be rejected. Business decisions and maths stay independently testable (see [ADR-007](docs/decisions/ADR-007-ai-never-scores.md), [ADR-002](docs/decisions/ADR-002-model-provider-abstraction.md)).
4. **One file per metric.** Each fragility metric lives in its own module with:
   - a `compute(graph, scenario) -> MetricResult` function;
   - a module docstring that states the **formula** and its **plain-language meaning**.
5. **Ports over adapters.** Services depend on interfaces in `backend/shared/ports/`. Wire concrete adapters only in `backend/api/dependencies.py` (and worker bootstrap). Do not leak Firestore, Pub/Sub, or Gemini types into domain logic.

---

## Engineering standards

- **Typed code.** Type hints on public functions and methods. Pydantic models at API, persistence, and model-provider boundaries.
- **Tests as the spec.** Prefer known-answer / golden cases for scoring and metrics. Cover happy path, edge cases, and ruin/red-flag behaviour where relevant.
- **Green before PR.** `ruff check` and the relevant test suite must pass locally. CI must stay green.
- **Small, focused PRs.** One concern per PR; clear title and description; state assumptions and out-of-scope items.
- **No secrets in git.** Use `.env` (gitignored) or a secret manager. Never commit API keys, credentials, or private keys. Prefer `.env.example` for documentation.
- **Pin versions for production-bound work.** Prefer pinned dependency and model versions (`GEMINI_MODEL`, etc.) when hardening for deploy; do not silently bump models in a feature PR.
- **Structured logging.** Use `backend.shared.logging.get_logger`. Prefer JSON logs in non-local environments; include correlation / event ids when available. Do not log secrets.
- **Docs track behaviour.** Update README / ADRs / this file when behaviour, contracts, or run instructions change. Do not invent metrics or eval scores in docs without measured evidence.

### Definition of done

- [ ] Principles above respected (especially no prediction / no blended score / deterministic metrics)
- [ ] Types and Pydantic contracts in place at boundaries
- [ ] Tests added or updated; known-answer cases for new metrics/scoring
- [ ] Lint and tests pass (`make lint` / `make test` or CI equivalents)
- [ ] No secrets introduced
- [ ] Docs updated if behaviour or workflow changed

---

## How to run and test

### Setup

```bash
pip install -r requirements.txt   # includes pinned ruff for lint
cp .env.example .env
```

Frontend (optional):

```bash
cd frontend && npm ci && cp .env.example .env
# VITE_API_BASE=http://localhost:8000 for local API
```

### Run

```bash
make dev
# or: PYTHONPATH=. python -m backend.main
# API: http://localhost:8000  docs: /docs  health: /health

cd frontend && npm run dev   # Vite dashboard
```

Docker: `docker-compose up --build`. Optional: `--profile pubsub` / `--profile firestore` for emulators.

### Test and lint

```bash
make lint                                    # ruff check backend/ tests/ metrics/ evals/
PYTHONPATH=. pytest tests/ metrics/tests/ -m "not evaluation"   # default backend CI set
make test-unit | make test-integration | make test-contract
PYTHONPATH=. pytest tests/ metrics/tests/    # includes evaluation (deterministic; no API key)
make eval-gate                               # metrics eval suite + offline -m evaluation
```

Frontend: `npm run lint` (oxlint), `npm run build`.

Pub/Sub and Firestore integration tests skip unless `PUBSUB_EMULATOR_HOST` / `FIRESTORE_EMULATOR_HOST` are set. Evaluation tests under `tests/evaluation/` marked `evaluation` are excluded from the default backend CI job; the **`eval-gate`** job runs them because they are offline (deterministic provider / stub Gemini, no API keys).

### Metrics eval suite (weakness detection, not prediction)

See [ADR-014](docs/decisions/ADR-014-eval-gate-weakness-detection.md) and [ADR-015](docs/decisions/ADR-015-convexity-distance-to-ruin-not-tested.md). Labelled synthetic dependency graphs in `evals/cases/` encode known structural weaknesses (monoculture, hidden SPOF, deep cascade, fragile harm curvature, ruin below/above the survival floor, low optionality/slack) plus robust controls that must not be flagged red. Ruin without an explicit probe is `not_tested`, never green. The runner reports per-metric detection recall, false-flag rate on controls, and group-status accuracy; it writes `evals/results.json` and fails if metrics regress below `evals/baseline.json` or any control is red.

```bash
PYTHONPATH=. python evals/run_evals.py       # prints report, writes results.json, checks baseline
```

Do not frame eval results as forecasts. Metric formula bugs found by the suite are fixed in a separate commit from harness/case changes.

---

## Workflow for agents

1. **Read before writing.** Inspect the real layout, ADRs, and neighbouring tests. Prefer matching existing patterns over inventing new ones.
2. **Plan large changes.** For multi-file or cross-cutting work, outline the approach, files touched, and risks before coding. Keep scope to the assigned task. Cursor rule `.cursor/rules/plan-first.mdc` requires a written plan and explicit approval before coding when the change touches more than about three files, schemas, run-record / DuckDB migrations, or any metric’s logic.
3. **Do not weaken tests.** Never delete, skip, or loosen assertions solely to make CI pass. Fix the code or add a justified, documented test change.
4. **State assumptions in the PR.** Call out concurrent work (e.g. metrics package), env expectations, and anything left as follow-up.
5. **Docs/config-only vs product code.** If the task says docs/config only, do not change application behaviour.
6. **Cursor rules.** Follow `.cursor/rules/*.mdc`; they summarise this file for scoped globs. When in conflict, **this file wins**.
7. **Cursor skills.** Use repo skills under `.cursor/skills/` when they match the task:
   - [`add-metric`](.cursor/skills/add-metric/SKILL.md) — tests-first workflow to add a fragility metric (unit + eval case, `run_all` / run-record registration, own status never a blended score, docs + ADR). Covers supply-side and optional financial-side metrics (`runway`, `customer_*`, `energy_margin`, covenants in ruin) per [ADR-019](docs/decisions/ADR-019-financial-side-model.md).
   - [`review-against-method`](.cursor/skills/review-against-method/SKILL.md) — review a diff against Aegis principles (including ADR-019 financial-side checks); pass/fail per principle with file and line references.

---

## Related docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — short human setup and PR conventions
- [README.md](README.md) — product overview and quick start
- [docs/architecture/overview.md](docs/architecture/overview.md)
- [docs/decisions/](docs/decisions/) — ADR index (product ADRs 005–013, 015–019; engineering ADRs 001–004; eval gate ADR-014)
- [`.cursor/skills/`](.cursor/skills/) — Cursor agent skills for Aegis method work
- [`.cursor/rules/`](.cursor/rules/) — Cursor rules (core principles, plan-first, metrics / Python / frontend)
