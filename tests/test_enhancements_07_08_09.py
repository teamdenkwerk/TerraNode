"""
tests/test_enhancements_07_08_09.py

Comprehensive test suite for:
- Enhancement 07: Infrastructure / Utility Crossing Intelligence
- Enhancement 08: Historical Ground Truth & Change Evidence
- Enhancement 09: Unified Reconciliation Evidence & Explainability
"""

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box, LineString, Polygon, mapping

from backend.main import app
from backend.infrastructure.service import get_infrastructure_service
from backend.infrastructure.repository import get_infrastructure_repository
from backend.infrastructure.models import InfrastructureType, VerificationStatus
from backend.infrastructure.intersection import evaluate_single_intersection
from backend.infrastructure.models import InfrastructureFeature
from backend.history.service import get_historical_evidence_service
from backend.evidence.service import get_unified_evidence_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. ENHANCEMENT 07: INFRASTRUCTURE INTELLIGENCE TESTS
# ---------------------------------------------------------------------------

def test_infrastructure_repository_loaded():
    """Verify infrastructure repository loads real layers and builds STRtree indexes."""
    repo = get_infrastructure_repository()
    layers = repo.get_layer_metadata()
    assert len(layers) >= 6

    road_layer = next(l for l in layers if l.type == "road")
    assert road_layer.is_available is True
    assert road_layer.feature_count > 0
    assert road_layer.verification_status == "VERIFIED"

    water_layer = next(l for l in layers if l.type == "water")
    assert water_layer.is_available is False
    assert "BWSSB" in water_layer.unavailability_reason


def test_spatial_road_intersection_calculation():
    """Validates metric road intersection calculation in projected UTM coordinates."""
    # 50m x 50m parcel centered at (100, 100)
    parcel_poly = box(77.6380, 12.9760, 77.6385, 12.9765)

    # Road LineString cutting directly across the parcel
    road_line = LineString([(77.6375, 12.9762), (77.6390, 12.9763)])

    feat = InfrastructureFeature(
        infrastructure_id="TEST-RD-01",
        infrastructure_type=InfrastructureType.ROAD,
        source_dataset_id="test_roads",
        source_feature_id="R-1",
        source_name="BBMP Test Roads",
        source_date="2026-01-01",
        geometry=mapping(road_line),
        verification_status=VerificationStatus.VERIFIED,
    )

    res = evaluate_single_intersection(parcel_poly, feat, road_line, projected_crs="EPSG:32643")
    assert res.intersection_exists is True
    assert res.intersection_status in ("Spatial Intersection Detected", "Infrastructure Overlap")
    assert res.intersection_length_m > 30.0  # ~50m width crossing
    assert res.minimum_distance_m == 0.0


def test_spatial_infrastructure_proximity_calculation():
    """Validates distance calculation when infrastructure is nearby but not intersecting."""
    parcel_poly = box(77.6380, 12.9760, 77.6385, 12.9765)

    # Road 15 meters north of the parcel (approx 0.00013 degrees lat)
    road_line_near = LineString([(77.6375, 12.97665), (77.6390, 12.97665)])

    feat = InfrastructureFeature(
        infrastructure_id="TEST-RD-02",
        infrastructure_type=InfrastructureType.ROAD,
        source_dataset_id="test_roads",
        source_feature_id="R-2",
        source_name="BBMP Test Roads",
        source_date="2026-01-01",
        geometry=mapping(road_line_near),
        verification_status=VerificationStatus.VERIFIED,
    )

    res = evaluate_single_intersection(parcel_poly, feat, road_line_near, projected_crs="EPSG:32643")
    assert res.intersection_exists is False
    assert res.intersection_status == "Proximity Detected"
    assert 10.0 <= res.minimum_distance_m <= 25.0


def test_infrastructure_api_endpoints():
    """Tests GET /api/infrastructure/layers and GET /api/infrastructure/features."""
    res_layers = client.get("/api/infrastructure/layers")
    assert res_layers.status_code == 200
    layers = res_layers.json()
    assert len(layers) == 6

    res_features = client.get("/api/infrastructure/features?layer_type=road")
    assert res_features.status_code == 200
    geo = res_features.json()
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) > 0


def test_parcel_infrastructure_intersections_api():
    """Tests GET /api/parcels/{parcel_uuid}/infrastructure-intersections on real Domlur parcel."""
    # Query for BLR-101
    res = client.get("/api/parcels/BLR-101/infrastructure-intersections")
    assert res.status_code == 200
    data = res.json()
    assert "parcel_uuid" in data
    assert "summary" in data
    assert "results" in data
    assert data["execution_time_ms"] > 0.0

    # Must contain road and drainage, plus unavailable water/electricity
    types = [r["infrastructure_type"] for r in data["results"]]
    assert "road" in types
    assert "drainage" in types
    assert "water" in types

    water_res = next(r for r in data["results"] if r["infrastructure_type"] == "water")
    assert water_res["intersection_status"] == "Data Unavailable"


# ---------------------------------------------------------------------------
# 2. ENHANCEMENT 08: HISTORICAL GROUND TRUTH & CHANGE EVIDENCE TESTS
# ---------------------------------------------------------------------------

def test_historical_timeline_endpoint():
    """Tests GET /api/parcels/{parcel_uuid}/timeline."""
    res = client.get("/api/parcels/BLR-101/timeline")
    assert res.status_code == 200
    data = res.json()
    assert data["has_historical_data"] is True
    assert data["total_versions"] >= 2
    assert len(data["timeline"]) >= 2

    # Check that versions have dated sources
    v1 = data["timeline"][0]
    assert v1["version_number"] == 1
    assert "Cadastral" in v1["source_type"]
    assert v1["verification_status"] == "VERIFIED"


def test_historical_version_compare_endpoint():
    """Tests GET /api/parcels/{parcel_uuid}/compare?version_a=1&version_b=3."""
    res = client.get("/api/parcels/BLR-101/compare?version_a=1&version_b=3")
    assert res.status_code == 200
    data = res.json()
    assert "version_a" in data
    assert "version_b" in data
    assert "comparison" in data

    comp = data["comparison"]
    assert "area_change_m2" in comp
    assert "area_change_percentage" in comp
    assert "centroid_shift_m" in comp
    assert "iou" in comp
    assert "boundary_change" in comp
    assert "source_agreement" in comp
    assert comp["iou"] > 0.80


def test_historical_missing_data_handling():
    """Tests missing historical data reporting when a parcel has no history."""
    service = get_historical_evidence_service()
    resp = service.get_timeline("NON_EXISTENT_UUID_999")
    assert resp.has_historical_data is False
    assert "No verified historical dataset available" in resp.message
    assert resp.required_dataset is not None


# ---------------------------------------------------------------------------
# 3. ENHANCEMENT 09: UNIFIED RECONCILIATION EVIDENCE TESTS
# ---------------------------------------------------------------------------

def test_unified_reconciliation_evidence_endpoint():
    """Tests GET /api/parcels/{parcel_uuid}/evidence on BLR-101."""
    res = client.get("/api/parcels/BLR-101/evidence")
    assert res.status_code == 200
    ev = res.json()

    # 1. Source Evidence
    assert "sources" in ev
    assert len(ev["sources"]) > 0
    assert ev["sources"][0]["verification_status"] == "VERIFIED"

    # 2. Geometric Evidence
    geo = ev["geometry_evidence"]
    assert "iou" in geo
    assert "centroid_drift_m" in geo
    assert "area_reference_m2" in geo

    # 3. Matching Evidence (8 signals)
    match_ev = ev["matching_evidence"]
    assert "candidate_score" in match_ev
    assert "classification" in match_ev
    assert "iou_score" in match_ev
    assert "centroid_score" in match_ev
    assert "area_score" in match_ev
    assert "shape_score" in match_ev
    assert "source_agreement_score" in match_ev
    assert "identifier_score" in match_ev

    # 4. Confidence Evidence
    conf_ev = ev["confidence_evidence"]
    assert "confidence_score" in conf_ev
    assert "auto_reconcile_threshold" in conf_ev
    assert "decision" in conf_ev

    # 5. Ground Truth Evidence
    gt_ev = ev["ground_truth_evidence"]
    assert gt_ev["is_available"] is True
    assert gt_ev["status"] == "VERIFIED"
    assert "RTK" in gt_ev["checkpoint_id"]

    # 6. Historical Evidence
    hist_ev = ev["historical_evidence"]
    assert hist_ev["has_history"] is True
    assert hist_ev["total_versions"] >= 2

    # 7. Infrastructure Evidence
    infra_ev = ev["infrastructure_evidence"]
    assert "categories_checked" in infra_ev
    assert infra_ev["categories_checked"] == 6

    # 8. Review History
    assert "review_history" in ev
    assert len(ev["review_history"]) > 0

    # 9. Final Decision Card
    dec_card = ev["final_decision"]
    assert dec_card["status"] in ("AUTO_RECONCILED", "REVIEW_REQUIRED", "CONFLICT_DETECTED")
    assert dec_card["confidence_pct"] > 0.0


def test_reconciliation_evidence_by_id_endpoint():
    """Tests GET /api/reconciliation/{reconciliation_id}/evidence."""
    res = client.get("/api/reconciliation/REC-BLR-101/evidence")
    assert res.status_code == 200
    data = res.json()
    assert "parcel_uuid" in data
    assert "geometry_evidence" in data
