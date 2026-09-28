"""
matching/advanced_matching.py

TERRANODE FEATURE 06 — ADVANCED MULTI-SOURCE MATCHING ENGINE

Extends the R-tree + bounding-box + IoU + centroid matching engine with 8 independent signals:
1. IoU (Intersection-over-Union)
2. Centroid drift distance (projected UTM meters)
3. Area difference & ratio
4. Perimeter difference & ratio
5. Shape similarity (isoperimetric compactness ratio)
6. Bounding-box envelope similarity
7. Source agreement (cross-departmental independence)
8. Identifier similarity (alphanumeric survey numbers/plot IDs)

Guarantees:
- Retains STRtree spatial indexing to avoid O(N²) comparisons.
- Calculates and stores every sub-score transparently.
- Uses strictly documented weights summing to 1.0.
- Classifies each pair as STRONG_MATCH, POSSIBLE_MATCH, WEAK_MATCH, or NO_MATCH.
- Measures candidate reduction ratio and processing time.
- Validated against ground-truth benchmarks.
"""

from __future__ import annotations

import difflib
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from backend.config.matching_config import (
    AUTHORITATIVE_MATCHING_CONFIG,
    AdvancedMatchingConfig,
    MatchClassification,
    MatchingWeightsConfig,
)
from matching.similarity import centroid_distance, iou


# ---------------------------------------------------------------------------
# MATHEMATICAL SIGNAL CALCULATIONS
# ---------------------------------------------------------------------------

def calculate_isoperimetric_quotient(geom: BaseGeometry) -> float:
    """
    Calculates the dimensionless isoperimetric compactness quotient:
    Q = 4 * pi * Area / Perimeter^2
    For a circle, Q = 1.0; for a square, Q = pi / 4 ~ 0.785.
    Degenerate or empty geometries return 0.0.
    """
    if geom is None or geom.is_empty:
        return 0.0
    area = geom.area
    perimeter = geom.length
    if area <= 0.0 or perimeter <= 0.0:
        return 0.0
    quotient = (4.0 * math.pi * area) / (perimeter * perimeter)
    return min(1.0, max(0.0, quotient))


def calculate_shape_similarity(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """
    Measures morphological similarity based on compactness quotient ratio:
    shape_score = min(Q_a, Q_b) / max(Q_a, Q_b)
    Captures indentation and elongation concordance independent of absolute scale.
    """
    if geom_a is None or geom_b is None or geom_a.is_empty or geom_b.is_empty:
        return 0.0
    q_a = calculate_isoperimetric_quotient(geom_a)
    q_b = calculate_isoperimetric_quotient(geom_b)
    if q_a <= 0.0 or q_b <= 0.0:
        return 0.0
    return min(q_a, q_b) / max(q_a, q_b)


def calculate_bbox_similarity(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """
    Computes Intersection-over-Union between the minimum bounding envelopes:
    bbox_score = IoU(envelope_a, envelope_b)
    """
    if geom_a is None or geom_b is None or geom_a.is_empty or geom_b.is_empty:
        return 0.0
    env_a = box(*geom_a.bounds)
    env_b = box(*geom_b.bounds)
    return iou(env_a, env_b)


def normalize_identifier(identifier: Optional[str]) -> str:
    """Normalizes survey/plot numbers: removes punctuation, spaces, converts to lowercase."""
    if not identifier:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", str(identifier).lower())
    # Remove common prefix words like 'plot', 'syno', 'survey', 'no'
    cleaned = re.sub(r"^(syno|surveyno|survey|plotno|plot|sy)", "", cleaned)
    return cleaned


def calculate_identifier_similarity(
    id_a: Optional[str],
    id_b: Optional[str],
) -> Tuple[float, str]:
    """
    Calculates alphanumeric similarity between survey numbers or plot identifiers.
    Returns (score [0.0, 1.0], method_name).

    Heuristics:
    - Missing in one or both: Neutral 0.50 (does not unfairly penalize unlabelled shapes).
    - Exact string match: 1.00
    - Normalized equivalent (e.g. '101/A' vs '101-A'): 0.95
    - Substring containment: 0.85
    - SequenceMatcher token ratio: float in [0.0, 0.80]
    """
    if not id_a or not id_b:
        return 0.50, "NEUTRAL_MISSING"

    raw_a = str(id_a).strip().lower()
    raw_b = str(id_b).strip().lower()

    if raw_a == raw_b:
        return 1.00, "EXACT_MATCH"

    norm_a = normalize_identifier(raw_a)
    norm_b = normalize_identifier(raw_b)

    if norm_a and norm_b:
        if norm_a == norm_b:
            return 0.95, "NORMALIZED_EQUIVALENT"
        if norm_a in norm_b or norm_b in norm_a:
            return 0.85, "SUBSTRING_CONTAINMENT"

    ratio = difflib.SequenceMatcher(None, raw_a, raw_b).ratio()
    scaled_ratio = round(ratio * 0.80, 4)
    return scaled_ratio, "FUZZY_STRING_SIMILARITY"


# ---------------------------------------------------------------------------
# MULTI-SIGNAL MATCH SCORE MODEL
# ---------------------------------------------------------------------------

@dataclass
class MultiSignalMatchScore:
    """
    Fully documented, transparent multi-signal match score breakdown.
    Every single component is explicitly stored and explainable.
    """
    candidate_score: float
    iou_score: float
    centroid_score: float
    area_score: float
    perimeter_score: float
    shape_score: float
    bbox_score: float
    source_agreement_score: float
    identifier_score: float
    classification: MatchClassification
    raw_metrics: Dict[str, Any] = field(default_factory=dict)
    weights_used: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_score": round(self.candidate_score, 4),
            "iou_score": round(self.iou_score, 4),
            "centroid_score": round(self.centroid_score, 4),
            "area_score": round(self.area_score, 4),
            "perimeter_score": round(self.perimeter_score, 4),
            "shape_score": round(self.shape_score, 4),
            "bbox_score": round(self.bbox_score, 4),
            "source_agreement_score": round(self.source_agreement_score, 4),
            "identifier_score": round(self.identifier_score, 4),
            "classification": self.classification.value,
            "raw_metrics": self.raw_metrics,
            "weights_used": self.weights_used,
        }


# ---------------------------------------------------------------------------
# SCORING & CLASSIFICATION LOGIC
# ---------------------------------------------------------------------------

def calculate_multi_signal_score(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    attrs_a: Optional[Dict[str, Any]] = None,
    attrs_b: Optional[Dict[str, Any]] = None,
    config: Optional[AdvancedMatchingConfig] = None,
) -> MultiSignalMatchScore:
    """
    Computes transparent multi-signal match score for a candidate pair.

    Score components:
    1. iou_score: Spatial IoU in [0, 1]
    2. centroid_score: 1.0 - (drift_meters / max_radius) clipped to [0, 1]
    3. area_score: min(A1, A2) / max(A1, A2)
    4. perimeter_score: min(P1, P2) / max(P1, P2)
    5. shape_score: min(Q1, Q2) / max(Q1, Q2)
    6. bbox_score: IoU of bounding envelopes
    7. source_agreement_score: 1.0 if different independent sources, 0.5 otherwise
    8. identifier_score: Alphanumeric survey/plot ID concordance
    """
    cfg = config or AUTHORITATIVE_MATCHING_CONFIG
    w = cfg.weights

    attrs_a = attrs_a or {}
    attrs_b = attrs_b or {}

    # 1. IoU Score
    iou_val = iou(geom_a, geom_b)
    iou_score = iou_val

    # 2. Centroid Drift Score
    drift_m = centroid_distance(geom_a, geom_b)
    if math.isinf(drift_m):
        centroid_score = 0.0
        drift_m_clean = 999.0
    else:
        drift_m_clean = drift_m
        norm_dist = min(drift_m / cfg.max_search_radius_m, 1.0)
        centroid_score = max(0.0, 1.0 - norm_dist)

    # 3. Area Score
    area_a = geom_a.area if geom_a and not geom_a.is_empty else 0.0
    area_b = geom_b.area if geom_b and not geom_b.is_empty else 0.0
    if area_a > 0.0 and area_b > 0.0:
        area_score = min(area_a, area_b) / max(area_a, area_b)
        area_diff_m2 = abs(area_a - area_b)
        area_diff_ratio = area_diff_m2 / max(area_a, area_b)
    else:
        area_score = 0.0
        area_diff_m2 = 0.0
        area_diff_ratio = 1.0

    # 4. Perimeter Score
    perim_a = geom_a.length if geom_a and not geom_a.is_empty else 0.0
    perim_b = geom_b.length if geom_b and not geom_b.is_empty else 0.0
    if perim_a > 0.0 and perim_b > 0.0:
        perim_score = min(perim_a, perim_b) / max(perim_a, perim_b)
        perim_diff_m = abs(perim_a - perim_b)
    else:
        perim_score = 0.0
        perim_diff_m = 0.0

    # 5. Shape Similarity (Isoperimetric Quotient)
    q_a = calculate_isoperimetric_quotient(geom_a)
    q_b = calculate_isoperimetric_quotient(geom_b)
    shape_score = calculate_shape_similarity(geom_a, geom_b)

    # 6. Bounding Box Similarity
    bbox_score = calculate_bbox_similarity(geom_a, geom_b)

    # 7. Source Agreement
    src_a = attrs_a.get("source") or attrs_a.get("source_dataset") or ""
    src_b = attrs_b.get("source") or attrs_b.get("source_dataset") or ""
    if src_a and src_b and src_a != src_b:
        source_agreement_score = 1.00  # Cross-agency corroboration
    elif not src_a or not src_b:
        source_agreement_score = 0.70  # Unknown source attribution
    else:
        source_agreement_score = 0.50  # Same-source intra comparison

    # 8. Identifier Similarity
    id_a = (
        attrs_a.get("survey_no")
        or attrs_a.get("survey_number")
        or attrs_a.get("plot_no")
        or attrs_a.get("parcel_id")
        or attrs_a.get("source_id")
        or attrs_a.get("id")
    )
    id_b = (
        attrs_b.get("survey_no")
        or attrs_b.get("survey_number")
        or attrs_b.get("plot_no")
        or attrs_b.get("parcel_id")
        or attrs_b.get("source_id")
        or attrs_b.get("id")
    )
    id_score, id_method = calculate_identifier_similarity(id_a, id_b)

    # Composite Candidate Score (Weighted Linear Combination)
    candidate_score = (
        w.w_iou * iou_score
        + w.w_centroid * centroid_score
        + w.w_area * area_score
        + w.w_shape * shape_score
        + w.w_perimeter * perim_score
        + w.w_bbox * bbox_score
        + w.w_source_agreement * source_agreement_score
        + w.w_identifier * id_score
    )
    candidate_score = min(1.0, max(0.0, candidate_score))

    # Authoritative Classification
    if (
        candidate_score >= cfg.strong_match_min_score
        and iou_val >= cfg.strong_match_min_iou
        and drift_m_clean < cfg.strong_match_max_drift_m
    ):
        classification = MatchClassification.STRONG_MATCH
    elif (
        candidate_score >= cfg.possible_match_min_score
        and drift_m_clean < cfg.possible_match_max_drift_m
    ):
        classification = MatchClassification.POSSIBLE_MATCH
    elif candidate_score >= cfg.weak_match_min_score and iou_val > 0.05:
        classification = MatchClassification.WEAK_MATCH
    else:
        classification = MatchClassification.NO_MATCH

    raw_metrics = {
        "iou": round(iou_val, 4),
        "centroid_drift_m": round(drift_m_clean, 3),
        "area_a_m2": round(area_a, 2),
        "area_b_m2": round(area_b, 2),
        "area_diff_m2": round(area_diff_m2, 2),
        "area_diff_ratio": round(area_diff_ratio, 4),
        "perimeter_a_m": round(perim_a, 2),
        "perimeter_b_m": round(perim_b, 2),
        "perimeter_diff_m": round(perim_diff_m, 2),
        "shape_compactness_a": round(q_a, 4),
        "shape_compactness_b": round(q_b, 4),
        "bbox_iou": round(bbox_score, 4),
        "identifier_a": str(id_a or ""),
        "identifier_b": str(id_b or ""),
        "identifier_match_method": id_method,
        "source_a": str(src_a),
        "source_b": str(src_b),
    }

    return MultiSignalMatchScore(
        candidate_score=candidate_score,
        iou_score=iou_score,
        centroid_score=centroid_score,
        area_score=area_score,
        perimeter_score=perim_score,
        shape_score=shape_score,
        bbox_score=bbox_score,
        source_agreement_score=source_agreement_score,
        identifier_score=id_score,
        classification=classification,
        raw_metrics=raw_metrics,
        weights_used=w.to_dict(),
    )


# ---------------------------------------------------------------------------
# LARGE-DATASET SPATIAL INDEXING & CANDIDATE REDUCTION ENGINE
# ---------------------------------------------------------------------------

@dataclass
class CandidateMatchRecord:
    """Represents a scored candidate pair matching record."""
    pair_id: str
    feature_id_a: str
    feature_id_b: str
    geometry_a: Dict[str, Any]
    geometry_b: Dict[str, Any]
    attributes_a: Dict[str, Any]
    attributes_b: Dict[str, Any]
    score_breakdown: MultiSignalMatchScore

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "feature_id_a": self.feature_id_a,
            "feature_id_b": self.feature_id_b,
            "attributes_a": self.attributes_a,
            "attributes_b": self.attributes_b,
            "score": self.score_breakdown.to_dict(),
        }


@dataclass
class MatchingBenchmarkResult:
    """
    Performance and reduction metrics proving avoidance of O(N^2) brute-force.
    """
    total_records_dataset_a: int
    total_records_dataset_b: int
    theoretical_brute_force_pairs: int
    spatial_candidate_pairs: int
    actual_comparisons: int
    candidate_reduction_ratio_pct: float
    matched_pairs: int
    strong_matches: int
    possible_matches: int
    weak_matches: int
    no_matches: int
    processing_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records_dataset_a": self.total_records_dataset_a,
            "total_records_dataset_b": self.total_records_dataset_b,
            "theoretical_brute_force_pairs": self.theoretical_brute_force_pairs,
            "spatial_candidate_pairs": self.spatial_candidate_pairs,
            "actual_comparisons": self.actual_comparisons,
            "candidate_reduction_ratio_pct": round(self.candidate_reduction_ratio_pct, 2),
            "matched_pairs": self.matched_pairs,
            "strong_matches": self.strong_matches,
            "possible_matches": self.possible_matches,
            "weak_matches": self.weak_matches,
            "no_matches": self.no_matches,
            "processing_time_ms": round(self.processing_time_ms, 2),
        }


class AdvancedMatchingEngine:
    """
    STRtree spatial index-backed matching engine for multi-source datasets.
    Guarantees:
    - Retains R-tree spatial indexing.
    - Avoids O(N^2) comparisons.
    - Accurately tracks candidate reduction ratio and execution time.
    """

    def __init__(self, config: Optional[AdvancedMatchingConfig] = None):
        self.config = config or AUTHORITATIVE_MATCHING_CONFIG

    def match_datasets(
        self,
        dataset_a_features: List[Dict[str, Any]],
        dataset_b_features: List[Dict[str, Any]],
        search_radius_m: Optional[float] = None,
    ) -> Tuple[List[CandidateMatchRecord], MatchingBenchmarkResult]:
        """
        Executes multi-source candidate generation and scoring using STRtree.
        """
        start_time = time.perf_counter()
        radius = search_radius_m or self.config.max_search_radius_m

        n_a = len(dataset_a_features)
        n_b = len(dataset_b_features)
        theoretical_pairs = n_a * n_b

        if n_a == 0 or n_b == 0:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return [], MatchingBenchmarkResult(
                total_records_dataset_a=n_a,
                total_records_dataset_b=n_b,
                theoretical_brute_force_pairs=theoretical_pairs,
                spatial_candidate_pairs=0,
                actual_comparisons=0,
                candidate_reduction_ratio_pct=100.0,
                matched_pairs=0,
                strong_matches=0,
                possible_matches=0,
                weak_matches=0,
                no_matches=0,
                processing_time_ms=elapsed_ms,
            )

        # Parse geometries for dataset A
        geoms_a = []
        valid_a_indices = []
        for i, feat in enumerate(dataset_a_features):
            geom = feat.get("geometry")
            if geom:
                try:
                    s_geom = shape(geom)
                    if not s_geom.is_empty:
                        geoms_a.append(s_geom)
                        valid_a_indices.append(i)
                except Exception:
                    continue

        if not geoms_a:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return [], MatchingBenchmarkResult(
                total_records_dataset_a=n_a,
                total_records_dataset_b=n_b,
                theoretical_brute_force_pairs=theoretical_pairs,
                spatial_candidate_pairs=0,
                actual_comparisons=0,
                candidate_reduction_ratio_pct=100.0,
                matched_pairs=0,
                strong_matches=0,
                possible_matches=0,
                weak_matches=0,
                no_matches=0,
                processing_time_ms=elapsed_ms,
            )

        # Build STRtree spatial index on Dataset A
        tree = STRtree(geoms_a)

        matched_records: List[CandidateMatchRecord] = []
        seen_pairs: set[Tuple[int, int]] = set()

        strong_count = 0
        possible_count = 0
        weak_count = 0
        no_match_count = 0

        # Query index with buffered Dataset B geometries
        for j, feat_b in enumerate(dataset_b_features):
            geom_b_raw = feat_b.get("geometry")
            if not geom_b_raw:
                continue
            try:
                s_geom_b = shape(geom_b_raw)
                if s_geom_b.is_empty:
                    continue
            except Exception:
                continue

            query_envelope = s_geom_b.buffer(radius)
            candidate_indices_in_geoms_a = tree.query(query_envelope)

            for idx in candidate_indices_in_geoms_a:
                orig_i = valid_a_indices[idx]
                pair_key = (orig_i, j)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                feat_a = dataset_a_features[orig_i]
                s_geom_a = geoms_a[idx]

                attrs_a = feat_a.get("properties", {})
                attrs_b = feat_b.get("properties", {})

                score = calculate_multi_signal_score(
                    geom_a=s_geom_a,
                    geom_b=s_geom_b,
                    attrs_a=attrs_a,
                    attrs_b=attrs_b,
                    config=self.config,
                )

                if score.classification == MatchClassification.STRONG_MATCH:
                    strong_count += 1
                elif score.classification == MatchClassification.POSSIBLE_MATCH:
                    possible_count += 1
                elif score.classification == MatchClassification.WEAK_MATCH:
                    weak_count += 1
                else:
                    no_match_count += 1

                id_a = str(attrs_a.get("id") or attrs_a.get("survey_no") or orig_i)
                id_b = str(attrs_b.get("id") or attrs_b.get("survey_no") or j)
                geom_a_raw = feat_a.get("geometry", {})

                matched_records.append(
                    CandidateMatchRecord(
                        pair_id=f"PAIR-{id_a}-{id_b}",
                        feature_id_a=id_a,
                        feature_id_b=id_b,
                        geometry_a=geom_a_raw,
                        geometry_b=geom_b_raw,
                        attributes_a=attrs_a,
                        attributes_b=attrs_b,
                        score_breakdown=score,
                    )
                )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        candidate_count = len(seen_pairs)
        reduction_ratio = (
            (1.0 - (candidate_count / theoretical_pairs)) * 100.0
            if theoretical_pairs > 0
            else 100.0
        )

        benchmark = MatchingBenchmarkResult(
            total_records_dataset_a=n_a,
            total_records_dataset_b=n_b,
            theoretical_brute_force_pairs=theoretical_pairs,
            spatial_candidate_pairs=candidate_count,
            actual_comparisons=candidate_count,
            candidate_reduction_ratio_pct=max(0.0, reduction_ratio),
            matched_pairs=strong_count + possible_count,
            strong_matches=strong_count,
            possible_matches=possible_count,
            weak_matches=weak_count,
            no_matches=no_match_count,
            processing_time_ms=elapsed_ms,
        )

        # Sort matches by candidate_score descending
        matched_records.sort(key=lambda r: r.score_breakdown.candidate_score, reverse=True)
        return matched_records, benchmark
