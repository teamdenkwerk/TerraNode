"""
tests/test_crs_intelligence.py

Comprehensive test suite for TERRANODE FEATURE 02: LEGACY CRS INTELLIGENCE.
Verifies:
1. Valid EPSG declarations (geographic & projected)
2. Missing CRS metadata (Indian geographic degree extents & projected fallback)
3. Invalid / unparseable CRS declarations
4. Coordinate-range mismatches (declared projected vs degree coords, declared degree vs metric coords)
5. Geographic CRS classification & unit deduction
6. Projected CRS classification & UTM processing CRS calculation
7. Safe geometry reprojection using PyProj
8. API Integration: GET /api/datasets/{id}/crs-report & POST /api/datasets/{id}/crs-confirm
"""

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Polygon, mapping

from backend.main import app
from backend.geospatial.crs_intelligence import (
    LegacyCRSIntelligence,
    CRSDetectionMethod,
    TransformationStatus,
    VERIFIED_CRS_DEFINITIONS,
)


@pytest.fixture
def crs_service():
    return LegacyCRSIntelligence()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# TEST 1: VALID EPSG DECLARATIONS
# ---------------------------------------------------------------------------

def test_valid_geographic_epsg(crs_service):
    """Verifies authoritative resolution of valid EPSG:4326 with degree coordinates."""
    sample_coords = [(77.638, 12.976), (77.643, 12.980), (77.640, 12.978)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-geo-valid",
        declared_crs="EPSG:4326",
        sample_coords=sample_coords,
    )

    assert report.detected_crs == "EPSG:4326"
    assert report.crs_confidence == 1.0
    assert report.crs_detection_method == CRSDetectionMethod.DECLARED_AUTHORITATIVE
    assert report.coordinate_range.units == "degrees"
    assert report.coordinate_range.is_geographic is True
    assert report.coordinate_range.is_projected is False
    assert report.requires_confirmation is False
    assert report.transformation_status == TransformationStatus.READY
    assert len(report.inconsistencies) == 0


def test_valid_projected_epsg(crs_service):
    """Verifies authoritative resolution of valid EPSG:32643 with metric UTM coordinates."""
    sample_coords = [(780100.0, 1435200.0), (780250.0, 1435350.0), (780150.0, 1435100.0)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-proj-valid",
        declared_crs="EPSG:32643",
        sample_coords=sample_coords,
    )

    assert report.detected_crs == "EPSG:32643"
    assert report.crs_confidence == 1.0
    assert report.crs_detection_method == CRSDetectionMethod.DECLARED_AUTHORITATIVE
    assert report.coordinate_range.units == "meters"
    assert report.coordinate_range.is_geographic is False
    assert report.coordinate_range.is_projected is True
    assert report.requires_confirmation is False
    assert report.processing_crs == "EPSG:32643"
    assert len(report.inconsistencies) == 0


# ---------------------------------------------------------------------------
# TEST 2: MISSING CRS METADATA
# ---------------------------------------------------------------------------

def test_missing_crs_indian_geographic_extent(crs_service):
    """
    Verifies that missing CRS with coordinates in Indian bounds (68-98 E, 6-38 N)
    is diagnosed as EPSG:4326 with 0.95 confidence and documented warning.
    """
    # Coordinates in Bengaluru area (77.6, 12.9)
    sample_coords = [(77.640, 12.978), (77.645, 12.982), (77.642, 12.979)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-missing-crs",
        declared_crs=None,
        sample_coords=sample_coords,
    )

    assert report.detected_crs == "EPSG:4326"
    assert report.crs_confidence >= 0.90
    assert report.crs_detection_method == CRSDetectionMethod.COORDINATE_EXTENT_ANALYSIS
    assert report.coordinate_range.is_geographic is True
    assert any("Missing CRS metadata" in w for w in report.warnings)
    # Processing CRS should be automatically selected UTM zone for 77.64 E -> EPSG:32643
    assert report.processing_crs == "EPSG:32643"


def test_missing_crs_projected_uncertainty_guardrail(crs_service):
    """
    CRITICAL GUARDRAIL: When coordinates are projected meters but no CRS or AOI
    is declared, confidence MUST NOT exceed 0.75 and confirmation MUST be required.
    """
    sample_coords = [(780100.0, 1435200.0), (780250.0, 1435350.0)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-missing-proj",
        declared_crs=None,
        sample_coords=sample_coords,
        aoi_metadata=None,
    )

    assert report.crs_confidence < 0.75
    assert report.requires_confirmation is True
    assert report.transformation_status == TransformationStatus.REQUIRES_CONFIRMATION
    assert len(report.suggested_crs_options) >= 3
    # Check that common Indian UTM zones are offered
    suggested_codes = [opt["crs"] for opt in report.suggested_crs_options]
    assert "EPSG:32643" in suggested_codes
    assert "EPSG:32644" in suggested_codes


# ---------------------------------------------------------------------------
# TEST 3: INVALID / UNRECOGNIZED CRS
# ---------------------------------------------------------------------------

def test_invalid_epsg_code(crs_service):
    """Verifies that unparseable/bogus EPSG definitions are flagged as anomalies."""
    sample_coords = [(77.640, 12.978), (77.645, 12.982)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-invalid-crs",
        declared_crs="EPSG:999999",
        sample_coords=sample_coords,
    )

    assert report.requires_confirmation is True
    assert any("Invalid CRS declaration" in inc for inc in report.inconsistencies)
    assert any("Unrecognized CRS" in w for w in report.warnings)
    assert report.detected_crs == "EPSG:4326"


# ---------------------------------------------------------------------------
# TEST 4: COORDINATE-RANGE MISMATCH (ANOMALY DETECTION)
# ---------------------------------------------------------------------------

def test_mismatch_declared_projected_with_degree_coordinates(crs_service):
    """
    CRITICAL ANOMALY: Dataset metadata declares projected CRS (e.g. UTM zone 43N),
    but the actual geometry coordinates are in geographic angular degrees (e.g. 77.64, 12.97).
    Must flag inconsistency and mandate human review before silent corruption.
    """
    sample_coords = [(77.6408, 12.9784), (77.6415, 12.9790), (77.6420, 12.9775)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-mismatch-deg",
        declared_crs="EPSG:32643",  # Declared projected metric!
        sample_coords=sample_coords,  # But coords are degrees!
    )

    assert any("Coordinate-range mismatch" in inc for inc in report.inconsistencies)
    assert report.requires_confirmation is True
    assert report.transformation_status == TransformationStatus.REQUIRES_CONFIRMATION
    assert report.detected_crs == "EPSG:4326"
    assert report.original_crs == "EPSG:32643"
    assert len(report.suggested_crs_options) > 0


def test_mismatch_declared_geographic_with_projected_coordinates(crs_service):
    """
    CRITICAL ANOMALY: Dataset metadata declares EPSG:4326 (degrees),
    but coordinates exceed 180 (e.g. 780,000 Easting).
    Must flag inconsistency and warn officer.
    """
    sample_coords = [(780100.0, 1435200.0), (780250.0, 1435350.0)]
    report = crs_service.diagnose_and_report(
        dataset_id="test-mismatch-metric",
        declared_crs="EPSG:4326",  # Declared degrees!
        sample_coords=sample_coords,  # But coords are metric meters!
    )

    assert any("Coordinate-range mismatch" in inc for inc in report.inconsistencies)
    assert report.requires_confirmation is True
    assert report.transformation_status == TransformationStatus.REQUIRES_CONFIRMATION


# ---------------------------------------------------------------------------
# TEST 5: GEOGRAPHIC VS PROJECTED PROPERTIES & UNITS
# ---------------------------------------------------------------------------

def test_coordinate_range_geographic_classification(crs_service):
    """Verifies strict range bounding for geographic degree coordinates."""
    coords = [(72.85, 19.11), (72.86, 19.12), (72.87, 19.10)]
    cr = crs_service.inspect_coordinate_range(coords)

    assert cr.units == "degrees"
    assert cr.is_geographic is True
    assert cr.is_projected is False
    assert cr.sample_count == 3
    assert cr.min_x == 72.85
    assert cr.max_y == 19.12


def test_coordinate_range_projected_classification(crs_service):
    """Verifies strict range bounding for metric projected coordinates."""
    coords = [(270000.0, 2115000.0), (270500.0, 2115500.0)]
    cr = crs_service.inspect_coordinate_range(coords)

    assert cr.units == "meters"
    assert cr.is_geographic is False
    assert cr.is_projected is True
    assert cr.sample_count == 2


# ---------------------------------------------------------------------------
# TEST 6: SAFE TOPOLOGICAL REPROJECTION
# ---------------------------------------------------------------------------

def test_transform_geometry_safely(crs_service):
    """
    Verifies that geometry reprojection from EPSG:4326 to UTM 43N (EPSG:32643)
    and back preserves valid polygon topology and approximate metric area.
    """
    # 50m x 40m footprint in Bengaluru
    poly = Polygon([
        (77.6400, 12.9780),
        (77.6405, 12.9780),
        (77.6405, 12.9784),
        (77.6400, 12.9784),
        (77.6400, 12.9780),
    ])
    assert poly.is_valid

    # Forward transform to UTM 43N
    proj_geom = crs_service.transform_geometry_safely(poly, "EPSG:4326", "EPSG:32643")
    assert proj_geom.is_valid
    # Area should be roughly ~2400 sq meters
    assert 2000.0 < proj_geom.area < 3000.0

    # Inverse transform back to EPSG:4326
    back_geom = crs_service.transform_geometry_safely(proj_geom, "EPSG:32643", "EPSG:4326")
    assert back_geom.is_valid
    assert pytest.approx(back_geom.bounds[0], abs=1e-5) == poly.bounds[0]
    assert pytest.approx(back_geom.bounds[1], abs=1e-5) == poly.bounds[1]


# ---------------------------------------------------------------------------
# TEST 7: API INTEGRATION (GET & POST)
# ---------------------------------------------------------------------------

def test_api_get_crs_report_bengaluru(client):
    """Verifies GET /api/datasets/bengaluru-ward112/crs-report returns complete audit metadata."""
    res = client.get("/api/datasets/bengaluru-ward112/crs-report")
    assert res.status_code == 200
    data = res.json()

    assert data["dataset_id"] == "bengaluru-ward112"
    assert data["detected_crs"] == "EPSG:4326"
    assert data["processing_crs"] == "EPSG:32643"
    assert data["display_crs"] == "EPSG:4326"
    assert data["crs_detection_method"] in ["DECLARED_AUTHORITATIVE", "COORDINATE_EXTENT_ANALYSIS"]
    assert "crs_confidence" in data
    assert data["crs_confidence"] >= 0.75
    assert "original_crs" in data
    assert "coordinate_range" in data
    assert data["coordinate_range"]["units"] == "degrees"


def test_api_get_crs_report_not_found(client):
    """Verifies 404 for nonexistent dataset ID."""
    res = client.get("/api/datasets/nonexistent-dataset-id/crs-report")
    assert res.status_code == 404


def test_api_confirm_crs(client):
    """Verifies POST /api/datasets/{id}/crs-confirm persists officer approval."""
    payload = {
        "confirmed_crs": "EPSG:32643",
        "officer_id": "OFFICER-GNSS-42",
        "notes": "Verified against local cadastral survey sheet #104",
    }
    res = client.post("/api/datasets/bengaluru-ward112/crs-confirm", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert data["confirmed_crs"] == "EPSG:32643"
    assert data["status"] == "confirmed"
