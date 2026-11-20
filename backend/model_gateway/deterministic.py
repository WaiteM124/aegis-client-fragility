"""
Deterministic model provider.

Default for local development and CI.  Requires no API key.
Produces structured output by parsing the user prompt and filling
the requested schema fields with rule-generated text.

This provider exists to:
  1. Let the full pipeline run end-to-end without any external dependency.
  2. Serve as a reference for how the model provider interface works.
  3. Act as the fallback when no API key is configured.

The output conforms to whatever schema is requested; it introspects
the schema fields to build a valid response.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..shared.logging import get_logger
from ..shared.ports.model_provider import ModelProviderPort

logger = get_logger("model_gateway.deterministic")


class DeterministicModelProvider(ModelProviderPort):
    PROVIDER_NAME = "deterministic"
    MODEL_VERSION = "rules-v1"

    @property
    def provider_name(self) -> str:
        return self.PROVIDER_NAME

    @property
    def model_version(self) -> str:
        return self.MODEL_VERSION

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> BaseModel:
        """
        Extract signals from the prompt and populate the schema fields
        with rule-generated text.
        """
        ctx = _parse_prompt(user_prompt)

        # Build field values keyed to AssessmentOutput's known structure.
        # For unknown schemas, fill string fields generically.
        fields = output_schema.model_fields
        kwargs: dict = {}

        for field_name, field_info in fields.items():
            annotation = field_info.annotation
            # Resolve Optional / list annotations
            origin = getattr(annotation, "__origin__", None)

            if origin is list:
                kwargs[field_name] = _generate_list(field_name, ctx)
            else:
                kwargs[field_name] = _generate_text(field_name, ctx)

        validated = output_schema(**kwargs)

        logger.debug(
            "Deterministic output generated",
            extra={"schema": output_schema.__name__, "event": ctx.get("event_title", "")},
        )

        return validated

    async def health_check(self) -> bool:
        return True


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_prompt(prompt: str) -> dict:
    """Extract named fields from the structured user prompt."""
    ctx: dict = {}
    for label, key in [
        ("Event:", "event_title"),
        ("Category:", "category"),
        ("Severity:", "severity"),
        ("Client:", "client_name"),
        ("Industry:", "industry"),
        ("Regions of operation:", "regions"),
        ("Affected regions:", "affected_regions"),
        ("Affected project:", "project"),
    ]:
        for line in prompt.splitlines():
            if line.startswith(label):
                ctx[key] = line[len(label):].strip()
                break
    return ctx


def _generate_text(field_name: str, ctx: dict) -> str:
    event = ctx.get("event_title", "the event")
    client = ctx.get("client_name", "the client")
    severity = ctx.get("severity", "unknown")
    industry = ctx.get("industry", "")
    regions = ctx.get("affected_regions") or ctx.get("regions", "affected regions")

    templates: dict[str, str] = {
        "assessment_text": (
            f"The {severity}-severity event '{event}' presents material considerations "
            f"for {client}. Based on the event profile and available evidence, "
            f"operational continuity, supply chain dependencies, and regulatory exposure "
            f"should be reviewed. Situational monitoring at {severity} escalation threshold "
            f"is recommended. This assessment reflects event classification and client "
            f"profile matching as of ingestion time."
        ),
    }

    return templates.get(
        field_name,
        f"Assessment for '{event}' in context of {industry} operations across {regions}.",
    )


def _generate_list(field_name: str, ctx: dict) -> list[str]:
    event = ctx.get("event_title", "the event")
    regions = ctx.get("affected_regions") or ctx.get("regions", "affected regions")
    severity = ctx.get("severity", "unknown")

    lists: dict[str, list[str]] = {
        "key_risks": [
            f"Operational disruption linked to '{event}' in {regions}",
            "Supply chain or partner exposure in affected geographies",
            f"Regulatory or compliance implications following {severity}-severity event",
            "Reputational or stakeholder communication risk",
        ],
        "recommended_actions": [
            "Activate geographic contingency protocols",
            "Review contractual obligations and force majeure clauses",
            "Establish stakeholder communication cadence",
            f"Monitor situation at {severity}-level escalation threshold",
            "Assess counterparty and supplier exposure in affected regions",
        ],
    }

    return lists.get(field_name, [f"Item related to {event}"])
