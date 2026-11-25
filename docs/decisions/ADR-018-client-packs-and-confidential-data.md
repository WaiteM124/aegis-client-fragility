# ADR-018: Per-client packs; confidential data stays out of git

**Date:** 2026-11-25

## Context

Structural-fragility work needs evidence, dependency models, locked maps, and
run history to stay **per client** and traceable. Mixing example graphs,
backtests, and live client material in one tree invites leaks and muddles
cut-off rules. Real client evidence must not land in a public or shared git
remote.

## Decision

1. **One folder per client** under `clients/<client_id>/` with
   `client.yaml`, `model/`, `sources/manifest.yaml`, `maps/` (locked,
   date-stamped, never edited after creation), and `runs/` (local,
   gitignored).
2. **Schemas** for `client.yaml` and `sources/manifest.yaml` live under
   `clients/schemas/` and are validated in tests. Backtest packs require
   `cut_off_date`; any source with `publication_date` after that cut-off fails
   a check.
3. **Classification.** `data_classification` is `public` | `example` |
   `confidential`. Packs marked **confidential** must not have files under
   `sources/` or `model/` committed. CI runs
   `python -m metrics.client_pack --check-confidential`. Real client data
   belongs in **private cloud storage**, not git.
4. **Run records.** `run_record.v2` adds `client_id`; DuckDB migration 002
   adds the column. v1 records remain loadable (`client_id` NULL).
   `metrics.run_all --client <id>` resolves models, writes
   `clients/<id>/runs/`, and with `--store` loads DuckDB; `--lock` copies into
   `maps/` with a date stamp and refuses overwrite.

## Status

Accepted

## Consequences

- Example packs (e.g. ChillCo) may commit made-up models; backtests may commit
  public sources on or before the cut-off; confidential packs keep payloads
  out of the repository.
- Operators use private object storage / a private repo mirror for live client
  evidence and graphs, syncing into a local `clients/<id>/` that stays
  untracked or gitignored.
- Locked maps for public/example/backtest work can be committed when that is
  the intentional audit trail; confidential locked maps follow the same
  private-storage rule.

## Alternatives rejected

- **Single shared `data/` tree for all clients.** Hides ownership and makes
  cut-off / classification enforcement harder.
- **Encrypt secrets in git.** Still accumulates sensitive material in history;
  private storage is simpler and safer for this portfolio stage.
- **Blended “client score” across packs.** Violates the no-blended-score
  principle ([ADR-008](ADR-008-no-blended-fragility-score.md)).
