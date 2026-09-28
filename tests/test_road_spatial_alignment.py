"""
tests/test_road_spatial_alignment.py

Automated test suite verifying the spatial accuracy, coordinate order, geometry normalization,
feature identity binding, and dataset isolation of road centerlines and infrastructure networks.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.infrastructure.repository import get_infrastructure_repository
from backend.infrastructure.validators import validate_and_normalize_geometry

client = TestClient(app)


def test_geometry_validator_detects_inverted_coords():
    """Inverted [lat, lon] coordinates in India must be normalized to standard GeoJSON [lon, lat]."""
    inverted_geom = {
        "type": "LineString",
        "coordinates": [
            [13.0445, 80.2325],
            [13.0480, 80.2335],
        ]
    }
    normalized, s_geom = validate_and_normalize_geometry(inverted_geom, city="chennai")
    coords = normalized["coordinates"]
    # First coordinate must now have longitude (~80.23) and latitude (~13.04)
    assert 80.0 <= coords[0][0] <= 81.0, f"Expected longitude ~80.23, got {coords[0][0]}"
    assert 13.0 <= coords[0][1] <= 14.0, f"Expected latitude ~13.04, got {coords[0][1]}"
    assert s_geom.is_valid


def test_geometry_validator_rejects_out_of_bounds():
    """Coordinates outside WGS84 range must raise ValueError."""
    invalid_geom = {
        "type": "LineString",
        "coordinates": [
            [999.0, 13.0],
            [80.0, 13.0],
        ]
    }
    with pytest.raises(ValueError):
        validate_and_normalize_geometry(invalid_geom)


def test_usman_road_exact_spatial_alignment():
    """
    Verifies that 'ROAD-MAA-001' (Usman Road Flyover & North Usman Road Arterial)
    is accurately positioned on the real OpenStreetMap road corridor (Lon ~80.232 to 80.234, Lat ~13.041 to 13.053).
    """
    repo = get_infrastructure_repository()
    feature = repo.get_feature_by_id("ROAD-MAA-001", city="Chennai")
    assert feature is not None, "Feature ROAD-MAA-001 not found in repository"

    props = feature["properties"]
    assert "Usman Road" in props["name"]
    assert props["verification_status"] == "VERIFIED"

    geom = feature["geometry"]
    assert geom["type"] == "LineString"
    coords = geom["coordinates"]
    assert len(coords) >= 15, "Usman Road centerline should have multi-point high-fidelity curve vertices"

    # All coordinates must be within the actual Usman Road corridor
    for lon, lat in coords:
        assert 80.2300 <= lon <= 80.2355, f"Longitude {lon} is outside Usman Road corridor [80.2300, 80.2355]"
        assert 13.0400 <= lat <= 13.0540, f"Latitude {lat} is outside Usman Road corridor [13.0400, 13.0540]"

    # Centroid check
    centroid = props["geometry_centroid"]
    assert 80.2315 <= centroid[0] <= 80.2340, f"Centroid lon {centroid[0]} not aligned with Usman Road"
    assert 13.0440 <= centroid[1] <= 13.0490, f"Centroid lat {centroid[1]} not aligned with Usman Road"

    # Metric length check (> 1000m)
    assert props["length_meters"] > 1000.0, f"Expected length > 1000m, got {props['length_meters']}m"


def test_tnagar_arterial_road_network_corridors():
    """Verifies all T. Nagar arterial roads align with their physical corridors."""
    repo = get_infrastructure_repository()
    roads = repo.get_all_features_geojson(infra_type="road", city="Chennai")
    features = roads.get("features", [])
    assert len(features) >= 6

    feature_map = {f["properties"]["feature_id"]: f for f in features}

    # ROAD-MAA-002: South Usman Road
    assert "ROAD-MAA-002" in feature_map
    sur = feature_map["ROAD-MAA-002"]
    assert "South Usman Road" in sur["properties"]["name"]
    assert sur["properties"]["geometry_centroid"][1] < 13.042  # South of Panagal Park

    # ROAD-MAA-003: Pondy Bazaar / Sir Theagaraya Road (East-West corridor)
    assert "ROAD-MAA-003" in feature_map
    pbr = feature_map["ROAD-MAA-003"]
    assert "Theagaraya" in pbr["properties"]["name"] or "Pondy" in pbr["properties"]["name"]
    bounds_pbr = pbr["properties"]["geometry_bounds"]
    # Spans from Panagal Park (~80.233) eastward towards Anna Salai (~80.245)
    assert bounds_pbr[0] < 80.235 and bounds_pbr[2] > 80.244

    # ROAD-MAA-004: G.N. Chetty Road (Diagonally northeast from Panagal Park to Gemini)
    assert "ROAD-MAA-004" in feature_map
    gnc = feature_map["ROAD-MAA-004"]
    assert "G.N. Chetty" in gnc["properties"]["name"] or "Gopathi" in gnc["properties"]["name"]

    # ROAD-MAA-005: Venkatanarayana Road (Southeast to Nandanam)
    assert "ROAD-MAA-005" in feature_map
    vkr = feature_map["ROAD-MAA-005"]
    assert "Venkatanarayana" in vkr["properties"]["name"]


def test_mambalam_canal_alignment():
    """
    Verifies Mambalam Canal runs north-south parallel to western railway corridor
    and does NOT cut diagonally across Panagal Park or city blocks.
    """
    repo = get_infrastructure_repository()
    feature = repo.get_feature_by_id("DRAIN-MAA-001", city="Chennai")
    assert feature is not None
    props = feature["properties"]
    assert "Mambalam Canal" in props["name"]

    geom = feature["geometry"]
    coords = geom["coordinates"]
    # All canal coordinates must stay west of Usman Road corridor (lon <= 80.2305)
    for lon, lat in coords:
        assert 80.2260 <= lon <= 80.2305, f"Canal lon {lon} cuts into blocks/park!"
        assert 13.0300 <= lat <= 13.0540


def test_dataset_isolation_no_leakage():
    """Chennai queries must not return Bengaluru features, and vice versa."""
    repo = get_infrastructure_repository()
    chennai_feats = repo.get_all_features_geojson(city="Chennai")["features"]
    bengaluru_feats = repo.get_all_features_geojson(city="Bengaluru")["features"]

    for f in chennai_feats:
        assert "chennai" in f["properties"]["source_dataset_id"].lower()
        assert "blr" not in f["properties"]["infrastructure_id"].lower()

    for f in bengaluru_feats:
        assert "chennai" not in f["properties"]["source_dataset_id"].lower()


def test_infrastructure_api_endpoints():
    """Verifies the REST API endpoints for road lookup and diagnostics."""
    # 1. Scoped features with diagnostic flag
    res = client.get("/api/infrastructure/features?layer_type=road&city=Chennai&diagnostic=true")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    assert "diagnostic" in data
    assert data["diagnostic"]["active_city"] == "Chennai"
    assert len(data["features"]) >= 6

    # 2. Get specific feature by ID
    res_feat = client.get("/api/infrastructure/features/ROAD-MAA-001?city=Chennai")
    assert res_feat.status_code == 200
    feat_data = res_feat.json()
    assert feat_data["id"] == "ROAD-MAA-001"
    assert "Usman Road" in feat_data["properties"]["name"]

    # 3. Road-specific alias endpoint
    res_road = client.get("/api/infrastructure/roads/ROAD-MAA-001?city=Chennai")
    assert res_road.status_code == 200
    road_data = res_road.json()
    assert road_data["id"] == "ROAD-MAA-001"
    assert road_data["properties"]["length_meters"] > 1000

    # 4. Not found feature returns 404
    res_404 = client.get("/api/infrastructure/features/NON_EXISTENT_ROAD?city=Chennai")
    assert res_404.status_code == 404
