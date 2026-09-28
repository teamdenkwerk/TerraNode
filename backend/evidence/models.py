"""
backend/evidence/models.py

TERRANODE ENHANCEMENT 09 — UNIFIED RECONCILIATION EVIDENCE & EXPLAINABILITY

Comprehensive, transparent data model synthesizing all 9 pillars of reconciliation evidence:
1. Source Evidence
2. Geometric Evidence
3. Matching Evidence (8 Signals)
4. Confidence & Policy Thresholds
5. Ground Truth (GNSS RTK / CORS)
6. Historical Evidence & Version Continuity
7. Infrastructure / Utility Overlap
8. Review & State Machine Audit Trail
9. Final Decision & Administrative Attribution
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceEvidenceItem(BaseModel):
    dataset_id: str
    source_name: str
    source_type: str
    source_feature_id: str
    source_date: Optional[str] = None
    verification_status: str = "VERIFIED"
    properties: Dict[str, Any] = Field(default_factory=dict)


class GeometricEvidence(BaseModel):
    iou: float = Field(..., description="Spatial Intersection over Union [0.0, 1.0]")
    centroid_drift_m: float = Field(..., description="Projected metric centroid displacement in meters")
    area_reference_m2: float
    area_candidate_m2: float
    area_difference_m2: float
    area_difference_percentage: float
    perimeter_reference_m: float
    perimeter_candidate_m: float
    perimeter_difference_m: float
    is_valid_geometry: bool = True
    geometry_repair_applied: bool = False
    repair_details: Optional[str] = None


class MatchingEvidence(BaseModel):
    candidate_score: float
    classification: str
    iou_score: float
    centroid_score: float
    area_score: float
    perimeter_score: float
    shape_score: float
    bbox_score: float
    source_agreement_score: float
    identifier_score: float
    weights_used: Dict[str, float]
    raw_metrics: Dict[str, Any]


class ConfidenceEvidence(BaseModel):
    confidence_score: float
    auto_reconcile_threshold: float = 0.85
    review_threshold: float = 0.70
    max_centroid_drift_threshold_m: float = 2.0
    decision: str
    decision_reason: str
    authoritative_rule_applied: str


class GroundTruthEvidence(BaseModel):
    reference_name: str = "Survey of India CORS / GNSS RTK Field Network"
    is_available: bool = False
    status: str = "VERIFIED"
    checkpoint_id: Optional[str] = None
    centroid_drift_m: Optional[float] = None
    within_tolerance: Optional[bool] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class HistoricalEvidenceSummary(BaseModel):
    has_history: bool = False
    total_versions: int = 1
    current_version: int = 1
    previous_version_date: Optional[str] = None
    latest_version_date: Optional[str] = None
    area_change_m2: Optional[float] = None
    boundary_change: Optional[str] = None
    summary_text: str


class InfrastructureEvidenceSummary(BaseModel):
    has_intersections: bool = False
    intersections_detected: int = 0
    categories_checked: int = 0
    road_intersection: Optional[str] = None
    drainage_intersection: Optional[str] = None
    water_line_status: str = "Data Unavailable"
    summary_text: str
    items: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewEvent(BaseModel):
    timestamp: str
    actor: str
    action: str
    state_from: Optional[str] = None
    state_to: Optional[str] = None
    reason: Optional[str] = None


class FinalDecisionCard(BaseModel):
    status: str
    confidence_pct: float
    centroid_drift_m: float
    iou: float
    ground_truth_status: str
    review_requirement: str
    primary_reason: str


class ReconciliationEvidence(BaseModel):
    """
    Unified evidence object explaining every reconciliation decision in TerraNode.
    """
    parcel_uuid: str
    reconciliation_id: str

    # Source Evidence
    source_dataset_ids: List[str]
    source_feature_ids: List[str]
    source_count: int
    sources: List[SourceEvidenceItem]

    # Geometric Evidence
    geometry_evidence: GeometricEvidence

    # Matching Evidence (8 signals)
    matching_evidence: MatchingEvidence

    # Confidence Evidence
    confidence_evidence: ConfidenceEvidence

    # Ground Truth Evidence
    ground_truth_evidence: GroundTruthEvidence

    # Historical Evidence
    historical_evidence: HistoricalEvidenceSummary

    # Infrastructure Evidence
    infrastructure_evidence: InfrastructureEvidenceSummary

    # Review History
    review_status: str
    reviewer: Optional[str] = None
    review_reason: Optional[str] = None
    review_history: List[ReviewEvent] = Field(default_factory=list)

    # Final Decision
    final_decision: FinalDecisionCard

    # Consensus Footprint Metadata
    consensus_method: str = "CADASTRE_LEGAL_BOUNDARY_PRIORITIZATION"
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
