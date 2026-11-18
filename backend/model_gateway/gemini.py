"""
Gemini model provider.

Used only when MODEL_PROVIDER=gemini and GEMINI_API_KEY is set.
Requires: pip install google-generativeai

``google.generativeai`` is imported lazily inside ``generate()`` and
``health_check()`` so this module loads even when the package is not
installed.  An ``_client`` parameter can be injected for unit testing
without touching the real API.

Output is always validated against the caller-supplied Pydantic schema.
If Gemini returns malformed JSON the ValidationError propagates to the
worker, which applies the retry + DLQ policy.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Type

from pydantic import BaseModel, ValidationError

from ..shared.logging import get_logger
from ..shared.ports.model_provider import ModelProviderPort

logger = get_logger("model_gateway.gemini")


class GeminiModelProvider(ModelProviderPort):
    """
    Google Gemini model provider.

    Parameters
    ----------
    api_key:
        Gemini API key.  Never logged or included in any output.
    model:
        Model name, e.g. ``"gemini-1.5-flash"``.
    _client:
        Optional pre-built client for testing.  When provided, the lazy
        ``google.generativeai`` import and ``genai.configure()`` call are
        skipped, so no API key validation happens at construction time.
        The injected client must implement ``generate_content_async(prompt)``.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        _client=None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model
        # _client is None → lazily initialised on first call.
        # _client provided → injected stub/mock, no real API calls.
        self._client = _client

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_version(self) -> str:
        return self._model_name

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> BaseModel:
        # ── Lazy import: module loads even without google-generativeai ─────────
        if self._client is None:
            try:
                import google.generativeai as genai  # noqa: PLC0415
            except ImportError as exc:
                raise RuntimeError(
                    "google-generativeai is not installed. "
                    "Run: pip install google-generativeai"
                ) from exc

            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=system_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                },
            )

        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        full_prompt = (
            f"{system_prompt}\n\n"
            f"{user_prompt}\n\n"
            f"Respond with valid JSON conforming exactly to this schema:\n{schema_json}"
        )

        response = await self._client.generate_content_async(full_prompt)
        raw_text = response.text.strip()

        # Strip markdown fences if the model wraps output in ```json … ```
        raw_text = re.sub(r"^```(?:json)?\s*\n?", "", raw_text)
        raw_text = re.sub(r"\n?```\s*$", "", raw_text)

        try:
            parsed = json.loads(raw_text)
            validated = output_schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.error(
                "Gemini output failed schema validation",
                extra={"error": str(exc), "raw_prefix": raw_text[:300]},
            )
            # Re-raise so the assessment service can wrap it in an AssessmentError
            raise

        logger.debug(
            "Gemini output validated",
            extra={"model": self._model_name, "schema": output_schema.__name__},
        )

        return validated

    async def health_check(self) -> bool:
        """Return True if the provider appears functional; False on any error."""
        try:
            import google.generativeai as genai  # noqa: F401,PLC0415  # lazy import
            return bool(self._api_key)
        except ImportError:
            return False
