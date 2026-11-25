# Carillion plc — public backtest

Public historical backtest for Aegis structural-fragility methods.
**No prediction.** The pack finds structural weaknesses that were (or were not)
visible in public evidence at the cut-off; it does not forecast insolvency or
any event.

## Backtest rules (approved 25 Nov 2026)

1. **Cut-off:** `2017-03-01` (see `client.yaml`). Inclusive — sources dated
   that day are allowed; later dates fail the cut-off check.
2. **Sources:** only **public** pre-cut-off material. Every source is logged in
   `sources/manifest.yaml` with publisher, `publication_date`, and url (and/or
   path). No documents are stored in the repo — URLs and metadata only.
3. **Method freeze:** metric modules, `metrics/thresholds.py`, eval baseline,
   and schemas are frozen and **git-tagged** before modelling. Tag:
   `carillion-method-v1` (created on the merge commit that introduced this
   pack; see [docs/backtests/carillion-method-freeze.md](../../docs/backtests/carillion-method-freeze.md)).
4. **Blind model:** the dependency model is built **only** from this logged
   source pack — no post-cut-off hindsight.
5. **Unknowns as fragile:** missing structure, missing documents, and
   unresolved figures are treated as fragile (do not invent reassuring
   structure). See known gaps below.
6. **Map lock:** lock the fragility map under `maps/` (date-stamped run record
   + rendered output, with `method_tag`) **before** any comparison with later
   outcomes. Locked files are never edited after creation.
7. **Score the method:** report **hits**, **misses**, and **false flags**
   against labelled structural weaknesses.
8. **No prediction claim:** do not claim prediction, probability, or a blended
   fragility score.

## Key finding — 2016 Annual Report excluded

The **2016 Annual Report & Accounts** (Carillion plc, published **29 March
2017**, RNS 9429A) is **after** the cut-off and must not be used. The primary
pre-cut-off financial sources are therefore:

- **2016 Final Results** RNS (`fy-results-2016`, published **1 March 2017** —
  on the cut-off day; allowed)
- **2015 Annual Report & Accounts** (`ar-2015`, published **21 March 2016**)

Companies House group accounts for the year ended 31 December 2016 (filed
12 May 2017) and later 2017 trading / financing / charge filings are also
excluded. See comments in `sources/manifest.yaml`.

## Known gaps (treat as fragile unknowns)

These were not available as agreed public documents on or before the cut-off
(or were not found as public filings). Model them as **unknown / fragile**,
not as reassuring defaults:

- No pre-cut-off **credit-rating reports** in the pack
- No agreed **31 December 2016 triennial pension valuation** (the 1 March 2017
  results state it was not yet agreed)
- No full **facility agreement**, **US private placement**, or **convertible
  bond** instruments as public documents (only RNS summaries and account notes)

## This pack

- `client.yaml` — kind `backtest`, classification `public`, cut-off set.
- `sources/manifest.yaml` — logged public sources (publication_date ≤ cut-off).
- `model/` — intentionally empty until the method is tagged and a blind model
  is built (**no Carillion model numbers** in this commit).
- `maps/` — locked maps go here once a freeze and model exist (`method_tag`
  recorded on lock).
- `runs/` — local run records (gitignored).
