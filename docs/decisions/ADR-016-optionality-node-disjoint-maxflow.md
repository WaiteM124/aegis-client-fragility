# ADR-016: Optionality counts node-disjoint corridors (Menger / max-flow)

**Date:** 2026-11-25

## Context

Optionality v1 packed simple paths while treating only `asset` / `route` nodes as
cuts. Supplier nodes were reusable across packed paths. That misread graphs such
as `hidden_shared_subtier`: two assemblers look like alternate corridors, but both
start at the same upstream supplier, so there is only one independent way out.
The metric reported `O = 2` / GREEN.

## Decision

Optionality v2 counts **node-disjoint** supply corridors via Menger’s theorem,
implemented as max-flow on a node-split network:

1. Add a super-source σ feeding every supplier.
2. Split every non-sink node `v` into `v_in → v_out` with capacity 1.
3. Map each original edge `u → v` to `u_out → v_in` with capacity ∞.
4. `O = max-flow(σ → client)`.

Shared sources count as shared: a supplier used by two apparent routes admits
only one unit of flow through its split node. Drivers list packed paths and
`shared_collapse:<node>` for nodes that lie on every supplier→client path when
apparent route count exceeds `O`.

Status thresholds are unchanged (green if `O ≥ 2`, amber if `O = 1`, red if
`O = 0`). This remains a structural count — not a forecast of path usage and
not part of any blended fragility score.

## Status

Accepted

## Consequences

- `metrics/optionality.py` version bumps to `2.0.0`.
- `hidden_shared_subtier` → `O = 1`, non-green; shared collapse names `subtier`.
- Graphs with one shared source and two downstream routes (e.g.
  `two_parallel_routes`, eval `spof-003`) correctly fall to `O = 1`.
- Truly independent corridors (distinct suppliers, no shared internal nodes)
  stay at `O ≥ 2` (e.g. control parallel-independent).
- Eval case `spof-003` expected Optionality group status updates from green to
  amber — the change matches the corrected definition, not a loosened gate.

## Alternatives rejected

- **Keep suppliers reusable; only cut assets/routes.** Leaves the hidden-subtier
  false green in place.
- **Edge-disjoint max-flow.** Would still treat two edges out of one shared
  supplier as independent corridors.
- **Heuristic path packing without flow.** Harder to prove correct on denser
  graphs; max-flow is the standard reduction.
