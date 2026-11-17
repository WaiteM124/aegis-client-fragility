"""
Rule-based event classifier.

Deterministic keyword matching — no LLM.
Classification is predictable, fully auditable, and versioned.
"""

from __future__ import annotations

from ..shared.logging import get_logger
from ..shared.models.events import (
    Event,
    EventCategory,
    EventClassification,
    EventSeverity,
)

logger = get_logger("classifier")

VERSION = "1.0.0"

# ── Category keyword tables ───────────────────────────────────────────────────

_CATEGORY_KEYWORDS: dict[EventCategory, list[str]] = {
    EventCategory.GEOPOLITICAL: [
        "war", "conflict", "military", "invasion", "coup", "election",
        "government", "diplomatic", "treaty", "territorial", "protest",
        "revolution", "terrorism", "attack", "sanctions", "ceasefire",
        "occupation", "sovereignty", "regime", "parliament",
    ],
    EventCategory.ECONOMIC: [
        "recession", "inflation", "interest rate", "gdp", "trade", "tariff",
        "market crash", "bankruptcy", "currency", "supply chain", "oil price",
        "unemployment", "investment", "stock market", "devaluation",
        "credit rating", "default", "fiscal", "monetary policy",
    ],
    EventCategory.NATURAL_DISASTER: [
        "earthquake", "hurricane", "typhoon", "flood", "wildfire", "tsunami",
        "drought", "volcanic", "storm", "tornado", "cyclone", "eruption",
        "landslide", "avalanche", "blizzard",
    ],
    EventCategory.CYBER: [
        "cyberattack", "ransomware", "data breach", "hacking", "malware",
        "ddos", "vulnerability", "exploit", "phishing", "cyber incident",
        "zero-day", "intrusion", "botnet", "espionage",
    ],
    EventCategory.REGULATORY: [
        "regulation", "legislation", "compliance", "law", "policy", "ruling",
        "enforcement", "fine", "ban", "restriction", "mandate", "directive",
        "statute", "legal", "court", "tribunal",
    ],
    EventCategory.HEALTH: [
        "pandemic", "epidemic", "outbreak", "virus", "disease", "vaccine",
        "public health", "who", "healthcare", "infection", "pathogen",
        "quarantine", "mortality",
    ],
    EventCategory.ENVIRONMENTAL: [
        "climate", "carbon", "emissions", "pollution", "deforestation",
        "environmental", "sustainability", "esg", "net zero", "biodiversity",
        "contamination",
    ],
    EventCategory.SECURITY: [
        "shooting", "explosion", "bombing", "assassination", "hostage",
        "kidnapping", "extremism", "insurgency", "cartel",
    ],
    EventCategory.TECHNOLOGY: [
        "ai", "semiconductor", "chip", "technology", "innovation", "patent",
        "startup", "ipo", "acquisition", "platform", "data centre",
    ],
}

_SEVERITY_KEYWORDS: dict[EventSeverity, list[str]] = {
    EventSeverity.CRITICAL: [
        "war", "invasion", "nuclear", "catastrophic", "mass casualty",
        "systemic collapse", "pandemic", "critical infrastructure",
        "assassination", "coup", "default",
    ],
    EventSeverity.HIGH: [
        "major", "significant", "severe", "serious", "widespread",
        "escalation", "crisis", "emergency", "attack", "sanctions",
        "explosion", "outbreak", "collapse", "devaluation",
    ],
    EventSeverity.MEDIUM: [
        "moderate", "notable", "concerning", "disruption", "tension",
        "uncertainty", "risk", "incident", "protest", "strike",
    ],
}


# ── Classifier ────────────────────────────────────────────────────────────────


class RuleBasedClassifier:
    """Classify an event using keyword frequency over its combined text."""

    VERSION = VERSION

    def classify(self, event: Event) -> EventClassification:
        combined = (
            f"{event.title} {event.summary or ''} {event.raw_content}"
        ).lower()

        category = _classify_category(combined)
        severity = _classify_severity(combined)
        confidence = _estimate_confidence(combined, category)

        classification = EventClassification(
            event_id=event.id,
            category=category,
            severity=severity,
            confidence=confidence,
            classifier_version=self.VERSION,
            rationale=(
                f"Rule-based classifier v{self.VERSION}: "
                f"category={category}, severity={severity}"
            ),
        )

        logger.info(
            "Event classified",
            extra={
                "event_id": event.id,
                "category": category,
                "severity": severity,
                "confidence": confidence,
            },
        )

        return classification


# ── Private helpers ───────────────────────────────────────────────────────────


def _classify_category(text: str) -> EventCategory:
    scores: dict[EventCategory, int] = {}
    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score

    if not scores:
        return EventCategory.UNKNOWN
    return max(scores, key=lambda c: scores[c])


def _classify_severity(text: str) -> EventSeverity:
    for severity in (EventSeverity.CRITICAL, EventSeverity.HIGH, EventSeverity.MEDIUM):
        if any(kw in text for kw in _SEVERITY_KEYWORDS.get(severity, [])):
            return severity
    return EventSeverity.LOW


def _estimate_confidence(text: str, category: EventCategory) -> float:
    if category == EventCategory.UNKNOWN:
        return 0.3
    keywords = _CATEGORY_KEYWORDS.get(category, [])
    matches = sum(1 for kw in keywords if kw in text)
    # Confidence scales with match density; cap at 0.95 to signal imperfection
    raw = min(matches / max(len(keywords), 1), 1.0)
    return round(0.4 + raw * 0.55, 3)
