"""
backend/config/matching_config.py

TERRANODE FEATURE 06 — CENTRALIZED ADVANCED MATCHING CONFIGURATION

Centralized, mathematically defensible configuration for multi-source candidate matching.
Documented rationale for every component weight and classification threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict


class MatchClassification(str, Enum):
    """Categorical classification of cross-source candidate pair alignment."""
    STRONG_MATCH = "STRONG_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    NO_MATCH = "NO_MATCH"


# ---------------------------------------------------------------------------
# DOCUMENTED WEIGHTS (STRICT SUM = 1.0)
# ---------------------------------------------------------------------------
# Rationale:
# - w_iou (0.30): Primary metric for cadastral parcel overlap agreement.
# - w_centroid (0.25): Centroid proximity directly proves physical geographic identity.
# - w_area (0.12): Area parity under statutory survey tolerance (revenue vs municipal).
# - w_shape (0.10): Isoperimetric compactness ratio captures morphology independent of scale.
# - w_perimeter (0.08): Boundary perimeter length agreement.
# - w_bbox (0.05): Bounding-box envelope alignment and aspect-ratio consistency.
# - w_identifier (0.05): Alphanumeric survey number / plot ID token similarity.
# - w_source_agreement (0.05): Bonus for cross-departmental source divergence.

DEFAULT_WEIGHT_IOU: float = 0.30
DEFAULT_WEIGHT_CENTROID: float = 0.25
DEFAULT_WEIGHT_AREA: float = 0.12
DEFAULT_WEIGHT_SHAPE: float = 0.10
DEFAULT_WEIGHT_PERIMETER: float = 0.08
DEFAULT_WEIGHT_BBOX: float = 0.05
DEFAULT_WEIGHT_IDENTIFIER: float = 0.05
DEFAULT_WEIGHT_SOURCE_AGREEMENT: float = 0.05

# ---------------------------------------------------------------------------
# CLASSIFICATION THRESHOLDS
# ---------------------------------------------------------------------------
STRONG_MATCH_MIN_SCORE: float = 0.82
STRONG_MATCH_MIN_IOU: float = 0.70
STRONG_MATCH_MAX_DRIFT_M: float = 2.0

POSSIBLE_MATCH_MIN_SCORE: float = 0.60
POSSIBLE_MATCH_MAX_DRIFT_M: float = 5.0

WEAK_MATCH_MIN_SCORE: float = 0.40
MAX_SEARCH_RADIUS_METERS: float = 15.0


@dataclass(frozen=True)
class MatchingWeightsConfig:
    """Immutable, validated weights for multi-source candidate scoring."""
    w_iou: float = DEFAULT_WEIGHT_IOU
    w_centroid: float = DEFAULT_WEIGHT_CENTROID
    w_area: float = DEFAULT_WEIGHT_AREA
    w_shape: float = DEFAULT_WEIGHT_SHAPE
    w_perimeter: float = DEFAULT_WEIGHT_PERIMETER
    w_bbox: float = DEFAULT_WEIGHT_BBOX
    w_identifier: float = DEFAULT_WEIGHT_IDENTIFIER
    w_source_agreement: float = DEFAULT_WEIGHT_SOURCE_AGREEMENT

    def __post_init__(self):
        total = (
            self.w_iou
            + self.w_centroid
            + self.w_area
            + self.w_shape
            + self.w_perimeter
            + self.w_bbox
            + self.w_identifier
            + self.w_source_agreement
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Matching weights must strictly sum to 1.0, got {total:.6f}")

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class AdvancedMatchingConfig:
    """Authoritative centralized configuration for the Feature 06 matching engine."""
    version: str = "2026.1"
    weights: MatchingWeightsConfig = MatchingWeightsConfig()
    strong_match_min_score: float = STRONG_MATCH_MIN_SCORE
    strong_match_min_iou: float = STRONG_MATCH_MIN_IOU
    strong_match_max_drift_m: float = STRONG_MATCH_MAX_DRIFT_M
    possible_match_min_score: float = POSSIBLE_MATCH_MIN_SCORE
    possible_match_max_drift_m: float = POSSIBLE_MATCH_MAX_DRIFT_M
    weak_match_min_score: float = WEAK_MATCH_MIN_SCORE
    max_search_radius_m: float = MAX_SEARCH_RADIUS_METERS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "weights": self.weights.to_dict(),
            "thresholds": {
                "strong_match": {
                    "min_composite_score": self.strong_match_min_score,
                    "min_iou": self.strong_match_min_iou,
                    "max_centroid_drift_m": self.strong_match_max_drift_m,
                },
                "possible_match": {
                    "min_composite_score": self.possible_match_min_score,
                    "max_centroid_drift_m": self.possible_match_max_drift_m,
                },
                "weak_match": {
                    "min_composite_score": self.weak_match_min_score,
                },
                "search_radius_m": self.max_search_radius_m,
            },
        }


AUTHORITATIVE_MATCHING_CONFIG = AdvancedMatchingConfig()
