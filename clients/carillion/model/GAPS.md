# Carillion model — known unknowns (treated as fragile)

Cut-off: **2017-03-01**. Where the logged pack does not state a figure, the
model leaves it **unknown**. Under the frozen method, unknowns are treated as
**fragile** (not as reassuring defaults). No figure below was invented to “fill
in” structure.

## Pack-level gaps (from `clients/carillion/README.md`)

| Unknown | Why unknown at cut-off | Method treatment |
|---|---|---|
| Credit-rating reports | No pre-cut-off rating reports in the manifest | Fragile unknown — no rating-based covenant or swing |
| Agreed 31 Dec 2016 triennial pension valuation | fy-results-2016 states the valuation was **not yet agreed**; deficit recovery assumed similar pending agreement | Fragile unknown — IAS 19 deficit and £46.6m contributions are cited, but funding valuation outcome is unknown |
| Full facility agreement | Only RNS summaries / account notes; instrument not public | Fragile unknown — numerical covenant tests absent |
| US private placement note purchase agreement | Not found as a public document | Fragile unknown — stock £360.8m cited; covenants/tests not |
| Convertible bond instrument | Not found as a public document beyond account notes | Fragile unknown — £170m stock cited; holder rights only partially summarised in AR |

## Schema / expression gaps (not fixed by changing frozen code)

| Item | What the pack says | Why it is not in `carillion.yaml` | Treatment |
|---|---|---|---|
| Financial covenants — numerical limits | ar-2015 going-concern note: Board forecasts “covenants associated with the Group’s bank facilities and private placement funding” so they continue to be met. No published numerical tests (e.g. max net debt/EBITDA, interest cover). | `dependency_graph.v1` requires `covenants[].limit` as a **number**. Unknown limits cannot be expressed without inventing them or changing the schema (forbidden under the freeze). | `covenants: []` in the model; wording recorded here. Covenant ruin lines are therefore **absent** → related distance probes do not use covenant lines; absence is not a pass on covenant headroom. |
| Support-services / FM contract pricing type | Nationwide, Centrica, Openreach, Scape, MoD FM, etc. disclosed as contracts/frameworks with values; **fixed vs cost-plus not stated**. | `contracts[].pricing` is required enum `fixed` \| `cost_plus`. | Listed under “Contracts omitted” below; not entered as contracts. |
| Contract-level margins for named awards | Segment margins disclosed; individual award margins not. | Entering a segment margin on a named award would invent precision. | Named construction awards use `margin: null` (fragile if input-cost convexity probes them). |
| Energy cost share / pass-through | “Energy services” is a **revenue** line inside support services. Pack does not disclose energy as a % of group cost or pass-through. | Optional `energy` section omitted. | `energy_margin` → NOT_TESTED (`optional_section_absent`). Not assumed immaterial beyond “not disclosed”. |
| Fixed monthly cash outflows | Interest & tax £41.3m, pension deficit contributions £46.6m, dividends £82.7m, etc. are annual line items — **no single “fixed monthly outflows” figure**. | `liquidity.fixed_monthly_outflows` left `null`. | `runway` → RED (`fragile_unknown` / missing required field). |
| Individual named supplier shares | Category management and EPF described; no supplier HHI or named % of spend. | Aggregated supplier nodes only. | Concentration metrics run on aggregates; true name-level concentration unknown → residual fragility noted here. |
| Public / private split inside `uk_other_customers` | UK residual after £1bn infrastructure floor mixes private FM and other public FM (Scape, local government, MoD support, Cabinet Office, NIHE, etc.). | `CustomerSpec.public_sector` defaults to `false` when unknown (schema cannot express “unknown”). | Fragile unknown on public-sector share beyond the cited infrastructure floor. **Read-through:** `customer_monoculture` may flag a large `public_sector:false` bucket — that is an encoding artefact of unknown→false, not a pack claim that residual revenue is private. |
| General `supply_shock` WOR | No pack figure for a historical supplier-interruption intensity. | `worst_on_record: null`. | Convexity / distance for that input → NOT_TESTED (missing WOR). |
| `construction_cost_shock` WOR | No cited historical % cost overrun / input-cost spike. | `worst_on_record: null`. | Same — NOT_TESTED for that input. |
| PPP materials-supply edges | PPP revenue includes construction-phase progress and equity returns; no cited split of materials flow into the PPP platform. | `ppp_platform` has outbound edge to `carillion` but no cited inbound supplier edge. | Structural gap recorded; not filled with invented supply. |
| Back-office partner edge share | Partner existence and ~£20m 2016 platform-licence profit cited; **share of supply not disclosed**. | Stub `share: 0.01` / flow 10 only to keep the critical node connected. | Low-confidence stub — see lowest-confidence list in the PR. |
| Drawn vs undrawn on £870m facilities | Bank loans £145.9m used as drawn proxy; AR2015 undrawn was £761.2m (consistent order of magnitude). 2016 undrawn not printed as a single line in the results RNS. | Derived undrawn 724.1. | Medium confidence; if bank loans include items outside the committed facilities, undrawn is misstated → fragile residual. |
| Customer revenue shares for named counterparties | Contract **lifetime** values disclosed (Nationwide £350m / 7y, etc.); **2016 revenue % of group** not disclosed. | Named awards not given positive `revenue_share` (would require inventing annualisation). | Avoids false customer concentration; named awards appear in citations / gaps only. |
| Termination notice / loss exposure | Not disclosed for modelled contracts. | Left `null`. | Unknown. |
| Rating-implied leverage swings | No rating reports in pack. | No leverage covenant stress input with a rating-based WOR. | Fragile unknown. |

## Contracts omitted from `contracts:` (pricing type not disclosed)

These are in the pack and inform customer / order-book structure, but lack a
cited `fixed` / `cost_plus` label:

- Nationwide FM (~£350m / 7y) — `contract-nationwide-2016`
- Centrica FM (~£90m / 5y) — `contract-centrica-2016`
- Openreach framework extension (Carillion share up to £500m / 3y) — `contract-openreach-2017`
- Scape FM framework (up to £1.5bn / 6y, public sector) — `contract-scape-fm-2015`
- MoD Army Basing support-services element (~£215m Carillion share) — `contract-mod-jv-2016`
- Arriva / London Overground FM — fy-results-2016 narrative / `contract-arriva-2015`
- NIHE housing maintenance (up to £366m) — fy-results-2016 narrative
- Cabinet Office (£42m) — fy-results-2016 narrative
- PDO extension (~£240m) — fy-results-2016 narrative
- Other 2015–2017 award RNS in the manifest

Construction-side awards with target-cost / out-turn language are in the model
as `pricing: fixed` with `margin: null` where contract margin is undisclosed.

## Pensions (recorded; no first-class schema section)

| Item | Cited value | Source | Notes |
|---|---|---|---|
| IAS 19 deficit pre-tax | £804.8m | fy-results-2016 p.19 | |
| IAS 19 deficit net of tax | £663.2m | fy-results-2016 | |
| Deficit contributions | £46.6m (2016) | fy-results-2016 | Expected similar in 2017 pending triennial |
| Triennial at 31 Dec 2016 | **Not agreed** | fy-results-2016 | Fragile unknown |

Pensions are not a separate YAML section in `dependency_graph.v1`. Figures are
cited here and in CITATIONS.md; they are not turned into invented covenant
limits or outflows beyond what runway already marks unknown.

## Debt stock outside undrawn facilities

| Instrument | Amount | Source | Model handling |
|---|---|---|---|
| US private placement | £360.8m | fy-results-2016 | Not listed as undrawn facility |
| Convertible bonds | £170.0m | fy-results-2016 | Not listed as undrawn facility |
| Finance leases | £15.6m | fy-results-2016 note 9 | Not modelled as a facility |
| Schuldschein | £112m drawn | schuldschein-refinancing-2017 | Listed with drawn = limit (no undrawn) |

## What this file is not

- Not a comparison with any post-cut-off outcome.
- Not a claim that the company will or will not meet obligations.
- Not permission to fill gaps with industry “typical” ratios.
