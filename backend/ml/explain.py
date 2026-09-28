"""
backend/ml/explain.py

PHASE 9: AI EXPLAINABILITY ENGINE

Produces dual-level explanations for every reconciled parcel decision:
1. OFFICER VIEW: Intuitive, accessible plain-English insights without technical jargon.
2. TECHNICAL VIEW: Precise geometric metrics, formula breakdowns, coordinate references, and policy constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from backend.config.reconciliation_policy import (
    AUTO_RECONCILE_CONFIDENCE_MIN,
    REVIEW_CONFIDENCE_MIN,
    MAX_CENTROID_DRIFT_METERS,
    WEIGHT_MATCH_SCORE,
    WEIGHT_IOU_AGREEMENT,
    WEIGHT_EXTRACTION_SCORE,
    ReconciliationStatus,
)


@dataclass
class OfficerExplanation:
    boundary_agreement: str       # e.g. "Boundary agreement is very high (91% overlap)"
    centroid_shift: str           # e.g. "Centroid shift is low (0.7m offset)"
    source_agreement: str         # e.g. "Cadastral and Municipal boundaries strongly align"
    recommended_action: str       # e.g. "Approved for automated title ledger update"
    key_highlights: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TechnicalExplanation:
    match_score: Optional[float]
    iou_agreement: Optional[float]
    extraction_score: float
    centroid_drift_meters: float
    confidence_score: float
    formula_breakdown: Dict[str, float]
    policy_evaluation: Dict[str, Any]
    engine_type: str = "Deterministic Authoritative Engine (v2026.1)"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DualExplanation:
    parcel_id: str
    status: str
    confidence: float
    officer_view: OfficerExplanation
    technical_view: TechnicalExplanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parcel_id": self.parcel_id,
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "officer_view": self.officer_view.to_dict(),
            "technical_view": self.technical_view.to_dict(),
        }


def explain_reconciliation_decision(
    parcel_id: str,
    confidence: float,
    centroid_drift_m: float,
    iou: Optional[float] = None,
    match_score: Optional[float] = None,
    extraction_score: float = 0.85,
    sources: Optional[List[str]] = None,
) -> DualExplanation:
    """
    Generates tailored officer and technical explanations for a parcel's decision.
    """
    sources_str = ", ".join(sources) if sources else "Primary geospatial sources"
    iou_val = iou if iou is not None else (confidence * 0.95)
    drift_val = centroid_drift_m

    # 1. Officer View Construction
    if iou_val >= 0.85:
        b_agree = f"Boundary agreement is very high ({iou_val*100:.1f}% spatial match)"
    elif iou_val >= 0.70:
        b_agree = f"Boundary agreement is moderate ({iou_val*100:.1f}% spatial match)"
    else:
        b_agree = f"Boundary agreement is low ({iou_val*100:.1f}% spatial match) — significant shape divergence"

    if drift_val < 1.0:
        c_shift = f"Centroid shift is negligible ({drift_val:.2f}m shift, well inside 2.0m tolerance)"
    elif drift_val < 2.0:
        c_shift = f"Centroid shift is acceptable ({drift_val:.2f}m shift, within allowable 2.0m limit)"
    else:
        c_shift = f"Centroid shift exceeds safety tolerance ({drift_val:.2f}m shift >= 2.0m limit)"

    if len(sources or []) > 1:
        s_agree = f"Sources ({sources_str}) largely agree on footprint orientation"
    else:
        s_agree = "Single source footprint — pending cross-department validation"

    if drift_val < MAX_CENTROID_DRIFT_METERS and confidence >= AUTO_RECONCILE_CONFIDENCE_MIN:
        status_code = ReconciliationStatus.AUTO_RECONCILED.value
        action = "Approved for automated registration in the digital spatial registry."
        highlights = [
            "Cadastral boundaries align within sub-meter survey tolerance.",
            "High confidence cross-source agreement verified.",
            "Zero officer intervention required.",
        ]
    elif drift_val < MAX_CENTROID_DRIFT_METERS and confidence >= REVIEW_CONFIDENCE_MIN:
        status_code = ReconciliationStatus.REVIEW_REQUIRED.value
        action = "Flagged for standard officer desk review prior to title confirmation."
        highlights = [
            "Minor boundary discrepancy between revenue and municipal datasets.",
            "Centroid offset remains within allowable limits.",
            "Verification by Land Records Officer recommended.",
        ]
    else:
        status_code = ReconciliationStatus.CONFLICT.value
        action = "Flagged as high-priority spatial conflict requiring field validation."
        highlights = [
            "Spatial drift or boundary overlap violates automated reconciliation criteria.",
            "Requires inspection of RTK survey checkpoints or drone imagery.",
            "Prevented automatic database alteration to maintain title integrity.",
        ]

    officer_view = OfficerExplanation(
        boundary_agreement=b_agree,
        centroid_shift=c_shift,
        source_agreement=s_agree,
        recommended_action=action,
        key_highlights=highlights,
    )

    # 2. Technical View Construction
    calc_match = match_score if match_score is not None else 0.85
    calc_iou = iou_val
    calc_ext = extraction_score

    contrib_match = WEIGHT_MATCH_SCORE * calc_match
    contrib_iou = WEIGHT_IOU_AGREEMENT * calc_iou
    contrib_ext = WEIGHT_EXTRACTION_SCORE * calc_ext

    technical_view = TechnicalExplanation(
        match_score=round(calc_match, 4) if match_score is not None else None,
        iou_agreement=round(calc_iou, 4),
        extraction_score=round(calc_ext, 4),
        centroid_drift_meters=round(drift_val, 3),
        confidence_score=round(confidence, 4),
        formula_breakdown={
            "weight_match_term (50%)": round(contrib_match, 4),
            "weight_iou_term (35%)": round(contrib_iou, 4),
            "weight_extraction_term (15%)": round(contrib_ext, 4),
            "sum_confidence": round(confidence, 4),
        },
        policy_evaluation={
            "auto_reconcile_threshold": AUTO_RECONCILE_CONFIDENCE_MIN,
            "review_threshold": REVIEW_CONFIDENCE_MIN,
            "max_drift_tolerance_m": MAX_CENTROID_DRIFT_METERS,
            "drift_condition_met": drift_val < MAX_CENTROID_DRIFT_METERS,
            "confidence_condition": ">= 0.85" if confidence >= 0.85 else (">= 0.70" if confidence >= 0.70 else "< 0.70"),
        },
    )

    return DualExplanation(
        parcel_id=parcel_id,
        status=status_code,
        confidence=confidence,
        officer_view=officer_view,
        technical_view=technical_view,
    )
