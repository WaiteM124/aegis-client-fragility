"""
Event normaliser.

Pure transformation — no I/O, no external calls.
Cleans text, extracts a summary, and standardises geography tokens.
"""

from __future__ import annotations

import re

from ..shared.logging import get_logger
from ..shared.models.events import Event

logger = get_logger("normaliser")

# Canonical region aliases.  Keys are lowercase; values are snake_case region IDs.
_REGION_ALIASES: dict[str, str] = {
    "usa": "north_america",
    "united states": "north_america",
    "u.s.": "north_america",
    "us": "north_america",
    "uk": "europe",
    "great britain": "europe",
    "united kingdom": "europe",
    "eu": "europe",
    "europe": "europe",
    "eastern europe": "europe",
    "western europe": "europe",
    "china": "asia_pacific",
    "taiwan": "asia_pacific",
    "japan": "asia_pacific",
    "south korea": "asia_pacific",
    "india": "asia_pacific",
    "southeast asia": "asia_pacific",
    "russia": "europe_cis",
    "cis": "europe_cis",
    "middle east": "middle_east",
    "gulf": "middle_east",
    "mena": "middle_east",
    "africa": "africa",
    "sub-saharan africa": "africa",
    "north africa": "africa",
    "latam": "latin_america",
    "latin america": "latin_america",
    "south america": "latin_america",
}


class EventNormaliser:
    """Normalises a raw Event into a cleaned, enriched Event."""

    VERSION = "1.0.0"

    def normalise(self, event: Event) -> Event:
        """Return a new Event with normalised fields; the original is unchanged."""
        normalised = event.model_copy(deep=True)

        normalised.title = _clean_text(event.title)
        normalised.raw_content = _clean_text(event.raw_content)
        normalised.summary = _extract_summary(event.raw_content)
        normalised.affected_regions = _normalise_regions(
            event.affected_regions + ([event.location] if event.location else [])
        )

        logger.debug(
            "Event normalised",
            extra={
                "event_id": event.id,
                "normaliser_version": self.VERSION,
                "regions": normalised.affected_regions,
            },
        )

        return normalised


# ── Helpers ───────────────────────────────────────────────────────────────────


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_summary(content: str, max_sentences: int = 3) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    return " ".join(sentences[:max_sentences])


def _normalise_regions(regions: list[str]) -> list[str]:
    normalised: set[str] = set()
    for region in regions:
        key = region.lower().strip()
        canonical = _REGION_ALIASES.get(key)
        if canonical:
            normalised.add(canonical)
        elif key:
            # Keep unknown regions in snake_case
            normalised.add(re.sub(r"[^a-z0-9]+", "_", key).strip("_"))
    return sorted(normalised)
