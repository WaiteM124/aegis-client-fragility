"""
Unit tests for the event normaliser.
"""

import pytest
from datetime import datetime

from backend.event_processing.normaliser import EventNormaliser, _normalise_regions
from backend.shared.models.events import Event


def _make_event(**kwargs) -> Event:
    defaults = dict(
        source="test",
        title="Test event",
        raw_content="Content.",
        event_date=datetime(2026, 11, 1),
    )
    defaults.update(kwargs)
    return Event(**defaults)


class TestEventNormaliser:
    normaliser = EventNormaliser()

    def test_whitespace_cleaned(self):
        event = _make_event(title="  Extra   whitespace   here  ")
        result = self.normaliser.normalise(event)
        assert result.title == "Extra whitespace here"

    def test_summary_extracted(self):
        event = _make_event(
            raw_content="First sentence. Second sentence. Third sentence. Fourth sentence."
        )
        result = self.normaliser.normalise(event)
        assert result.summary
        assert "First sentence" in result.summary
        assert "Fourth sentence" not in result.summary

    def test_regions_normalised(self):
        event = _make_event(affected_regions=["USA", "UK", "Europe"])
        result = self.normaliser.normalise(event)
        assert "north_america" in result.affected_regions
        assert "europe" in result.affected_regions

    def test_location_merged_into_regions(self):
        event = _make_event(location="Middle East", affected_regions=[])
        result = self.normaliser.normalise(event)
        assert "middle_east" in result.affected_regions

    def test_null_bytes_removed(self):
        event = _make_event(raw_content="Content with\x00null byte")
        result = self.normaliser.normalise(event)
        assert "\x00" not in result.raw_content

    def test_id_unchanged(self):
        event = _make_event()
        result = self.normaliser.normalise(event)
        assert result.id == event.id

    def test_original_unchanged(self):
        event = _make_event(title="  Spaces  ")
        _ = self.normaliser.normalise(event)
        assert event.title == "  Spaces  "


class TestNormaliseRegions:
    def test_usa_maps_to_north_america(self):
        assert "north_america" in _normalise_regions(["USA"])

    def test_uk_maps_to_europe(self):
        assert "europe" in _normalise_regions(["UK"])

    def test_unknown_region_snake_cased(self):
        result = _normalise_regions(["South Pacific"])
        assert "south_pacific" in result

    def test_deduplication(self):
        result = _normalise_regions(["USA", "United States", "us"])
        assert result.count("north_america") == 1
