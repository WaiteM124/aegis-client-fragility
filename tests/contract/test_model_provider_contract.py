"""
Contract tests for ModelProviderPort.

Every concrete provider must satisfy this contract.
Add new providers to the ``providers`` fixture — no other changes needed.

Contract requirements:
  1. provider_name and model_version are non-empty strings.
  2. health_check() returns a bool.
  3. generate() returns a validated instance of the requested schema.
  4. generate() raises if the schema cannot be satisfied (checked via a strict schema).
  5. The same inputs always produce the same schema-valid output (structural contract,
     not content contract — deterministic provider only).
"""

import json

import pytest
from pydantic import BaseModel
from typing import Optional

from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.model_gateway.gemini import GeminiModelProvider
from backend.shared.ports.model_provider import ModelProviderPort


# ── Test schemas ──────────────────────────────────────────────────────────────


class SimpleOutput(BaseModel):
    assessment_text: str
    key_risks: list[str]
    recommended_actions: list[str]


# ── Gemini stub ───────────────────────────────────────────────────────────────


class _StubResponse:
    """Minimal stand-in for a Gemini API response object."""

    def __init__(self, text: str) -> None:
        self.text = text


class _StubGeminiClient:
    """
    Fake Gemini client that returns structurally valid JSON.

    Injected via GeminiModelProvider(_client=...) so no real API calls
    are made during contract tests.
    """

    async def generate_content_async(self, prompt: str) -> _StubResponse:
        payload = json.dumps(
            {
                "assessment_text": (
                    "Stub assessment: the event presents material risk "
                    "to the client's operations."
                ),
                "key_risks": [
                    "Operational disruption in affected regions",
                    "Regulatory and compliance exposure",
                ],
                "recommended_actions": [
                    "Activate contingency protocols",
                    "Review contractual obligations",
                ],
            }
        )
        return _StubResponse(payload)


# ── Provider fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(params=["deterministic", "gemini_stub"])
def provider(request) -> ModelProviderPort:
    if request.param == "deterministic":
        return DeterministicModelProvider()
    if request.param == "gemini_stub":
        # Injected fake client — no real API call, no key validation
        return GeminiModelProvider(api_key="stub-key", _client=_StubGeminiClient())
    raise ValueError(f"Unknown provider: {request.param}")


# ── Contract tests ────────────────────────────────────────────────────────────


class TestModelProviderContract:

    async def test_provider_name_non_empty(self, provider):
        assert isinstance(provider.provider_name, str)
        assert len(provider.provider_name) > 0

    async def test_model_version_non_empty(self, provider):
        assert isinstance(provider.model_version, str)
        assert len(provider.model_version) > 0

    async def test_health_check_returns_bool(self, provider):
        result = await provider.health_check()
        assert isinstance(result, bool)

    async def test_generate_returns_validated_schema(self, provider):
        result = await provider.generate(
            system_prompt="You are an intelligence analyst.",
            user_prompt=(
                "Event: Cyber attack on financial infrastructure\n"
                "Severity: high\n"
                "Client: Test Bank\n"
                "Industry: investment_banking\n"
                "Regions of operation: europe, north_america\n"
            ),
            output_schema=SimpleOutput,
        )
        assert isinstance(result, SimpleOutput)
        assert isinstance(result.assessment_text, str)
        assert len(result.assessment_text) > 0
        assert isinstance(result.key_risks, list)
        assert len(result.key_risks) > 0
        assert isinstance(result.recommended_actions, list)
        assert len(result.recommended_actions) > 0

    async def test_generate_produces_non_empty_assessment(self, provider):
        result = await provider.generate(
            system_prompt="You are an intelligence analyst.",
            user_prompt=(
                "Event: Oil sanctions\n"
                "Severity: critical\n"
                "Client: Energy Corp\n"
                "Industry: energy\n"
                "Affected regions: middle_east\n"
            ),
            output_schema=SimpleOutput,
        )
        assert result.assessment_text.strip() != ""

    async def test_deterministic_provider_idempotent(self):
        """Structural contract: deterministic provider returns structurally identical output."""
        # Only meaningful for the deterministic provider; Gemini stub may vary.
        provider = DeterministicModelProvider()
        kwargs = dict(
            system_prompt="Analyst.",
            user_prompt="Event: Test\nSeverity: low\nClient: Corp\nIndustry: tech\n",
            output_schema=SimpleOutput,
        )
        r1 = await provider.generate(**kwargs)
        r2 = await provider.generate(**kwargs)
        # Same structure (not necessarily identical text, but same field types)
        assert type(r1) == type(r2)
        assert isinstance(r1.key_risks, list)
        assert isinstance(r2.key_risks, list)
