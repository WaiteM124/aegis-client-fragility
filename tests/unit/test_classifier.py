"""
Unit tests for the rule-based event classifier.
"""

from datetime import datetime

import pytest

from backend.event_processing.classifier import RuleBasedClassifier
from backend.shared.models.events import Event, EventCategory, EventSeverity


def _make_event(title: str, content: str = "") -> Event:
    return Event(
        source="test",
        title=title,
        raw_content=content or title,
        event_date=datetime(2026, 11, 1),
    )


class TestRuleBasedClassifier:
    clf = RuleBasedClassifier()

    def test_geopolitical_category(self):
        event = _make_event(
            "Military conflict escalates at border",
            "Armed forces have crossed the territorial boundary. War declared.",
        )
        cls = self.clf.classify(event)
        assert cls.category == EventCategory.GEOPOLITICAL

    def test_cyber_category(self):
        # Avoid "attack" which is also a GEOPOLITICAL keyword; use cyber-specific terms
        event = _make_event(
            "Ransomware cyber incident hits hospital network",
            "Cyberattack deploys ransomware malware. Zero-day vulnerability exploited. Data breach confirmed.",
        )
        cls = self.clf.classify(event)
        assert cls.category == EventCategory.CYBER

    def test_natural_disaster_category(self):
        event = _make_event(
            "7.8 magnitude earthquake strikes coastal region",
            "Earthquake triggers tsunami warning across Pacific.",
        )
        cls = self.clf.classify(event)
        assert cls.category == EventCategory.NATURAL_DISASTER

    def test_economic_category(self):
        event = _make_event(
            "Central bank raises interest rate amid high inflation",
            "GDP figures disappoint; currency devaluation feared.",
        )
        cls = self.clf.classify(event)
        assert cls.category == EventCategory.ECONOMIC

    def test_unknown_category_on_empty_content(self):
        event = _make_event("xyz abc def ghi jkl mno pqr stu")
        cls = self.clf.classify(event)
        assert cls.category == EventCategory.UNKNOWN
        assert cls.confidence == pytest.approx(0.3)

    def test_critical_severity_on_war(self):
        event = _make_event("War declared; nuclear threat raised")
        cls = self.clf.classify(event)
        assert cls.severity == EventSeverity.CRITICAL

    def test_low_severity_default(self):
        event = _make_event(
            "Minor trade dispute between neighbouring countries",
            "Negotiators exchanged positions at summit.",
        )
        cls = self.clf.classify(event)
        assert cls.severity in (EventSeverity.LOW, EventSeverity.MEDIUM)

    def test_confidence_range(self):
        for title in [
            "Oil sanctions tighten on major producer",
            "Earthquake strikes capital city",
            "Ransomware hits energy grid",
        ]:
            event = _make_event(title)
            cls = self.clf.classify(event)
            assert 0.0 <= cls.confidence <= 1.0

    def test_event_id_carried_through(self):
        event = _make_event("Test event")
        cls = self.clf.classify(event)
        assert cls.event_id == event.id
