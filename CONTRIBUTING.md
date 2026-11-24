# Contributing

Short human guide. Agents and detailed product rules: see [AGENTS.md](AGENTS.md).

## Setup

**Prerequisites:** Python 3.12+, pip; optional Node.js 18+ (dashboard), Docker (Compose / emulators).

```bash
pip install -r requirements.txt   # includes pinned ruff for `make lint`
cp .env.example .env
```

Default `.env` uses the deterministic model, SQLite, in-memory bus, and lexical retrieval — no API keys.

Dashboard:

```bash
cd frontend
npm ci
cp .env.example .env   # VITE_API_BASE=http://localhost:8000
```

## Running

```bash
make dev                 # API on http://localhost:8000
cd frontend && npm run dev
# or: docker-compose up --build
```

## Tests and lint

```bash
make lint
PYTHONPATH=. pytest tests/ -m "not evaluation"   # matches CI
make test-unit
make test-integration
make test-contract
cd frontend && npm run lint && npm run build
```

Evaluation tests (`tests/evaluation/`) use the deterministic provider and local fixtures; they are excluded from the default CI job via `-m "not evaluation"`.

## Branch and PR conventions

- Branch from `master` with a short, descriptive name.
- Keep PRs **small and focused** on one concern.
- Fill in the pull request template checklist.
- State assumptions, concurrent work, and follow-ups in the description.
- Do not commit secrets; use env vars or a secret manager.
- Do not delete or weaken tests solely to make CI pass.

## Definition of done

- Product principles in `AGENTS.md` respected (no prediction; no blended fragility score; deterministic metrics)
- Tests added/updated and passing; lint clean
- No secrets in the change
- Docs updated when behaviour or workflow changes
- CI green on the PR
