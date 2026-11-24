# ADR-007: AI never produces scores

**Date:** 2026-11-22

## Context

LLMs are useful for evidence, graphs, and narrative, but they are not trustworthy producers of authoritative numbers. If the model emits scores, probabilities, or breakpoints, business decisions become untestable and hallucinations can corrupt risk state. Engineering ADR-002 already required schema-validated model output; this ADR states the product boundary for what AI may and may not do.

## Decision

AI **never** produces scores, probabilities, or breakpoints. Those stay in deterministic, tested Python.

AI's role is to:

1. Build **cited** dependency graphs (human-checked before they become authoritative).
2. Map live events onto the graph as stressors.
3. Hypothesise hidden coupling for a human or engine to verify.
4. Draft stress scenarios.
5. Write **cited** briefs.
6. Answer questions by **calling the engine** (metrics / scorers), not by inventing numbers.

## Status

Accepted

## Consequences

- Fragility readings come from `metrics/*/compute` → `MetricResult`. Event impact scores come from `backend/decision_engine/risk_scorer.py` (`RiskScorer`). Neither path accepts LLM-authored numerics.
- Model calls go through `ModelProviderPort` (`backend/shared/ports/model_provider.py`); output must validate against a Pydantic schema or be rejected ([ADR-002](ADR-002-model-provider-abstraction.md)).
- Default local path uses `DeterministicModelProvider`; Gemini is optional. Future graph-building and brief-writing features must keep the same boundary.

## Alternatives rejected

- **LLM-assigned risk scores or status colours** — untestable and non-deterministic.
- **Model-emitted probabilities or ruin breakpoints** — collapses into prediction and cannot be golden-tested as maths.
- **Unvalidated free-text that is parsed for numbers** — same failure mode with extra ambiguity.
