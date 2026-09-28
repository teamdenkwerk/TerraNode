"""
tests/test_policy.py

UNIT TESTS: AUTHORITATIVE RECONCILIATION POLICY & EDGE CASES

Validates exact threshold boundary conditions:
- confidence 69.99 vs 70.0
- confidence 84.99 vs 85.0
- drift 1.99m vs 2.00m
- high confidence with drift >= 2.0m (must CONFLICT)
- duplicate source collisions
"""

import pytest
from backend.config.reconciliation_policy import (
    evaluate_reconciliation,
    compute_confidence_score,
    ReconciliationStatus,
    DecisionResult,
    AUTO_RECONCILE_CONFIDENCE_MIN,
    REVIEW_CONFIDENCE_MIN,
    MAX_CENTROID_DRIFT_METERS,
)


def test_confidence_formula():
    # 0.50 * match + 0.35 * iou + 0.15 * ext
    # 0.50 * 1.0 + 0.35 * 1.0 + 0.15 * 1.0 = 1.0
    assert compute_confidence_score(1.0, 1.0, 1.0) == 1.0
    # 0.50 * 0.8 + 0.35 * 0.8 + 0.15 * 0.8 = 0.8
    assert compute_confidence_score(0.8, 0.8, 0.8) == 0.8
    # 0.50 * 0.0 + 0.35 * 0.0 + 0.15 * 0.0 = 0.0
    assert compute_confidence_score(0.0, 0.0, 0.0) == 0.0


def test_edge_case_confidence_69_99_is_conflict():
    # Confidence 69.99% (< 70%) with low drift (0.5m) MUST be CONFLICT
    res = evaluate_reconciliation(confidence=0.6999, centroid_drift_meters=0.5)
    assert res.status == ReconciliationStatus.CONFLICT
    assert res.is_conflict is True
    assert res.needs_review is True
    assert res.is_auto_reconciled is False


def test_edge_case_confidence_70_00_is_review():
    # Confidence exactly 70.0% with low drift (0.5m) MUST be REVIEW_REQUIRED
    res = evaluate_reconciliation(confidence=0.7000, centroid_drift_meters=0.5)
    assert res.status == ReconciliationStatus.REVIEW_REQUIRED
    assert res.needs_review is True
    assert res.is_conflict is False
    assert res.is_auto_reconciled is False


def test_edge_case_confidence_84_99_is_review():
    # Confidence 84.99% (< 85%) with low drift (1.2m) MUST be REVIEW_REQUIRED
    res = evaluate_reconciliation(confidence=0.8499, centroid_drift_meters=1.2)
    assert res.status == ReconciliationStatus.REVIEW_REQUIRED
    assert res.needs_review is True
    assert res.is_conflict is False
    assert res.is_auto_reconciled is False


def test_edge_case_confidence_85_00_is_auto_reconciled():
    # Confidence exactly 85.0% with drift < 2.0m MUST be AUTO_RECONCILED
    res = evaluate_reconciliation(confidence=0.8500, centroid_drift_meters=1.99)
    assert res.status == ReconciliationStatus.AUTO_RECONCILED
    assert res.is_auto_reconciled is True
    assert res.needs_review is False
    assert res.is_conflict is False


def test_edge_case_drift_1_99m_allows_auto():
    # Drift 1.99m (< 2.0m) with 90% confidence MUST be AUTO_RECONCILED
    res = evaluate_reconciliation(confidence=0.90, centroid_drift_meters=1.99)
    assert res.status == ReconciliationStatus.AUTO_RECONCILED
    assert res.is_auto_reconciled is True


def test_edge_case_drift_2_00m_forces_conflict():
    # Drift exactly 2.00m (>= 2.0m) MUST be CONFLICT even if confidence is 99%
    res = evaluate_reconciliation(confidence=0.99, centroid_drift_meters=2.00)
    assert res.status == ReconciliationStatus.CONFLICT
    assert res.is_conflict is True
    assert res.is_auto_reconciled is False
    assert "exceeds maximum allowable tolerance" in res.reason


def test_edge_case_huge_drift_forces_conflict():
    # Huge drift (15.5m) MUST be CONFLICT
    res = evaluate_reconciliation(confidence=0.95, centroid_drift_meters=15.5)
    assert res.status == ReconciliationStatus.CONFLICT
    assert res.is_conflict is True


def test_edge_case_duplicate_source_collision():
    # Two footprints from the same source collision MUST be flagged
    res = evaluate_reconciliation(confidence=0.92, centroid_drift_meters=0.4, duplicate_source_collision=True)
    assert res.status == ReconciliationStatus.CONFLICT
    assert res.needs_review is True
    assert "Source collision" in res.reason
