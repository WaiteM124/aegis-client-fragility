# ADR-015: Convexity from model output; distance to ruin; NOT_TESTED status

**Date:** 2026-11-25

## Context

Three structural weaknesses in the metrics package needed fixing, and one gap needed closing:

1. **Ruin without a probe looked safe.** With no shock configured, ruin silently ran the default 10/20/50% ladder and could report GREEN. An untested company looked resilient.
2. **SPOF status ignored criticality.** One cut node was always AMBER and two or more RED, so a sole supplier on a critical flow could not go RED on its own.
3. **Convexity was circular.** Edges declared a `stress_response` label (buffered / linear / decelerating / cliff) and tests asserted that the label’s shape appeared. The answer was an input.
4. **Distance to ruin was missing.** Operators need, per input, how many times the worst-on-record move fits before a configured ruin line is crossed — without averaging across inputs or attaching probabilities.

## Decision

### NOT_TESTED status

Extend `Status` with `not_tested`. Ruin returns `NOT_TESTED` (never GREEN) when no explicit probe is configured: no node/edge shocks, no `scenario.run_stress_ladder` / `stress_ladder`, and no explicit `ladder=` argument. CLI opt-in: `--stress-ladder`.

`NOT_TESTED` is never counted as a pass. Group roll-up ranks
`red > amber > not_tested > green`, so an untested member cannot make a group look green.

### SPOF criticality is explicit

Graph nodes may set `critical: true` (sole supplier, sole critical route, sole site for a critical output). Criticality is **not** inferred from topology.

- no cut nodes → GREEN  
- cut nodes only on non-critical paths → AMBER  
- any critical cut node → RED (even if count = 1)

### Convexity from model output

Convexity is measured from the model’s actual harm (loss) curve via symmetric second differences:

\[
\Delta^2(d) = \mathrm{harm}(x+d) + \mathrm{harm}(x-d) - 2\cdot\mathrm{harm}(x)
\]

anchored on each input’s `worst_on_record` move, with step sizes
\(d \in \{0.25, 0.5, 1.0, 1.5, 2.0\}\times W\). The scan grid carries **no likelihoods**.

- Clearly positive curvature → FRAGILE  
- Near zero → ROBUST  
- Clearly negative → ANTIFRAGILE (own flag, not merely green)  
- Large neighbouring jumps → cliff, reported separately; cliffs elevate status at least to amber  

Bounded inputs are clamped; clamping sites are reported. Edge `stress_response` labels may remain as modelling inputs but must not be what tests assert.

This supersedes the label-circular reading described in [ADR-011](ADR-011-stress-ladder.md) for convexity classification. The stress ladder remains the explicit ruin probe ([ADR-009](ADR-009-ruin-hard-red-flag.md)).

### Distance to ruin

New metric `metrics/distance_to_ruin.py`:

- Per input, scan multiples of `worst_on_record`, then bisect to the ruin line (survival floor / covenant).
- Report ruin multiple (or “no ruin within scan range […]”), whether harm accelerates (reuses convexity), and which line broke.
- Never average across inputs; ruin is absorbing.
- Status cut-offs live in versioned `DistanceToRuinThresholds` (default: ≤1× RED, ≤2× AMBER, beyond GREEN).
- Missing `ruin_line` or `worst_on_record` → `NOT_TESTED`.

## Status

Accepted

## Consequences

- Contracts: `Status.NOT_TESTED`, `GraphInputSpec`, `RuinLineSpec`, node `critical`, `Scenario.run_stress_ladder`.
- Modules: `ruin.py` v2, `single_points_of_failure.py` v2, `convexity.py` v2, new `distance_to_ruin.py`; wired into `run_all` Convexity group.
- Example YAMLs and eval cases gain `inputs`, `ruin_line`, and critical flags; ruin-detecting evals set `scenario.run_stress_ladder: true`.
- Eval baseline updated for intentional status shifts (controls’ Convexity group is `not_tested` without an explicit ruin probe).
- Related: [ADR-006](ADR-006-no-prediction.md), [ADR-008](ADR-008-no-blended-fragility-score.md), [ADR-009](ADR-009-ruin-hard-red-flag.md), [ADR-011](ADR-011-stress-ladder.md), [ADR-014](ADR-014-eval-gate-weakness-detection.md).

## Alternatives rejected

- **Keep silent default ladder for ruin** — makes untested graphs look safe.  
- **Infer criticality from sole-supplier topology** — opaque; criticality must be declared.  
- **Keep label→shape convexity tests** — circular; fails the “labels removed ⇒ same result” check.  
- **Single blended distance-to-ruin score across inputs** — hides absorbing ruin and invents a blend ([ADR-008](ADR-008-no-blended-fragility-score.md)).  
- **Attach probabilities to the scan grid** — prediction; forbidden ([ADR-006](ADR-006-no-prediction.md)).
