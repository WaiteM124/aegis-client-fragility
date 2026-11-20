"""Adversarial evaluation tests.

Each adversarial event targets a specific robustness property:

- adv-001: sub-region 'gulf' normalises to 'middle_east' via GEO_HIERARCHY
- adv-002: synonym 'chip' expands to 'semiconductor'; event.tags updated
- adv-003: 'soil'/'recoil' do NOT match the 'oil' keyword (word-boundary fix)
- adv-004: region 'antarctica' is outside all client geographies → 0 matches
- adv-005: multi-region [asia_pacific, middle_east] triggers all 5 clients
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.event_processing.classifier import RuleBasedClassifier

from .conftest import make_event

# ---------------------------------------------------------------------------
# Load dataset
# ---------------------------------------------------------------------------

ADV_PATH = Path("data/evaluation/adversarial.json")
ADV_EVENTS: list[dict] = json.loads(ADV_PATH.read_text())

HELD_PATH = Path("data/evaluation/held_out.json")
HELD_EVENTS: list[dict] = json.loads(HELD_PATH.read_text())


def _get(eid: str, dataset: list[dict]) -> dict:
    return next(e for e in dataset if e["id"] == eid)


# ---------------------------------------------------------------------------
# Adversarial matching correctness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_false_positives(pipeline):
    """Actual matched clients must equal expected (no extra matches)."""
    clf, svc, _store = pipeline
    failures: list[str] = []
    for ed in ADV_EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        actual = sorted(a.client_id for a in assessments)
        expected = ed["expected"]["matched_client_ids"]
        if actual != expected:
            failures.append(f"{ed['id']}: expected={expected} got={actual}")
    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_no_false_negatives(pipeline):
    """Every expected client must appear in the actual matches."""
    clf, svc, _store = pipeline
    failures: list[str] = []
    for ed in ADV_EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        actual = sorted(a.client_id for a in assessments)
        for cid in ed["expected"]["matched_client_ids"]:
            if cid not in actual:
                failures.append(
                    f"{ed['id']}: expected client {cid!r} missing from actual {actual}"
                )
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# Specific robustness tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gulf_normalises_to_middle_east(pipeline):
    """Events in region 'gulf' must match the same clients as 'middle_east' events."""
    clf, svc, _store = pipeline
    ed = _get("adv-001", ADV_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    actual = sorted(a.client_id for a in assessments)
    assert "client-001" in actual, (
        "client-001 (middle_east geography) must match gulf→middle_east event"
    )
    assert "client-003" in actual, (
        "client-003 (middle_east geography) must match gulf→middle_east event"
    )


@pytest.mark.asyncio
async def test_chip_synonym_expands_to_semiconductor(pipeline):
    """'chip' must be expanded to 'semiconductor' and appear in event.tags."""
    clf, _svc, _store = pipeline
    ed = _get("adv-002", ADV_EVENTS)
    e = make_event(ed)
    clf.classify(e)  # classify() mutates event.tags via synonym expansion
    assert "semiconductor" in e.tags, (
        f"Expected 'semiconductor' in event.tags after classify(); got {e.tags}"
    )


@pytest.mark.asyncio
async def test_soil_does_not_trigger_oil_keyword(pipeline):
    """'soil' and 'recoil' in text must NOT match the 'oil' client keyword."""
    clf, svc, store = pipeline
    ed = _get("adv-003", ADV_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    actual = sorted(a.client_id for a in assessments)
    expected = ed["expected"]["matched_client_ids"]
    assert actual == expected, (
        f"adv-003: expected {expected} (geo-only), got {actual}"
    )
    # Scores for client-001 and client-003 must reflect geo-only matching
    # (no keyword boost from a false 'oil' match)
    for a in assessments:
        if a.client_id in ("client-001", "client-003"):
            score_obj = await store.get_risk_score(a.id)
            assert score_obj is not None
            s = score_obj.overall_score
            hi = ed["expected"]["max_risk_score"]
            assert s <= hi, (
                f"adv-003/{a.client_id}: score {s:.2f} exceeds max {hi}; "
                "may indicate false 'oil' keyword match from 'soil'/'recoil'"
            )


@pytest.mark.asyncio
async def test_no_client_match_for_unsupported_region(pipeline):
    """Events in 'antarctica' are outside all client geographies; zero matches expected."""
    clf, svc, _store = pipeline
    ed = _get("adv-004", ADV_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    assert assessments == [], (
        f"adv-004: expected 0 matches for 'antarctica' region, "
        f"got {[a.client_id for a in assessments]}"
    )


@pytest.mark.asyncio
async def test_multiregion_event_matches_all_clients(pipeline):
    """Events in [asia_pacific, middle_east] must match all 5 clients."""
    clf, svc, _store = pipeline
    ed = _get("adv-005", ADV_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    actual = sorted(a.client_id for a in assessments)
    expected = ["client-001", "client-002", "client-003", "client-004", "client-005"]
    assert actual == expected, (
        f"adv-005: expected all 5 clients, got {actual}"
    )


# ---------------------------------------------------------------------------
# Held-out events: classification and matching
# ---------------------------------------------------------------------------


def test_held_out_classification():
    """Held-out events must classify to their expected category and severity."""
    clf = RuleBasedClassifier()
    failures: list[str] = []
    for ed in HELD_EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        exp = ed["expected"]
        if str(cls.category) != exp["category"]:
            failures.append(
                f"{ed['id']}: category expected={exp['category']!r} got={cls.category!r}"
            )
        if str(cls.severity) != exp["severity"]:
            failures.append(
                f"{ed['id']}: severity expected={exp['severity']!r} got={cls.severity!r}"
            )
    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_held_out_client_matches(pipeline):
    """Held-out events must match their expected client IDs."""
    clf, svc, _store = pipeline
    failures: list[str] = []
    for ed in HELD_EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        actual = sorted(a.client_id for a in assessments)
        expected = ed["expected"]["matched_client_ids"]
        if actual != expected:
            failures.append(
                f"{ed['id']}: expected={expected} got={actual}"
            )
    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_latin_america_normalises_to_north_america(pipeline):
    """Events in 'latin_america' must normalise to 'north_america' and match north_america clients."""
    clf, svc, _store = pipeline
    ed = _get("held-001", HELD_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    actual = sorted(a.client_id for a in assessments)
    # client-001 and client-004 and client-005 all have north_america in their geography
    for cid in ("client-001", "client-004", "client-005"):
        assert cid in actual, (
            f"held-001: {cid} (north_america geography) must match latin_america event "
            f"via GEO_HIERARCHY normalisation; actual matches: {actual}"
        )


@pytest.mark.asyncio
async def test_southeast_asia_normalises_to_asia_pacific(pipeline):
    """Events in 'southeast_asia' must normalise to 'asia_pacific' and match asia_pacific clients."""
    clf, svc, _store = pipeline
    ed = _get("held-002", HELD_EVENTS)
    e = make_event(ed)
    cls = clf.classify(e)
    assessments = await svc.assess_event(e, cls)
    actual = sorted(a.client_id for a in assessments)
    for cid in ("client-002", "client-004", "client-005"):
        assert cid in actual, (
            f"held-002: {cid} (asia_pacific geography) must match southeast_asia event "
            f"via GEO_HIERARCHY normalisation; actual matches: {actual}"
        )
