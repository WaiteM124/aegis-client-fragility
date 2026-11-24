## Summary

<!-- What changed and why. State assumptions and out-of-scope items. -->

## Checklist

- [ ] **Principles respected** — no prediction / forecasting in metrics or copy; no blended fragility score; LLMs do not produce scores; ruin remains a hard red flag ([AGENTS.md](../AGENTS.md))
- [ ] **Tests added or updated** — known-answer cases where scoring/metrics change; existing tests not weakened or deleted to pass
- [ ] **Tests and lint passing** — `ruff check` / frontend lint and the relevant pytest / build suite (CI green)
- [ ] **No secrets** — no API keys, credentials, or private keys in code or this PR
- [ ] **Docs updated** — README / ADRs / `AGENTS.md` / `CONTRIBUTING.md` updated if behaviour or workflow changed

## Test plan

<!-- Commands run locally, or "rely on CI". -->
