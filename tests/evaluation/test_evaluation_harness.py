"""Evaluation harness: runs all 25 labelled events through the pipeline and validates outputs.

Coverage requirements:
- All 5 event categories present
- All 4 severity levels present
- All 5 clients covered by at least one event
- All classification confidences >= 0.3
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

EVAL_PATH = Path("data/evaluation/events.json")
EVENTS: list[dict] = json.loads(EVAL_PATH.read_text())


# ---------------------------------------------------------------------------
# Classification-only tests (no pipeline needed)
# ---------------------------------------------------------------------------


def test_all_events_classified_correctly():
    """Category and severity must match the labelled expected values for every event."""
    clf = RuleBasedClassifier()
    failures: list[str] = []
    for ed in EVENTS:
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


def test_confidence_above_threshold():
    """Every event's classification confidence must be >= 0.3."""
    clf = RuleBasedClassifier()
    failures: list[str] = []
    for ed in EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        if cls.confidence < 0.3:
            failures.append(
                f"{ed['id']}: confidence {cls.confidence:.3f} < 0.3"
            )
    assert not failures, "\n".join(failures)


def test_coverage():
    """Dataset must cover all 5 categories, all 4 severities, and all 5 clients."""
    assert len(EVENTS) == 25, f"Expected 25 events, got {len(EVENTS)}"

    cats = {e["expected"]["category"] for e in EVENTS}
    required_cats = {"cyber", "economic", "geopolitical", "health", "natural_disaster"}
    missing_cats = required_cats - cats
    assert not missing_cats, f"Missing categories: {missing_cats}"

    sevs = {e["expected"]["severity"] for e in EVENTS}
    required_sevs = {"critical", "high", "medium", "low"}
    missing_sevs = required_sevs - sevs
    assert not missing_sevs, f"Missing severity levels: {missing_sevs}"

    client_ids = {cid for e in EVENTS for cid in e["expected"]["matched_client_ids"]}
    required_clients = {"client-001", "client-002", "client-003", "client-004", "client-005"}
    missing_clients = required_clients - client_ids
    assert not missing_clients, f"Missing clients: {missing_clients}"


# ---------------------------------------------------------------------------
# Full-pipeline tests (require the `pipeline` fixture)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_client_matches_correct(pipeline):
    """Matched client IDs must equal the labelled expected set for every event."""
    clf, svc, _store = pipeline
    failures: list[str] = []
    for ed in EVENTS:
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        actual = sorted(a.client_id for a in assessments)
        expected = ed["expected"]["matched_client_ids"]
        if actual != expected:
            failures.append(
                f"{ed['id']}: expected clients={expected} got={actual}"
            )
    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_risk_scores_in_range(pipeline):
    """Every matched client's overall risk score must fall within [min, max]."""
    clf, svc, store = pipeline
    failures: list[str] = []
    for ed in EVENTS:
        exp = ed["expected"]
        if not exp["matched_client_ids"]:
            continue
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        for a in assessments:
            score_obj = await store.get_risk_score(a.id)
            assert score_obj is not None, f"{ed['id']}: no risk score for {a.client_id}"
            s = score_obj.overall_score
            lo, hi = exp["min_risk_score"], exp["max_risk_score"]
            if not (lo <= s <= hi):
                failures.append(
                    f"{ed['id']}/{a.client_id}: score={s:.2f} not in [{lo}, {hi}]"
                )
    assert not failures, "\n".join(failures)


@pytest.mark.asyncio
async def test_evidence_contains_expected_terms(pipeline):
    """Where specified, expected evidence terms must appear in evidence excerpts."""
    clf, svc, _store = pipeline
    failures: list[str] = []
    for ed in EVENTS:
        terms = ed["expected"].get("evidence_should_contain", [])
        if not terms:
            continue
        e = make_event(ed)
        cls = clf.classify(e)
        assessments = await svc.assess_event(e, cls)
        all_excerpts = " ".join(
            ref.content_excerpt.lower()
            for a in assessments
            for ref in a.evidence_references
        )
        for term in terms:
            if term.lower() not in all_excerpts:
                failures.append(
                    f"{ed['id']}: expected term {term!r} not found in evidence"
                )
    assert not failures, "\n".join(failures)
