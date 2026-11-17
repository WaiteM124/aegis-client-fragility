# ADR-002: Model Provider Abstraction and Output Validation

**Status:** Accepted  
**Date:** 2026-11-17  
**Checkpoint:** 1

---

## Context

The system uses an AI model to generate impact assessment text. We need to decide:

1. Where the boundary between model output and business logic sits.
2. How to prevent LLM hallucinations from corrupting authoritative business data.
3. How to swap providers (Gemini, Vertex, Gemma) without changing business logic.

## Decision

All model providers implement `ModelProviderPort`. The port's `generate()` method requires a `Type[BaseModel]` (Pydantic schema) as an argument and **must** return a validated instance of that schema. If the model's output cannot be validated, a `ValidationError` is raised — it is never silently accepted.

```
BusinessLogic → ModelProviderPort.generate(prompt, schema) → ValidatedModel
```

The model **never**:
- Determines which clients are affected (that is deterministic keyword matching).
- Assigns a risk score or risk level (that is the `RiskScorer`).
- Makes routing or business decisions.

The model **only**:
- Generates assessment text, key risks, and recommended actions.
- Returns content validated against `AssessmentOutput`.

## Default and optional providers

| Setting | Provider | Requirement |
|---|---|---|
| `MODEL_PROVIDER=deterministic` | `DeterministicModelProvider` | No API key — default |
| `MODEL_PROVIDER=gemini` | `GeminiModelProvider` | `GEMINI_API_KEY` required |
| `MODEL_PROVIDER=vertex` | `VertexModelProvider` | Checkpoint 4 |
| `MODEL_PROVIDER=gemma` | `GemmaModelProvider` | Interface stub — no GPU endpoint |

## Rationale

- Deterministic provider enables a fully testable pipeline with no external dependencies.
- Output schema validation prevents LLM hallucinations from reaching persistence.
- Provider identity (`provider_name`, `model_version`) is stored in every assessment for audit.
- `raw_model_output` is retained verbatim, enabling offline re-scoring.

## Consequences

- Every caller must supply an `output_schema` — the port cannot be used for unstructured generation.
- The `DeterministicModelProvider` currently hardcodes field names matching `AssessmentOutput`. This is acceptable for the PoC; a schema-introspecting version can replace it without changing the port contract.
- Retry and DLQ policy (in the worker) handles `ValidationError` from any provider uniformly.
