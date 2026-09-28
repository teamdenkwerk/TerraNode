"""
backend/config/reconciliation_policy.py

ONE AUTHORITATIVE RECONCILIATION POLICY FOR TERRANODE.

Rules:
- AUTO-RECONCILED:
    confidence >= 0.85 AND centroid_drift < 2.0 meters
- REVIEW REQUIRED:
    confidence >= 0.70 AND confidence < 0.85 AND centroid_drift < 2.0 meters
- CONFLICT:
    confidence < 0.70 OR centroid_drift >= 2.0 meters

Confidence Formula:
    Confidence = 0.50 * Match Score + 0.35 * IoU Agreement + 0.15 * Extraction Score

All modules, APIs, frontend UI components, reports, and tests MUST consume this single policy.
No other file may hardcode or redefine these thresholds or weights.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict


class ReconciliationStatus(str, Enum):
    AUTO_RECONCILED = "auto_reconciled"
    REVIEW_REQUIRED = "review_required"
    CONFLICT = "conflict"


# Authoritative Threshold Constants
AUTO_RECONCILE_CONFIDENCE_MIN: float = 0.85
REVIEW_CONFIDENCE_MIN: float = 0.70
MAX_CENTROID_DRIFT_METERS: float = 2.0

# Authoritative Weights for Confidence Computation (Sum = 1.0)
WEIGHT_MATCH_SCORE: float = 0.50
WEIGHT_IOU_AGREEMENT: float = 0.35
WEIGHT_EXTRACTION_SCORE: float = 0.15

# Default extraction confidence when none is provided
DEFAULT_EXTRACTION_CONFIDENCE: float = 0.50


@dataclass(frozen=True)
class PolicyConfig:
    version: str = "2026.1"
    auto_reconcile_confidence_min: float = AUTO_RECONCILE_CONFIDENCE_MIN
    review_confidence_min: float = REVIEW_CONFIDENCE_MIN
    max_centroid_drift_meters: float = MAX_CENTROID_DRIFT_METERS
    weight_match_score: float = WEIGHT_MATCH_SCORE
    weight_iou_agreement: float = WEIGHT_IOU_AGREEMENT
    weight_extraction_score: float = WEIGHT_EXTRACTION_SCORE
    default_extraction_confidence: float = DEFAULT_EXTRACTION_CONFIDENCE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


AUTHORITATIVE_POLICY = PolicyConfig()


@dataclass(frozen=True)
class DecisionResult:
    status: ReconciliationStatus
    status_label: str
    confidence: float
    centroid_drift_meters: float
    reason: str
    needs_review: bool
    is_conflict: bool
    is_auto_reconciled: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "status_label": self.status_label,
            "confidence": round(self.confidence, 4),
            "centroid_drift_meters": round(self.centroid_drift_meters, 4),
            "reason": self.reason,
            "needs_review": self.needs_review,
            "is_conflict": self.is_conflict,
            "is_auto_reconciled": self.is_auto_reconciled,
        }


def compute_confidence_score(
    match_score: float,
    iou_agreement: float,
    extraction_score: float = DEFAULT_EXTRACTION_CONFIDENCE,
) -> float:
    """
    Authoritative calculation:
    Confidence = 0.50 * match_score + 0.35 * iou_agreement + 0.15 * extraction_score
    Bounded to [0.0, 1.0].
    """
    raw = (
        WEIGHT_MATCH_SCORE * match_score
        + WEIGHT_IOU_AGREEMENT * iou_agreement
        + WEIGHT_EXTRACTION_SCORE * extraction_score
    )
    bounded = max(0.0, min(1.0, raw))
    return round(bounded, 4)


def evaluate_reconciliation(
    confidence: float,
    centroid_drift_meters: float,
    duplicate_source_collision: bool = False,
) -> DecisionResult:
    """
    Authoritative decision tree:
    - If duplicate_source_collision is True: forced to CONFLICT or REVIEW
    - If confidence >= 0.85 AND centroid_drift < 2.0: AUTO_RECONCILED
    - If 0.70 <= confidence < 0.85 AND centroid_drift < 2.0: REVIEW_REQUIRED
    - If confidence < 0.70 OR centroid_drift >= 2.0: CONFLICT
    """
    # Precision rounding for boundary safety (e.g. 69.999 vs 70.00)
    conf = round(float(confidence), 4)
    drift = round(float(centroid_drift_meters), 4)

    if duplicate_source_collision:
        return DecisionResult(
            status=ReconciliationStatus.CONFLICT,
            status_label="Conflict",
            confidence=conf,
            centroid_drift_meters=drift,
            reason="Source collision: Multiple distinct footprints originated from the same primary source.",
            needs_review=True,
            is_conflict=True,
            is_auto_reconciled=False,
        )

    if drift >= MAX_CENTROID_DRIFT_METERS:
        # Centroid drift exceeds tolerance -> automatically CONFLICT regardless of confidence
        return DecisionResult(
            status=ReconciliationStatus.CONFLICT,
            status_label="Conflict",
            confidence=conf,
            centroid_drift_meters=drift,
            reason=f"Spatial drift ({drift:.2f}m) exceeds maximum allowable tolerance ({MAX_CENTROID_DRIFT_METERS:.1f}m).",
            needs_review=True,
            is_conflict=True,
            is_auto_reconciled=False,
        )

    if conf >= AUTO_RECONCILE_CONFIDENCE_MIN:
        return DecisionResult(
            status=ReconciliationStatus.AUTO_RECONCILED,
            status_label="Auto-Reconciled",
            confidence=conf,
            centroid_drift_meters=drift,
            reason=f"High agreement (Confidence {conf*100:.1f}% >= 85%, Centroid Drift {drift:.2f}m < 2.0m).",
            needs_review=False,
            is_conflict=False,
            is_auto_reconciled=True,
        )
    elif conf >= REVIEW_CONFIDENCE_MIN:
        return DecisionResult(
            status=ReconciliationStatus.REVIEW_REQUIRED,
            status_label="Review Required",
            confidence=conf,
            centroid_drift_meters=drift,
            reason=f"Moderate agreement (Confidence {conf*100:.1f}% in [70%, 85%), Centroid Drift {drift:.2f}m < 2.0m). Officer verification recommended.",
            needs_review=True,
            is_conflict=False,
            is_auto_reconciled=False,
        )
    else:
        return DecisionResult(
            status=ReconciliationStatus.CONFLICT,
            status_label="Conflict",
            confidence=conf,
            centroid_drift_meters=drift,
            reason=f"Low confidence (Confidence {conf*100:.1f}% < 70%). Significant inter-source discrepancy.",
            needs_review=True,
            is_conflict=True,
            is_auto_reconciled=False,
        )
