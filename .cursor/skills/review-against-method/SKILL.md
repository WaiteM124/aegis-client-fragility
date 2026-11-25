---
name: review-against-method
description: Review a diff against Aegis product principles (no prediction, no blended score, cited worst_on_record only, deterministic engine, unknowns as fragile, no real client/.env commits, backtest cut-off). Includes ADR-019 financial-side checks (runway, customer_*, energy_margin, covenants in ruin). Use when reviewing a PR, finishing a change, or asked to check work against the Aegis method. Outputs pass/fail per principle with file and line references.
---

# Review against the Aegis method

Use this skill to audit a branch or diff. Read `AGENTS.md` and the cited ADRs before judging (include [ADR-019](../../../docs/decisions/ADR-019-financial-side-model.md) when financial sections or related metrics are touched). Prefer the actual patch (`git diff` / PR files) over memory.

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

**PASS if** language stays structural (weaknesses, probes, flags) and maths stays non-predictive — including runway, covenants, customers, and energy.

### 2. No probabilities — PASS | FAIL

Refs: ADR-006, [ADR-007](../../../docs/decisions/ADR-007-ai-never-scores.md).

**FAIL if** scores, statuses, or scan grids attach likelihoods / probability weights; or LLM output is used as a numeric probability.

**PASS if** intensities and ladders are structural probes with no likelihood attached.

### 3. No blended or weighted single fragility score — PASS | FAIL

Refs: [ADR-008](../../../docs/decisions/ADR-008-no-blended-fragility-score.md), [ADR-009](../../../docs/decisions/ADR-009-ruin-hard-red-flag.md), ADR-019.

**FAIL if** the diff introduces a cross-metric or cross-group weighted/averaged “fragility score”, overall index, or any roll-up that is not **worst-member** status (`red > amber > not_tested > green`). Softening ruin by averaging is an automatic FAIL. Also **FAIL** if supplier and customer concentration/SPOF are merged into one number (`customer_hhi` / `customer_monoculture` / `customer_spof` must stay separate labelled results).

**PASS if** each metric keeps its own status and groups use worst-member (ruin hard red when tested; optional-section `NOT_TESTED` with `optional_section_absent` correctly excluded from roll-up).

### 4. Swing sizes only from cited `worst_on_record` — PASS | FAIL

Refs: [ADR-015](../../../docs/decisions/ADR-015-convexity-distance-to-ruin-not-tested.md), ADR-019, `metrics/contracts.py` (`GraphInputSpec`, liquidity / covenants / energy fields), client packs.

**FAIL if** shock / scan magnitudes for convexity, distance-to-ruin, **runway**, **covenant** headroom, **energy_margin**, or similar probes come from free UI sliders, AI-chosen values, or unsourced constants presented as worst moves. `worst_on_record` values used as evidence for a client/backtest must be citeable (`source` + publication date in the pack manifest / evidence log).

**PASS if** anchors are declared on graph `inputs[].worst_on_record` and/or section fields that point at those inputs (or correctly `not_tested` / fragile-unknown when missing), and client evidence cites source and date. Synthetic eval fixtures may use fixed anchors without a live manifest — note that in evidence.

### 5. Deterministic engine — PASS | FAIL

Refs: ADR-007, [ADR-002](../../../docs/decisions/ADR-002-model-provider-abstraction.md), metrics conventions.

**FAIL if** metric `compute` or risk scoring calls an LLM, reads non-deterministic entropy for scores, or accepts model-emitted numbers as authoritative scores/statuses without deterministic Python ownership.

**PASS if** numerics and colours come from tested Python (`runway`, `customer_*`, `energy_margin`, covenant logic in `ruin` / `distance_to_ruin`, helpers in `metrics/finance.py`); model output (if any) is schema-validated narrative/support only.

### 6. Unknowns treated as fragile — PASS | FAIL

Refs: `clients/carillion/README.md` method freeze; ADR-015 `NOT_TESTED`; ADR-019.

**FAIL if** missing structure, missing probes, or unknown topology is filled with reassuring defaults that look green/safe (e.g. inventing diversifying edges; treating untested ruin as green; inventing cash / covenant `current` / WOR when a financial section is present).

**PASS if** unknowns stay conservative: omit unverified structure; use `not_tested` when a probe or optional section is absent; when a financial section is present but required fields are missing → fragile (red); do not invent comforting graph detail. Covenants add ruin lines beside `survival_floor` — they must not silently replace or drop the floor.

### 7. No real client data or `.env` files committed — PASS | FAIL

Refs: [ADR-018](../../../docs/decisions/ADR-018-client-packs-and-confidential-data.md), `.gitignore`.

**FAIL if** the diff commits `.env` (non-example), API keys, credentials, private keys, or confidential client `sources/` / `model/` payloads (including real liquidity, covenant, or customer figures). Confidential packs must not land real evidence in git. Example / EXAMPLE DATA packs must stay clearly labelled as such.

**PASS if** only `.env.example`, public/example packs, or clearly non-confidential skeletons are added; secrets stay out of the tree.

### 8. Backtest sources not after cut-off — PASS | FAIL

Refs: ADR-018, `metrics.client_pack.check_backtest_cut_off`.

**FAIL if** a `kind: backtest` pack’s `sources/manifest.yaml` (or added source files) includes a `publication_date` **after** `client.yaml` `cut_off_date`.

**PASS if** no backtest sources change, or all publication dates are on or before cut-off (inclusive). If validating, `python -m metrics.client_pack --validate <id>` should succeed.

---

## Financial-side quick scan (when relevant)

If the diff touches `liquidity` / `covenants` / `contracts` / `customers` / `energy`, `clients/schemas/dependency_graph.v1.json`, or metrics `runway` / `customer_*` / `energy_margin` / covenant paths in `ruin` / `distance_to_ruin`:

- Confirm optional sections do not break supply-only graphs.
- Confirm no supplier↔customer blend.
- Confirm every swing uses cited `worst_on_record`.
- Confirm missing required financial fields → fragile, not green.
- Cite file:line under principles 3, 4, and 6 as appropriate (do not add a ninth principle).

---

## Review procedure

1. Identify the diff scope (`git diff origin/master...HEAD` or the PR file list).
2. Read every touched file that could affect metrics, scoring, UI copy, client packs, schemas, or secrets.
3. Score principles 1–8 with file:line evidence.
4. End with a one-line overall verdict: `OVERALL: PASS` or `OVERALL: FAIL` (list failing principle numbers).
5. Optionally suggest a fix direction that still respects the method — never “add a blended score” or “ask the model for the swing”.

When the user also asked for a method-compliance gate on metric PRs, run this skill before marking the work done.
