"""
Port: AI model provider.

Design principles enforced by this interface:
  1. The provider never makes business decisions.
  2. Output is always validated against a caller-supplied Pydantic schema
     before it leaves this layer.
  3. Business logic receives a typed, validated object — never raw text or
     an unvalidated dict.
  4. Provider identity (name, version) is captured on every call and stored
     in the assessment for audit.

Concrete adapters:
  - DeterministicModelProvider  — rule-based, no API key, default
  - GeminiModelProvider         — Gemini API (requires GEMINI_API_KEY)
  - VertexModelProvider         — Vertex AI (checkpoint 4)
  - GemmaModelProvider          — interface stub, no GPU endpoint yet
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel


class ModelProviderPort(ABC):

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable identifier stored in every assessment, e.g. 'gemini'."""
        ...

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Model version stored in every assessment, e.g. 'gemini-1.5-flash'."""
        ...

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> BaseModel:
        """
        Generate a response and validate it against ``output_schema``.

        Raises ``pydantic.ValidationError`` if the output cannot be validated.
        Never returns unvalidated text to the caller.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable and functional."""
        ...
