# ADR-020: Public backtest scoring (structural weakness detection)

**Date:** 2026-11-25

## Context

The Carillion plc public pack has a blind model and a locked map under method
tag `carillion-method-v1` (see
[docs/backtests/carillion-method-freeze.md](../backtests/carillion-method-freeze.md)).
The next step is to score that map against post-event evidence.

[ADR-013](ADR-013-hormuz-case-study-dropped.md) forbids using a pre-registered
**event** backtest as the product's proof: that framing rewards forecasting a
headline. A public historical pack can still be useful if it answers a
different question — whether the locked map flagged the **structural
weaknesses** that later mattered — without probabilities, blended scores, or a
claim that Aegis "called" the collapse ([ADR-006](ADR-006-no-prediction.md),
[ADR-008](ADR-008-no-blended-fragility-score.md)).

Without fixed scoring rules, comparison drifts into group-level RED counts
(uninformative when every group is RED), outcome storytelling, or retrofitting
the frozen method. This ADR locks the scoring procedure **before** any outcome
comparison.

## Decision

### 1. Purpose and relation to ADR-013

The public backtest is **evidence of structural-weakness detection**, not
product proof and not a prediction. It asks: given only pre-cut-off public
evidence and a frozen method, did the locked map flag the structural
weaknesses that authoritative post-event sources later named as causal or
contributing?

It does **not** ask whether Aegis would have forecast insolvency, timing, or
severity. It does not replace the synthetic eval gate
([ADR-014](ADR-014-eval-gate-weakness-detection.md)) as the regression proof
for metric behaviour. ADR-013 still stands: an event-prediction retrospective
is not how we claim the product works. This ADR defines the allowed
structural-scoring use of a locked public pack.

### 2. Outcome reference list — procedure only

Before the locked map is opened for comparison, a separate PR commits an
**outcome reference list**. That PR contains no scoring results. This ADR
defines the list by procedure only; it includes **no** named outcome facts.

| Rule | Requirement |
|---|---|
| **Source classes** | Authoritative **post-event** public records only — e.g. parliamentary / select-committee reports, Official Receiver or Insolvency Service reports, regulator or enforcement findings, and similarly primary official inquiries. Secondary journalism and commentary are out of scope for the reference list. |
| **Extraction** | Each list item is a structural weakness **named by the source** as causal or contributing. We do not invent weaknesses from hindsight narrative; the source's wording carries the claim. |
| **Pre-commit** | The list is written and merged in its **own PR** before any scoring PR. |
| **Metric mapping** | Before comparison, every list item is mapped to the Aegis metric(s) and driver(s) that would constitute a hit (node, edge, contract, customer, or financial input id). Mapping is logged; ambiguous mappings are judgement calls (see Integrity). |
| **No facts in this ADR** | This decision record does not list Carillion (or any other pack's) outcome items. |

### 3. Match at driver level, not group level

A group status of RED is **not** a hit by itself. When every group is RED,
group-level agreement carries little information.

A **hit** requires:

1. A metric status of **RED** or **AMBER** on a metric mapped to the reference
   item; and
2. Drivers on that metric result that **name** the relevant node, edge,
   contract, customer, or financial input identified in the pre-committed
   mapping.

Worst-member group roll-up ([ADR-008](ADR-008-no-blended-fragility-score.md))
remains how the product reports group colour; it is not the backtest scoring
unit.

### 4. Categories

Each reference-list item, and each flagged metric without a matching item, is
placed in exactly one of the following categories. Categories are **never
merged** into a single success rate or blended score.

| Category | Definition |
|---|---|
| **hit-from-evidence** | Flagged metric (RED/AMBER) whose drivers name the mapped entity, and the flag is driven by **cited pack data** (not only by a gap). |
| **hit-from-unknown** | Flagged metric (RED/AMBER) whose drivers name the mapped entity, but the flag is driven **only** by a gap treated as fragile (unknown → fragile). Reported **separately** from hit-from-evidence; never pooled into one hit count. |
| **miss** | A mapped metric is **GREEN** for a reference item that the method can represent. |
| **method gap** | The weakness has **no representation** in the frozen method or schema (e.g. pensions as a first-class section, numeric covenant limits absent from public instruments), or the relevant metric is `NOT_TESTED` / `optional_section_absent`. Reported **separately** from misses — absence of a probe is not a failed detection. |
| **false flag** | A metric is RED or AMBER with drivers that do **not** match any reference-list item (after the logged mapping). |

### 5. Reporting

Scoring output must include:

- **Counts per category** (five numbers; no roll-up into one score).
- A **per-item table**: reference item → mapped metric(s)/driver(s) → category
  → short reason (including whether the flag was evidence-driven or
  unknown-driven).
- **Discrimination:** the share of metrics on the locked map that are flagged
  (RED or AMBER), plus an explicit statement that a map flagging everything
  carries little information.

Do **not** publish a single combined hit rate, F1, or "backtest score".

### 6. Integrity

- The **locked map** under `clients/<id>/maps/` and the **method tag** (e.g.
  `carillion-method-v1`) are **never edited** after creation.
- Findings feed a **new** method version (e.g. `carillion-method-v2`) via a
  later ADR and freeze — they are **never retrofitted** onto the frozen tag or
  locked artefacts.
- Scoring is drafted by an agent and **reviewed and approved by Miles** before
  the scoring PR merges.
- Any judgement call (mapping ambiguity, evidence-vs-unknown attribution,
  borderline driver match) is **logged with its reason** in the scoring
  artefact.

### 7. Contamination

The LLM assisting with scoring **knows the public outcome**. That is
accepted and mitigated, not denied:

1. The reference list is fixed by procedure and committed **before** scoring.
2. Matching is at **driver** level against that list, not free narrative.
3. Judgement calls are logged with reasons for human review.

Contamination is not cured by pretending the model is blind after cut-off.

## Status

Proposed

## Consequences

- Carillion (and any later public backtest) scoring follows this ADR before
  outcome comparison. Implementation artefacts (reference list PR, then scoring
  PR) stay docs/report only unless a separate, approved plan changes method
  code under a new method tag.
- [ADR-013](ADR-013-hormuz-case-study-dropped.md) gains a pointer: structural
  scoring of a locked pack is allowed under this ADR; event-prediction proof
  remains forbidden.
- Method-freeze docs point here for scoring rules
  ([docs/backtests/carillion-method-freeze.md](../backtests/carillion-method-freeze.md)).
- No change in this decision to metrics, thresholds, schemas, eval baselines,
  or locked maps.

## Alternatives rejected

- **Group-level RED as a hit** — uninformative when all groups are RED; hides
  whether the right drivers fired.
- **Single combined backtest score** — blends categories and softens method
  gaps; violates [ADR-008](ADR-008-no-blended-fragility-score.md).
- **Pooling hit-from-unknown with hit-from-evidence** — credits gap-as-fragile
  the same as cited structure; obscures what the pack actually showed.
- **Counting method gaps as misses** — punishes missing schema representation
  as if the metric failed; blocks honest freeze findings.
- **Editing the locked map or `carillion-method-v1` after findings** —
  destroys the blind freeze; retrofit is forbidden.
- **Event-prediction retrospective as product proof** — already rejected by
  [ADR-013](ADR-013-hormuz-case-study-dropped.md) and
  [ADR-006](ADR-006-no-prediction.md).
