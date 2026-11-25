# Client packs

Each client has a dedicated folder so evidence, dependency models, locked
fragility maps, and local run history stay separate and traceable.

```
clients/<client_id>/
  client.yaml              # id, display name, kind, data_classification, …
  model/<name>.yaml        # dependency graphs (same schema as metrics examples)
  sources/manifest.yaml    # evidence log (publication dates, urls/paths, sha256)
  maps/                    # locked maps (date-stamped; never edit after create)
  runs/                    # local run records (gitignored)
```

Schemas: `clients/schemas/client.v1.json`, `clients/schemas/sources_manifest.v1.json`,
`clients/schemas/dependency_graph.v1.json` (supply graph + optional financial sections).

| kind | Use |
|---|---|
| `example` | Made-up teaching / demo packs (e.g. ChillCo) |
| `backtest` | Historical public case; cut-off enforced on sources |
| `live` | Ongoing client work |

| data_classification | Git |
|---|---|
| `public` / `example` | Sources and models may be committed when appropriate |
| `confidential` | **Never** commit `sources/` or `model/` — real client data belongs in private cloud storage ([ADR-018](../docs/decisions/ADR-018-client-packs-and-confidential-data.md)) |

### Model format (short example)

Supply-only graphs remain valid. Optional financial sections ([ADR-019](../docs/decisions/ADR-019-financial-side-model.md)):

```yaml
# … nodes / edges …
ruin_line:
  survival_floor: 0.5
liquidity:
  cash_on_hand: 8.0
  fixed_monthly_outflows: 2.5
  committed_facilities:
    - { id: rcf, limit: 10.0, drawn: 4.0 }
  source: { label: "EXAMPLE DATA — placeholder", as_of: "2020-12-31" }
covenants:
  - id: net_debt_ebitda
    kind: max
    metric: net_debt_ebitda
    limit: 3.5
    current: 2.8
    stress_input_id: leverage_shock
    source: { label: "EXAMPLE DATA — placeholder", as_of: "2020-12-31" }
customers:
  - id: mega_retail
    revenue_share: 0.45
    critical: true
    public_sector: false
energy:
  cost_share: 0.12
  pass_through_pct: 0.20
  worst_on_record: 0.35
  source: { label: "EXAMPLE DATA — placeholder", as_of: "2022-08-01" }
```

Customer HHI/SPOF and supplier HHI/SPOF stay **separate labelled results** — never
one blended concentration number. Every swing size needs a cited
`worst_on_record` with source and date. Unknowns are flagged fragile.

Run against a pack:

```bash
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store --lock
```

Aegis never predicts. No blended fragility score.
