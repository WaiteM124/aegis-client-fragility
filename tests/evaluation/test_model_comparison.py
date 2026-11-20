"""
Model comparison evaluation tests (checkpoint 4, section 7).

Loads the 25-event evaluation dataset and runs both:
  - DeterministicModelProvider  (always available, no API key)
  - GeminiModelProvider with an injected stub client (simulates live Gemini)

Asserts that the stub Gemini provider:
  - Returns structurally valid output for all 25 events.
  - Produces at least 1 key_risk and 1 recommended_action per event.

These tests are marked ``evaluation`` and excluded from the default CI run.
Run with: pytest tests/evaluation/test_model_comparison.py -v -m evaluation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.assessment.service import AssessmentOutput
from backend.model_gateway.deterministic import DeterministicModelProvider
from backend.model_gateway.gemini import GeminiModelProvider

pytestmark = pytest.mark.evaluation

# ── Paths ─────────────────────────────────────────────────────────────────────

_EVAL_DATA = Path(__file__).resolve().parents[2] / "data" / "evaluation" / "events.json"


# ── Gemini stub ───────────────────────────────────────────────────────────────


class _StubGeminiResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _StubGeminiClient:
    """
    Deterministic fake client that always returns a structurally valid
    AssessmentOutput JSON — simulating a live Gemini response.
    """

    async def generate_content_async(self, prompt: str) -> _StubGeminiResponse:
        # Extract event title from the prompt to make responses slightly distinct
        title = "unknown event"
        for line in prompt.splitlines():
            if line.startswith("Event:"):
                title = line[len("Event:"):].strip()
                break

        payload = json.dumps(
            {
                "assessment_text": (
                    f"[Stub Gemini] The event '{title}' presents material considerations "
                    "for the client. Operational continuity and regulatory exposure "
                    "should be reviewed immediately."
                ),
                "key_risks": [
                    f"Primary operational risk from '{title}'",
                    "Supply chain disruption in affected geographies",
                    "Regulatory and compliance exposure",
                ],
                "recommended_actions": [
                    "Activate geographic contingency protocols",
                    "Review contractual obligations and force majeure clauses",
                    "Establish stakeholder communication cadence",
                ],
            }
        )
        return _StubGeminiResponse(payload)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def eval_events() -> list[dict]:
    """Load the 25-event evaluation dataset."""
    assert _EVAL_DATA.exists(), f"Evaluation data not found at {_EVAL_DATA}"
    with _EVAL_DATA.open() as f:
        data = json.load(f)
    assert len(data) >= 25, f"Expected at least 25 evaluation events, found {len(data)}"
    return data


@pytest.fixture(scope="module")
def deterministic_provider() -> DeterministicModelProvider:
    return DeterministicModelProvider()


@pytest.fixture(scope="module")
def gemini_stub_provider() -> GeminiModelProvider:
    return GeminiModelProvider(api_key="stub-key", _client=_StubGeminiClient())


# ── Helper ────────────────────────────────────────────────────────────────────


async def _run_provider(provider, event_title: str, severity: str) -> AssessmentOutput:
    """Run the provider for a single evaluation event and return validated output."""
    result = await provider.generate(
        system_prompt="You are an intelligence analyst. Assess impact on the client.",
        user_prompt=(
            f"Event: {event_title}\n"
            f"Severity: {severity}\n"
            f"Client: Evaluation Corp\n"
            f"Industry: energy\n"
            f"Regions of operation: global\n"
        ),
        output_schema=AssessmentOutput,
    )
    return result


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_deterministic_all_25_events_produce_valid_output(
    eval_events, deterministic_provider
):
    """DeterministicModelProvider produces valid AssessmentOutput for all 25 events."""
    failures = []
    for ev in eval_events[:25]:
        try:
            result = await _run_provider(
                deterministic_provider,
                ev["title"],
                ev.get("expected", {}).get("severity", "medium"),
            )
            assert isinstance(result, AssessmentOutput)
            assert len(result.assessment_text) > 0
            assert len(result.key_risks) >= 1
            assert len(result.recommended_actions) >= 1
        except Exception as exc:
            failures.append(f"Event {ev.get('id', '?')}: {exc}")

    assert not failures, "Deterministic provider failed on events:\n" + "\n".join(failures)


async def test_gemini_stub_all_25_events_produce_valid_output(
    eval_events, gemini_stub_provider
):
    """Stub Gemini provider produces valid AssessmentOutput for all 25 events."""
    failures = []
    for ev in eval_events[:25]:
        try:
            result = await _run_provider(
                gemini_stub_provider,
                ev["title"],
                ev.get("expected", {}).get("severity", "medium"),
            )
            assert isinstance(result, AssessmentOutput)
            assert len(result.key_risks) >= 1, (
                f"Event {ev['id']}: stub Gemini must produce >= 1 key_risk"
            )
            assert len(result.recommended_actions) >= 1, (
                f"Event {ev['id']}: stub Gemini must produce >= 1 recommended_action"
            )
        except Exception as exc:
            failures.append(f"Event {ev.get('id', '?')}: {exc}")

    assert not failures, "Stub Gemini provider failed on events:\n" + "\n".join(failures)


async def test_gemini_stub_returns_non_empty_assessment_text(
    eval_events, gemini_stub_provider
):
    """Stub Gemini provider returns non-empty assessment text for the first event."""
    ev = eval_events[0]
    result = await _run_provider(
        gemini_stub_provider,
        ev["title"],
        ev.get("expected", {}).get("severity", "medium"),
    )
    assert result.assessment_text.strip() != "", (
        "Stub Gemini must produce non-empty assessment_text"
    )


async def test_provider_names_are_distinct(deterministic_provider, gemini_stub_provider):
    """The two providers have different provider_name values."""
    assert deterministic_provider.provider_name != gemini_stub_provider.provider_name
    assert deterministic_provider.provider_name == "deterministic"
    assert gemini_stub_provider.provider_name == "gemini"
