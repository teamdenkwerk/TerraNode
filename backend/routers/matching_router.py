"""
backend/routers/matching_router.py

TERRANODE FEATURE 06 — ADVANCED MULTI-SOURCE MATCHING API

Endpoints:
  GET  /api/matching/config
  POST /api/matching/evaluate-pair
  POST /api/matching/batch
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from shapely.geometry import shape

from backend.config.matching_config import (
    AUTHORITATIVE_MATCHING_CONFIG,
    AdvancedMatchingConfig,
)
from matching.advanced_matching import (
    AdvancedMatchingEngine,
    calculate_multi_signal_score,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matching", tags=["matching"])


class EvaluatePairRequest(BaseModel):
    """Payload to evaluate a candidate pair using all 8 signals."""
    geometry_a: Dict[str, Any] = Field(..., description="GeoJSON Polygon/MultiPolygon A")
    geometry_b: Dict[str, Any] = Field(..., description="GeoJSON Polygon/MultiPolygon B")
    attributes_a: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata / properties for source A")
    attributes_b: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metadata / properties for source B")


class BatchMatchingRequest(BaseModel):
    """Payload to run R-tree multi-signal matching across two feature collections."""
    features_a: List[Dict[str, Any]] = Field(..., description="List of GeoJSON Feature objects for dataset A")
    features_b: List[Dict[str, Any]] = Field(..., description="List of GeoJSON Feature objects for dataset B")
    search_radius_meters: Optional[float] = Field(15.0, ge=1.0, le=100.0, description="Spatial search radius in meters")


@router.get("/config")
def get_matching_configuration():
    """
    GET /api/matching/config

    Returns the authoritative, documented weights and classification thresholds.
    Zero arbitrary undocumented weights.
    """
    return AUTHORITATIVE_MATCHING_CONFIG.to_dict()


@router.post("/evaluate-pair")
def evaluate_matching_pair(request: EvaluatePairRequest):
    """
    POST /api/matching/evaluate-pair

    Calculates multi-signal match score across 8 independent dimensions:
    - IoU
    - Centroid drift
    - Area difference & ratio
    - Perimeter difference & ratio
    - Shape similarity (compactness quotient)
    - Bounding-box envelope similarity
    - Source agreement
    - Identifier similarity

    Returns candidate_score, component breakdown, and classification
    (STRONG_MATCH, POSSIBLE_MATCH, WEAK_MATCH, NO_MATCH).
    """
    try:
        geom_a = shape(request.geometry_a)
        geom_b = shape(request.geometry_b)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid GeoJSON geometry provided: {e}",
        )

    score = calculate_multi_signal_score(
        geom_a=geom_a,
        geom_b=geom_b,
        attrs_a=request.attributes_a,
        attrs_b=request.attributes_b,
    )

    return score.to_dict()


@router.post("/batch")
def execute_batch_matching(request: BatchMatchingRequest):
    """
    POST /api/matching/batch

    Executes R-tree (STRtree) candidate generation and multi-signal scoring.
    Avoids O(N^2) comparisons and returns performance/reduction benchmark metrics:
    - total_records
    - candidate_pairs
    - actual_comparisons
    - candidate_reduction_ratio_pct
    - matched_pairs
    - processing_time_ms
    """
    engine = AdvancedMatchingEngine()
    matches, benchmark = engine.match_datasets(
        dataset_a_features=request.features_a,
        dataset_b_features=request.features_b,
        search_radius_m=request.search_radius_meters,
    )

    return {
        "benchmark": benchmark.to_dict(),
        "total_matches_returned": len(matches),
        "matches": [m.to_dict() for m in matches[:500]],  # cap return list for payload efficiency
    }
