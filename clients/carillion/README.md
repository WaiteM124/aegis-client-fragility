# Carillion plc — public backtest

Public historical backtest skeleton for Aegis structural-fragility methods.
**No prediction.** The pack finds structural weaknesses that were (or were not)
visible in public evidence at the cut-off; it does not forecast insolvency or
any event.

## Cut-off

- **cut_off_date:** `2017-03-01` (see `client.yaml`)
- Only **public** sources with `publication_date` on or before that date may
  enter `sources/manifest.yaml`.
- Each source must record its publication date. A check fails if any source is
  dated after the cut-off.

## Method freeze (before modelling)

Before any dependency model is built or compared with outcomes:

1. Freeze and **git-tag** the method: metric versions, status thresholds,
   survival floor, and worst-on-record conventions.
2. Build the model **only** from the logged source pack.
3. Treat unknowns as **fragile** (do not invent reassuring structure).
4. **Lock** the fragility map (`maps/`, date-stamped run record + rendered
   output) **before** any comparison with later outcomes. Locked files are
   never edited after creation.

## Results framing

Report **hits**, **misses**, and **false flags** against labelled structural
weaknesses. Do **not** claim prediction, probability, or a blended fragility
score.

## This skeleton

- `client.yaml` — kind `backtest`, classification `public`, cut-off set.
- `sources/manifest.yaml` — empty until public sources are logged.
- `model/` — intentionally empty; **no Carillion model numbers** in this pack yet.
- `maps/` — locked maps go here once a freeze exists.
- `runs/` — local run records (gitignored).
