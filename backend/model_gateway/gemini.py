"""
Gemini model provider.

Used only when MODEL_PROVIDER=gemini and GEMINI_API_KEY is set.
Requires: pip install google-generativeai

Output is always validated against the caller-supplied Pydantic schema.
If Gemini returns malformed JSON the ValidationError propagates to the
worker, which applies the retry + DLQ policy.
"""

from __future__ import annotations

import json
import re
from typing import Type

from pydantic import BaseModel, ValidationError

from ..shared.logging import get_logger
from ..shared.ports.model_provider import ModelProviderPort

logger = get_logger("model_gateway.gemini")


class GeminiModelProvider(ModelProviderPort):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash") -> None:
        self._api_key = api_key
        self._model_name = model
        self._client = None  # lazy-initialised on first call

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
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

        if self._client is None:
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
            f"{user_prompt}\n\n"
            f"Respond with valid JSON conforming exactly to this schema:\n{schema_json}"
        )

        response = await self._client.generate_content_async(full_prompt)
        raw_text = response.text.strip()

        # Strip markdown fences if the model wraps output
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
            raise

        logger.debug(
            "Gemini output validated",
            extra={"model": self._model_name, "schema": output_schema.__name__},
        )

        return validated

    async def health_check(self) -> bool:
        try:
            import google.generativeai as genai  # noqa: F401
            return bool(self._api_key)
        except ImportError:
            return False
