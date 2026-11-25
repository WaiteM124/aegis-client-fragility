---
name: review-against-method
description: Review a diff against Aegis product principles (no prediction, no blended score, cited worst_on_record only, deterministic engine, unknowns as fragile, no real client/.env commits, backtest cut-off). Use when reviewing a PR, finishing a change, or asked to check work against the Aegis method. Outputs pass/fail per principle with file and line references.
---

# Review against the Aegis method

Use this skill to audit a branch or diff. Read `AGENTS.md` and the cited ADRs before judging. Prefer the actual patch (`git diff` / PR files) over memory.

**Output format (required)**

For each principle below, emit exactly one verdict line, then evidence:

```
### <N>. <principle short name> — PASS | FAIL
- path/to/file.py:L12 — what you saw (quote or paraphrase)
- path/to/other.md:L4 — …
```

If there is no relevant change for a principle, mark **PASS** and note `no relevant diff` (still scan for accidental violations in touched files). A single FAIL anywhere means the review **FAIL**s overall. Do not soften FAIL into “nit” when a principle is broken.

Do not invent metrics or scores in the review. Do not suggest blended scores, probabilities, or free swing sliders as remedies.

---

## Principles to check

### 1. No prediction or forecast — PASS | FAIL

Refs: [ADR-006](../../../docs/decisions/ADR-006-no-prediction.md), `AGENTS.md`.

**FAIL if** the diff adds forecasting, event probabilities, fitted tails, historical-correlation estimates in metrics, or predictive copy in docs / API / UI (e.g. “likely”, “will happen”, “probability of X”, “expected shortfall”, Kelly-style sizing).

**PASS if** language stays structural (weaknesses, probes, flags) and maths stays non-predictive.

### 2. No probabilities — PASS | FAIL

Refs: ADR-006, [ADR-007](../../../docs/decisions/ADR-007-ai-never-scores.md).

**FAIL if** scores, statuses, or scan grids attach likelihoods / probability weights; or LLM output is used as a numeric probability.

**PASS if** intensities and ladders are structural probes with no likelihood attached.

### 3. No blended or weighted single fragility score — PASS | FAIL

Refs: [ADR-008](../../../docs/decisions/ADR-008-no-blended-fragility-score.md), [ADR-009](../../../docs/decisions/ADR-009-ruin-hard-red-flag.md).

**FAIL if** the diff introduces a cross-metric or cross-group weighted/averaged “fragility score”, overall index, or any roll-up that is not **worst-member** status (`red > amber > not_tested > green`). Softening ruin by averaging is an automatic FAIL.

**PASS if** each metric keeps its own status and groups use worst-member (ruin hard red when tested).

### 4. Swing sizes only from cited `worst_on_record` — PASS | FAIL

Refs: [ADR-015](../../../docs/decisions/ADR-015-convexity-distance-to-ruin-not-tested.md), `metrics/contracts.py` (`GraphInputSpec`), client packs.

**FAIL if** shock / scan magnitudes for convexity or distance-to-ruin style probes come from free UI sliders, AI-chosen values, or unsourced constants presented as worst moves. `worst_on_record` values used as evidence for a client/backtest must be citeable (source + publication date in the pack manifest / evidence log).

**PASS if** anchors are declared on graph `inputs[].worst_on_record` (or correctly `not_tested` when missing), and client evidence cites source and date. Synthetic eval fixtures may use fixed anchors without a live manifest — note that in evidence.

### 5. Deterministic engine — PASS | FAIL

Refs: ADR-007, [ADR-002](../../../docs/decisions/ADR-002-model-provider-abstraction.md), metrics conventions.

**FAIL if** metric `compute` or risk scoring calls an LLM, reads non-deterministic entropy for scores, or accepts model-emitted numbers as authoritative scores/statuses without deterministic Python ownership.

**PASS if** numerics and colours come from tested Python; model output (if any) is schema-validated narrative/support only.

### 6. Unknowns treated as fragile — PASS | FAIL

Refs: `clients/carillion/README.md` method freeze; ADR-015 `NOT_TESTED`.

**FAIL if** missing structure, missing probes, or unknown topology is filled with reassuring defaults that look green/safe (e.g. inventing diversifying edges; treating untested ruin as green).

**PASS if** unknowns stay conservative: omit unverified structure, use `not_tested` when a probe is absent, and do not invent comforting graph detail.

### 7. No real client data or `.env` files committed — PASS | FAIL

Refs: [ADR-018](../../../docs/decisions/ADR-018-client-packs-and-confidential-data.md), `.gitignore`.

**FAIL if** the diff commits `.env` (non-example), API keys, credentials, private keys, or confidential client `sources/` / `model/` payloads. Confidential packs must not land real evidence in git.

**PASS if** only `.env.example`, public/example packs, or clearly non-confidential skeletons are added; secrets stay out of the tree.

### 8. Backtest sources not after cut-off — PASS | FAIL

Refs: ADR-018, `metrics.client_pack.check_backtest_cut_off`.

**FAIL if** a `kind: backtest` pack’s `sources/manifest.yaml` (or added source files) includes a `publication_date` **after** `client.yaml` `cut_off_date`.

**PASS if** no backtest sources change, or all publication dates are on or before cut-off (inclusive). If validating, `python -m metrics.client_pack --validate <id>` should succeed.

---

## Review procedure

1. Identify the diff scope (`git diff origin/master...HEAD` or the PR file list).
2. Read every touched file that could affect metrics, scoring, UI copy, client packs, schemas, or secrets.
3. Score principles 1–8 with file:line evidence.
4. End with a one-line overall verdict: `OVERALL: PASS` or `OVERALL: FAIL` (list failing principle numbers).
5. Optionally suggest a fix direction that still respects the method — never “add a blended score” or “ask the model for the swing”.

When the user also asked for a method-compliance gate on metric PRs, run this skill before marking the work done.
