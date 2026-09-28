"""
tests/test_advanced_matching.py

TERRANODE FEATURE 06 — ADVANCED MULTI-SOURCE MATCHING ENGINE TESTS

Comprehensive test suite verifying:
1. Individual mathematical signals:
   - IoU
   - Centroid drift
   - Area difference
   - Perimeter difference
   - Shape similarity (isoperimetric compactness quotient)
   - Bounding-box envelope similarity
   - Source agreement
   - Identifier similarity (exact, normalized, fuzzy, neutral missing)
2. Documented weights and sum-to-one constraint.
3. Classification boundaries: STRONG_MATCH, POSSIBLE_MATCH, WEAK_MATCH, NO_MATCH.
4. STRtree spatial index candidate reduction (avoids O(N^2) brute force).
5. Ground-truth benchmark validation using reference datasets.
6. FastAPI endpoints:
   - GET /api/matching/config
   - POST /api/matching/evaluate-pair
   - POST /api/matching/batch
"""

import json
import math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point, Polygon, box, mapping

from backend.main import app
from backend.config.matching_config import (
    AUTHORITATIVE_MATCHING_CONFIG,
    AdvancedMatchingConfig,
    MatchClassification,
    MatchingWeightsConfig,
)
from matching.advanced_matching import (
    AdvancedMatchingEngine,
    calculate_bbox_similarity,
    calculate_identifier_similarity,
    calculate_isoperimetric_quotient,
    calculate_multi_signal_score,
    calculate_shape_similarity,
)

client = TestClient(app)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
CADASTRAL_FILE = UPLOADS_DIR / "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson"
MUNICIPAL_FILE = UPLOADS_DIR / "85f02bb7-ec7a-4285-ae1f-450c5f9c2768.geojson"


# ---------------------------------------------------------------------------
# 1. INDIVIDUAL MATHEMATICAL SIGNAL TESTS
# ---------------------------------------------------------------------------

def test_isoperimetric_quotient():
    """Validates compactness quotient for circle, square, and elongated rectangle."""
    # Approximate circle with 64 vertices, radius 10m
    circle_pts = [
        (10.0 * math.cos(2 * math.pi * i / 64), 10.0 * math.sin(2 * math.pi * i / 64))
        for i in range(64)
    ]
    circle_poly = Polygon(circle_pts)
    q_circle = calculate_isoperimetric_quotient(circle_poly)
    assert 0.99 <= q_circle <= 1.0  # Circle is maximum theoretical compactness

    # Square: 10m x 10m. Area = 100, Perimeter = 40. Q = 4*pi*100 / 1600 = pi / 4 ~ 0.785
    square_poly = box(0, 0, 10, 10)
    q_square = calculate_isoperimetric_quotient(square_poly)
    assert abs(q_square - (math.pi / 4.0)) < 0.01

    # Elongated strip: 100m x 1m. Area = 100, Perimeter = 202. Q = 4*pi*100 / 40804 ~ 0.0308
    strip_poly = box(0, 0, 100, 1)
    q_strip = calculate_isoperimetric_quotient(strip_poly)
    assert q_strip < 0.05


def test_shape_similarity():
    """Identical shapes have 1.0 similarity regardless of scaling."""
    sq1 = box(0, 0, 10, 10)
    sq2 = box(0, 0, 50, 50)  # scaled square
    assert calculate_shape_similarity(sq1, sq2) == pytest.approx(1.0, rel=1e-3)

    # Square vs elongated strip
    strip = box(0, 0, 100, 1)
    shape_sim = calculate_shape_similarity(sq1, strip)
    assert shape_sim < 0.10


def test_bbox_similarity():
    """Computes minimum bounding box envelope IoU."""
    poly1 = box(0, 0, 10, 10)
    poly2 = box(0, 0, 10, 10)
    assert calculate_bbox_similarity(poly1, poly2) == 1.0

    poly3 = box(5, 0, 15, 10)
    # Envelopes overlap by 5x10 = 50. Union = 15x10 = 150. IoU = 50/150 = 0.333
    assert calculate_bbox_similarity(poly1, poly3) == pytest.approx(1.0 / 3.0, rel=1e-3)


def test_identifier_similarity():
    """Tests exact, normalized, substring, and missing identifier heuristics."""
    # Exact
    score, method = calculate_identifier_similarity("101/A", "101/A")
    assert score == 1.0
    assert method == "EXACT_MATCH"

    # Normalized punctuation
    score, method = calculate_identifier_similarity("Plot-101/A", "plot 101 a")
    assert score >= 0.95
    assert method == "NORMALIZED_EQUIVALENT"

    # Substring
    score, method = calculate_identifier_similarity("101", "101/B")
    assert score == 0.85
    assert method == "SUBSTRING_CONTAINMENT"

    # Neutral missing
    score, method = calculate_identifier_similarity("101", None)
    assert score == 0.50
    assert method == "NEUTRAL_MISSING"


# ---------------------------------------------------------------------------
# 2. DOCUMENTED WEIGHTS CONSTRAINTS
# ---------------------------------------------------------------------------

def test_matching_weights_sum_to_one():
    """Ensures weights strictly sum to 1.0 and rejects arbitrary weights."""
    w = AUTHORITATIVE_MATCHING_CONFIG.weights
    total = sum(w.to_dict().values())
    assert abs(total - 1.0) < 1e-6

    # Attempting arbitrary invalid weights must raise ValueError
    with pytest.raises(ValueError, match="must strictly sum to 1.0"):
        MatchingWeightsConfig(w_iou=0.9, w_centroid=0.5)


# ---------------------------------------------------------------------------
# 3. MULTI-SIGNAL SCORING & CLASSIFICATION TESTS
# ---------------------------------------------------------------------------

def test_strong_match_classification():
    """Identical or nearly identical parcels classify as STRONG_MATCH."""
    poly_a = box(100, 100, 150, 150)
    poly_b = box(100.5, 100.5, 150.5, 150.5)  # 0.707m centroid drift

    score = calculate_multi_signal_score(
        geom_a=poly_a,
        geom_b=poly_b,
        attrs_a={"survey_no": "101/A", "source": "cadastral"},
        attrs_b={"survey_no": "101-A", "source": "municipal"},
    )

    assert score.classification == MatchClassification.STRONG_MATCH
    assert score.candidate_score >= 0.82
    assert score.iou_score > 0.90
    assert score.centroid_score > 0.90
    assert score.area_score > 0.95
    assert score.identifier_score >= 0.95
    assert score.source_agreement_score == 1.00


def test_possible_match_classification():
    """Moderate divergence (e.g. 3m centroid drift, 65% IoU) classifies as POSSIBLE_MATCH."""
    poly_a = box(100, 100, 150, 150)
    poly_b = box(103, 100, 153, 150)  # 3.0m shift

    score = calculate_multi_signal_score(
        geom_a=poly_a,
        geom_b=poly_b,
        attrs_a={"source": "cadastral"},
        attrs_b={"source": "drone"},
    )

    assert score.classification == MatchClassification.POSSIBLE_MATCH
    assert score.candidate_score >= 0.60
    assert score.raw_metrics["centroid_drift_m"] == 3.0


def test_weak_and_no_match_classification():
    """Very small overlap or distant parcels classify as WEAK_MATCH or NO_MATCH."""
    # Weak match: sliver overlap (1m overlap on 50m parcel)
    poly_a = box(0, 0, 50, 50)
    poly_b = box(49, 0, 99, 50)
    score_weak = calculate_multi_signal_score(geom_a=poly_a, geom_b=poly_b)
    assert score_weak.classification in (MatchClassification.WEAK_MATCH, MatchClassification.NO_MATCH)

    # No match: completely disjoint
    poly_distant = box(500, 500, 550, 550)
    score_none = calculate_multi_signal_score(geom_a=poly_a, geom_b=poly_distant)
    assert score_none.classification == MatchClassification.NO_MATCH
    assert score_none.candidate_score < 0.40


# ---------------------------------------------------------------------------
# 4. LARGE-DATASET SPATIAL INDEXING & CANDIDATE REDUCTION BENCHMARK
# ---------------------------------------------------------------------------

def test_rtree_candidate_reduction_avoids_o_n2():
    """
    Simulates a grid of 100 parcels in Dataset A and 100 in Dataset B.
    Brute-force comparisons = 100 * 100 = 10,000 pairs.
    R-tree spatial indexing should reduce candidate comparisons by > 90%.
    """
    features_a = []
    features_b = []

    # 10x10 grid with 50m parcels separated by 20m roads
    for r in range(10):
        for c in range(10):
            x = c * 70.0
            y = r * 70.0
            # Dataset A
            features_a.append({
                "geometry": mapping(box(x, y, x + 50, y + 50)),
                "properties": {"id": f"CAD-{r}-{c}", "survey_no": f"Sy-{r*10+c}", "source": "cadastre"},
            })
            # Dataset B (slight 1.0m shift in X and Y => sqrt(2) = 1.414m drift < 2.0m)
            features_b.append({
                "geometry": mapping(box(x + 1.0, y + 1.0, x + 51.0, y + 51.0)),
                "properties": {"id": f"MUN-{r}-{c}", "survey_no": f"Sy-{r*10+c}", "source": "municipal"},
            })

    engine = AdvancedMatchingEngine()
    matches, benchmark = engine.match_datasets(features_a, features_b, search_radius_m=15.0)

    assert benchmark.total_records_dataset_a == 100
    assert benchmark.total_records_dataset_b == 100
    assert benchmark.theoretical_brute_force_pairs == 10000

    # R-Tree should prune distant candidates: only nearby pairs are checked
    assert benchmark.spatial_candidate_pairs < 500
    assert benchmark.candidate_reduction_ratio_pct > 95.0  # > 95% reduction vs brute force!
    assert benchmark.matched_pairs == 100
    assert benchmark.strong_matches == 100
    assert benchmark.processing_time_ms > 0.0


# ---------------------------------------------------------------------------
# 5. REFERENCE GROUND-TRUTH DATASET VALIDATION
# ---------------------------------------------------------------------------

def test_reference_dataset_multi_signal_matching():
    """
    Validates Feature 06 on the actual demonstration datasets:
    Cadastral (37 features) vs Municipal (38 features).
    """
    assert CADASTRAL_FILE.exists()
    assert MUNICIPAL_FILE.exists()

    with open(CADASTRAL_FILE, "r", encoding="utf-8") as f:
        cad_features = json.load(f)["features"]
    with open(MUNICIPAL_FILE, "r", encoding="utf-8") as f:
        mun_features = json.load(f)["features"]

    # Transform geometries to metric UTM EPSG:32644
    from shapely.geometry import shape, mapping
    from backend.crs.transformer import reproject_geometry
    metric_cad = [
        {
            "geometry": mapping(reproject_geometry(shape(f["geometry"]), "EPSG:4326", "EPSG:32644")),
            "properties": f["properties"],
        }
        for f in cad_features
    ]
    metric_mun = [
        {
            "geometry": mapping(reproject_geometry(shape(f["geometry"]), "EPSG:4326", "EPSG:32644")),
            "properties": f["properties"],
        }
        for f in mun_features
    ]

    engine = AdvancedMatchingEngine()
    matches, benchmark = engine.match_datasets(metric_cad, metric_mun, search_radius_m=15.0)

    assert benchmark.total_records_dataset_a == 37
    assert benchmark.total_records_dataset_b == 38
    assert benchmark.theoretical_brute_force_pairs == 37 * 38  # 1406 pairs
    assert benchmark.candidate_reduction_ratio_pct > 80.0  # 85.4% reduction on tight reference cluster
    assert benchmark.matched_pairs == 37
    assert benchmark.strong_matches >= 30
    first_match = matches[0]
    score = first_match.score_breakdown
    assert score.iou_score >= 0.0
    assert score.centroid_score >= 0.0
    assert score.area_score >= 0.0
    assert score.perimeter_score >= 0.0
    assert score.shape_score >= 0.0
    assert score.bbox_score >= 0.0
    assert score.identifier_score >= 0.0
    assert score.source_agreement_score >= 0.0


# ---------------------------------------------------------------------------
# 6. REST API ENDPOINT TESTS
# ---------------------------------------------------------------------------

def test_api_get_matching_config():
    """GET /api/matching/config returns documented weights and thresholds."""
    res = client.get("/api/matching/config")
    assert res.status_code == 200
    data = res.json()
    assert "weights" in data
    assert "thresholds" in data
    weights = data["weights"]
    assert weights["w_iou"] == 0.30
    assert weights["w_centroid"] == 0.25
    assert sum(weights.values()) == pytest.approx(1.0, rel=1e-5)


def test_api_evaluate_pair():
    """POST /api/matching/evaluate-pair returns complete transparent score."""
    poly_a = mapping(box(0, 0, 10, 10))
    poly_b = mapping(box(0.5, 0.5, 10.5, 10.5))

    res = client.post(
        "/api/matching/evaluate-pair",
        json={
            "geometry_a": poly_a,
            "geometry_b": poly_b,
            "attributes_a": {"survey_no": "101", "source": "cadastral"},
            "attributes_b": {"survey_no": "101", "source": "municipal"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "candidate_score" in body
    assert "iou_score" in body
    assert "centroid_score" in body
    assert "area_score" in body
    assert "shape_score" in body
    assert "classification" in body
    assert body["classification"] == "STRONG_MATCH"
    assert "raw_metrics" in body


def test_api_batch_matching():
    """POST /api/matching/batch executes spatial indexed matching and reduction."""
    poly_a = mapping(box(0, 0, 10, 10))
    poly_b = mapping(box(1, 1, 11, 11))

    res = client.post(
        "/api/matching/batch",
        json={
            "features_a": [{"geometry": poly_a, "properties": {"id": "A1"}}],
            "features_b": [{"geometry": poly_b, "properties": {"id": "B1"}}],
            "search_radius_meters": 15.0,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "benchmark" in body
    assert "matches" in body
    bm = body["benchmark"]
    assert bm["actual_comparisons"] == 1
    assert len(body["matches"]) == 1
