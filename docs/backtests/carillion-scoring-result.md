# Carillion scoring result (`carillion-method-v1`)

**Status:** scoring by agent, pending Miles’s review per
[ADR-020](../decisions/ADR-020-backtest-scoring.md).

**Frame:** structural-weakness detection on a locked map. Not a claim that
Aegis called the collapse. No blended or single score. No prediction language.

| Artefact | Path |
|---|---|
| Locked map | `clients/carillion/maps/2026-11-25T154849Z_carillion_run.json` (+ `_output.txt`) |
| Method tag | `carillion-method-v1` |
| Reference list | `clients/carillion/outcome/reference_list.yaml` (OW-01…OW-12) |
| Procedure | [ADR-020](../decisions/ADR-020-backtest-scoring.md) |
| Model / citations / gaps | `clients/carillion/model/carillion.yaml`, `CITATIONS.md`, `GAPS.md` |

Inputs were **not** edited. Metrics, thresholds, schemas, and eval baselines
were **not** changed. The map was **not** re-run or re-locked.

---

## Counts per category

| Category | Count |
|---|---|
| hit-from-evidence | 5 |
| hit-from-unknown | 1 |
| miss | 1 |
| method gap | 5 |
| false flag | 4 |

Reference-list items: 12 (five pre-marked `not_representable`). Categories are
not merged into one success rate.

---

## Per-item table

| Item | Mapped metric(s) | Map status (mapped metrics) | Drivers (on flagged mapped metrics) | Category | Evidence or unknown | Judgement note |
|---|---|---|---|---|---|---|
| OW-01 Unsustainable debt-funded acquisitive growth | runway; distance_to_ruin; ruin | runway RED; distance_to_ruin AMBER; ruin GREEN | DTR: `liquidity_shock:1.710x/survival_floor`, `me_order_book_shock:1.414x/survival_floor`, `supply_shock:NOT_TESTED`, `construction_cost_shock:NOT_TESTED`. Runway drivers do not name OW-01 entities (`unknown:fixed_monthly_outflows` only). | hit-from-evidence | evidence | Hit via **distance_to_ruin** naming mapped `liquidity_shock` (cited WOR 0.31). `committed_bank_facilities` never appears in drivers. Runway RED not credited (wrong drivers). |
| OW-02 Thin cash generation and working-capital fragility | runway; distance_to_ruin | runway RED; distance_to_ruin AMBER | Same DTR drivers as OW-01 (includes `liquidity_shock:…`). Runway: `unknown:fixed_monthly_outflows` only. | hit-from-evidence | evidence | Hit via **distance_to_ruin** / `liquidity_shock`. Strict reading: `unknown:fixed_monthly_outflows` does **not** name mapped entity `liquidity` or `liquidity_shock` — runway not credited (see J-S03). |
| OW-03 Early Payment Facility as hidden supplier-financed credit | single_points_of_failure; optionality; cascade_depth; runway | SPOF GREEN; optionality GREEN; cascade_depth AMBER; runway RED | cascade_depth: `uk_epf_suppliers`. Runway does not name EPF nodes. | hit-from-evidence | evidence | Hit via **cascade_depth** naming mapped `uk_epf_suppliers` (cited EPF topology). Node `early_payment_facility` itself is absent from all RED/AMBER drivers; SPOF and optionality are GREEN (see J-S04). |
| OW-04 Systematic late payment / supply-chain exploitation | single_points_of_failure; cascade_depth; hhi; monoculture | SPOF GREEN; cascade_depth AMBER; hhi AMBER; monoculture RED | hhi: `uk_epf_suppliers`, `uk_direct_suppliers`. monoculture: `region:uk`, `uk_epf_suppliers`, `uk_direct_suppliers`, `back_office_outsourcing_partner`. cascade_depth: `uk_epf_suppliers`. | hit-from-evidence | evidence | Hit via **hhi**, **monoculture**, and **cascade_depth** naming mapped supplier nodes. Payment-term length itself remains unrepresentable (reference-list residual). |
| OW-05 Aggressive optimistic revenue recognition | *(not_representable)* | — | — | method gap | — | Pre-committed `not_representable`; no map comparison. |
| OW-06 Material losses on major long-term construction contracts | convexity; distance_to_ruin; ruin | convexity RED; distance_to_ruin AMBER; ruin GREEN | convexity: `shape=fragile`, `mean_curvature=…`, `cliffs=7`, `unknown_margin:smart_motorways_highways_england`, `unknown_margin:a14_cambridge_huntingdon`. DTR names `liquidity_shock` / `me_order_book_shock`; `construction_cost_shock:NOT_TESTED`. | miss | — | No flagged driver names `construction_ex_me_book`, `me_construction_book`, platforms, or a **tested** `construction_cost_shock`. Convexity RED names Highways England awards (OW-12 entities), not the mapped segment books. Method can represent the item; detection at driver level failed (see J-S05). |
| OW-07 Reckless Middle East / overseas construction expansion | convexity; customer_monoculture; distance_to_ruin | convexity RED (no ME book drivers); customer_monoculture RED; distance_to_ruin AMBER | customer_monoculture: `public_sector:false`, `uk_other_customers`, `mena_customers`, `canada_customers`, `row_customers`. DTR includes `me_order_book_shock:1.414x/survival_floor`. | hit-from-evidence | evidence | Hit via **distance_to_ruin** / cited `me_order_book_shock` and **customer_monoculture** naming `mena_customers`. Convexity does not name ME book/platform. `public_sector:false` encoding artefact also present in drivers (GAPS.md) — logged, not used to deny the `mena_customers` match (J-S06). |
| OW-08 Underfunded DB pension obligations | *(not_representable)* | — | — | method gap | — | Pre-committed `not_representable`. |
| OW-09 Dividends ahead of cash generation / deficit repair | *(not_representable)* | — | — | method gap | — | Pre-committed `not_representable`. |
| OW-10 Acquisition goodwill carrying values | *(not_representable)* | — | — | method gap | — | Pre-committed `not_representable`. |
| OW-11 Debt-covenant headroom / EPF classification | *(not_representable)* | — | — | method gap | — | Pre-committed `not_representable`. Survival-floor / runway RED not credited as OW-11 (reference-list rule). |
| OW-12 Low-margin fixed-price construction book | convexity | convexity RED | `shape=fragile`, `mean_curvature=…`, `cliffs=7`, `unknown_margin:smart_motorways_highways_england`, `unknown_margin:a14_cambridge_huntingdon` | hit-from-unknown | unknown | Drivers name mapped awards `smart_motorways_highways_england` and `a14_cambridge_huntingdon` only via `unknown_margin:*` (null margins → fragile). Segment books with cited thin margins are not named in drivers. `construction_cost_shock` NOT_TESTED (J-S07). |

---

## False flags

RED/AMBER metrics whose drivers match **no** reference-list mapped entity
(after the pre-committed mappings).

| Metric | Status | Drivers | Why false flag |
|---|---|---|---|
| customer_hhi | AMBER | `uk_other_customers` | No OW item maps to `customer_hhi` or `uk_other_customers`. Public-sector concentration was excluded (EX-01). |
| customer_spof | RED | `uk_infrastructure_services`, `uk_other_customers`, `public_sector:uk_infrastructure_services` | No OW item maps to `customer_spof` or these customer IDs (EX-01). |
| runway | RED | `unknown:fixed_monthly_outflows` | Metric is listed on OW-01/02/03, but this driver string names none of those items’ mapped entity IDs. Flag is gap-as-fragile on a null field, not a reference-list driver match. |
| slack | RED | `support_services_platform->carillion` | No OW item maps to `slack` or `support_services_platform`. |

**False-flag count: 4.**

Not false flags (matched at least one item’s mapped drivers): `hhi`,
`monoculture`, `customer_monoculture`, `cascade_depth`, `convexity`,
`distance_to_ruin`.

Green / not-tested metrics are out of scope for false flags:
`single_points_of_failure` (GREEN), `ruin` (GREEN), `optionality` (GREEN),
`energy_margin` (NOT_TESTED, `optional_section_absent`).

---

## Discrimination

| Quantity | Value |
|---|---|
| Metrics on locked map | 14 |
| Flagged (RED or AMBER) | 10 |
| Share flagged | 10/14 (~71%) |
| Group colours | Concentration RED; Contagion RED; Convexity RED; Optionality RED |

All four metric groups are RED. A map that flags most metrics (and every
group) carries little discrimination: group-level RED agreement is
uninformative when everything is RED. Driver-level matching against the
reference list is what carries information here (ADR-020 §3, §5).

---

## Judgement log

| ID | Topic | Decision | Reason |
|---|---|---|---|
| J-S01 | Mapping freeze | No mapping changed. Ambiguities logged only. | ADR-020 integrity; user instruction. |
| J-S02 | OW-01 / OW-02 hit basis | Credit **hit-from-evidence** on `distance_to_ruin` naming `liquidity_shock`. | Cited WOR; driver string contains mapped entity id. Overall DTR value is the ME multiple (1.414×); liquidity still appears in drivers at 1.710×. |
| J-S03 | Runway vs OW-02 | Do **not** treat `unknown:fixed_monthly_outflows` as naming mapped `liquidity`. | ADR-020 requires drivers to **name** the mapped entity id. Field-level unknown ≠ section id `liquidity`. Consequence: runway RED is a false flag, not an OW-02 hit-from-unknown. |
| J-S04 | OW-03 without `early_payment_facility` driver | Still a hit via `uk_epf_suppliers` on cascade_depth. | Pre-committed mapping lists either node. Logged that the EPF route node itself never appears in flagged drivers; SPOF/optionality GREEN. |
| J-S05 | OW-06 as miss (not method gap) | Miss. | Convexity and ruin can represent structural contract-loss exposure; they were tested. Drivers failed to name mapped segment books / platforms. `construction_cost_shock:NOT_TESTED` alone does not reclassify the whole item as method gap while other mapped metrics ran. |
| J-S06 | OW-07 and `public_sector:false` | Credit hit; note artefact. | `mena_customers` and `me_order_book_shock` are explicit mapped matches. GAPS.md encoding of unknown residual as `public_sector:false` is present but does not erase those matches. |
| J-S07 | OW-12 evidence vs unknown | **hit-from-unknown**. | Only contract ids in drivers are `unknown_margin:smart_motorways…` and `unknown_margin:a14…`. Metric forces RED when contract margins are unknown. Cited thin margins on segment books did not appear as drivers. |
| J-S08 | False-flag runway | Count runway as false flag. | Drivers match no reference-list entity id after strict naming (J-S03). |
| J-S09 | Contamination | Accepted per ADR-020 §7. | Reference list fixed before scoring; matching at driver level; judgements logged for Miles’s review. |

---

## Implications for method v2

Gaps found (names only — method unchanged under `carillion-method-v1`):

1. Accounting-policy / revenue-recognition aggressiveness probe (OW-05)
2. Pensions section / deficit-funding metric (OW-08)
3. Dividend / capital-return object (OW-09)
4. Goodwill / intangible carrying-value probe (OW-10)
5. Numeric covenant limits and EPF-as-debt covenant classification (OW-11)
6. Payment-term length as a first-class input (OW-04 residual)
7. `construction_cost_shock` WOR absence → distance probe NOT_TESTED (OW-06)
8. Convexity driver surfacing: unknown-margin named awards fire; cited thin-margin segment books do not appear in drivers (OW-06 miss / OW-12 unknown path)
9. `fixed_monthly_outflows` null → runway RED without naming liquidity entities (false flag vs OW cash items)
10. `early_payment_facility` node absent from flagged drivers despite EPF topology in the model (OW-03 partial)
11. Customer concentration / SPOF flags without reference-list counterparts (discrimination / false-flag load; EX-01)

Findings feed a **new** method tag only; do not retrofit this freeze or edit
the locked map.
