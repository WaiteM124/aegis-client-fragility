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

Schemas: `clients/schemas/client.v1.json`, `clients/schemas/sources_manifest.v1.json`.

| kind | Use |
|---|---|
| `example` | Made-up teaching / demo packs (e.g. ChillCo) |
| `backtest` | Historical public case; cut-off enforced on sources |
| `live` | Ongoing client work |

| data_classification | Git |
|---|---|
| `public` / `example` | Sources and models may be committed when appropriate |
| `confidential` | **Never** commit `sources/` or `model/` — real client data belongs in private cloud storage ([ADR-018](../docs/decisions/ADR-018-client-packs-and-confidential-data.md)) |

Run against a pack:

```bash
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store
PYTHONPATH=. python -m metrics.run_all --client chillco --stress-ladder --store --lock
```

Aegis never predicts. No blended fragility score.
