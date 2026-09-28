"""
tests/test_dataset_manager.py

Unit and integration tests for the City / AOI Dataset Management,
Import, Pre-Scan, and Safe Workspace Replacement System.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.dataset_manager import (
    get_active_dataset,
    get_active_dataset_id,
    set_active_dataset,
    scan_dataset_folder_or_files,
    STANDARD_CATEGORIES,
)

client = TestClient(app)


def test_standard_categories_defined():
    """Verify that all 15 standard TerraNode categories are defined."""
    assert len(STANDARD_CATEGORIES) == 15
    assert "01_BOUNDARY" in STANDARD_CATEGORIES
    assert "02_PARCELS" in STANDARD_CATEGORIES
    assert "03_BUILDINGS" in STANDARD_CATEGORIES
    assert "04_ROADS" in STANDARD_CATEGORIES
    assert "05_UTILITIES" in STANDARD_CATEGORIES
    assert "06_TRANSPORT" in STANDARD_CATEGORIES
    assert "07_ELEVATION" in STANDARD_CATEGORIES
    assert "08_IMAGERY" in STANDARD_CATEGORIES
    assert "09_GROUND_TRUTH" in STANDARD_CATEGORIES
    assert "10_HISTORICAL" in STANDARD_CATEGORIES
    assert "11_LAND_USE" in STANDARD_CATEGORIES
    assert "12_INFRASTRUCTURE" in STANDARD_CATEGORIES
    assert "13_ADDRESS" in STANDARD_CATEGORIES
    assert "14_CONTEXT" in STANDARD_CATEGORIES
    assert "15_METADATA" in STANDARD_CATEGORIES


def test_get_active_dataset_api():
    """Verify GET /api/datasets/active returns active dataset metadata."""
    set_active_dataset("bengaluru-ward112")
    response = client.get("/api/datasets/active")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "Bengaluru"
    assert data["dataset_status"] == "ACTIVE"


def test_scan_chennai_sample_package():
    """Verify POST /api/datasets/scan analyzes the sample package correctly."""
    response = client.post("/api/datasets/scan", json={"folder_path": "data/sample_packages/CHENNAI_DATA"})
    assert response.status_code == 200
    report = response.json()
    assert report["valid"] is True
    assert report["area"] == "Chennai"
    assert "02_PARCELS" in [l["category"] for l in report["detected_layers"]]
    assert "04_ROADS" in [l["category"] for l in report["detected_layers"]]
    assert "05_UTILITIES" in [l["category"] for l in report["detected_layers"]]
    assert report["requires_replacement_confirmation"] is True


def test_import_chennai_and_replace_workspace():
    """
    Verify POST /api/datasets/import activates Chennai, archives Bengaluru,
    and updates entity & infrastructure scoping.
    """
    # 1. Start on Bengaluru
    set_active_dataset("bengaluru-ward112")
    assert "bengaluru" in get_active_dataset_id()

    # 2. Import Chennai package
    import_payload = {
        "dataset_id": "chennai-tnagar",
        "name": "Chennai — T. Nagar AOI",
        "city": "Chennai",
        "aoi": "T. Nagar AOI",
        "crs": "EPSG:32644 (UTM 44N) -> EPSG:4326",
        "bbox": [80.226, 13.036, 80.244, 13.048],
        "center": [13.0418, 80.2341],
        "replace_active": True,
        "entities": [
            {
                "id": "MAA-101",
                "surveyNumber": "TS-401/1",
                "wardNo": "Ward 134",
                "zone": "T. Nagar",
                "status": "reconciled",
                "confidence": 97,
                "area": 420.5,
                "landUse": "Commercial",
                "centroid": [13.0418, 80.2341],
                "coordinates": [[13.0415, 80.2338], [13.0421, 80.2338], [13.0421, 80.2344], [13.0415, 80.2344]],
            }
        ],
    }

    res = client.post("/api/datasets/import", json=import_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["active_dataset"]["dataset_id"] == "chennai-tnagar"
    assert get_active_dataset_id() == "chennai-tnagar"

    # 3. Check active dataset endpoint
    active_res = client.get("/api/datasets/active")
    assert active_res.status_code == 200
    assert active_res.json()["city"] == "Chennai"

    # 4. Check infrastructure features scoping to Chennai
    infra_res = client.get("/api/infrastructure/features?layer_type=road")
    assert infra_res.status_code == 200
    infra_features = infra_res.json()["features"]
    road_names = [f["properties"]["metadata"].get("road_name") for f in infra_features]
    assert any("Usman Road" in str(r) for r in road_names)

    # 5. Check entities scoping
    ent_res = client.get("/entities")
    assert ent_res.status_code == 200
    entities = ent_res.json()
    assert any(e["canonical_uid"] == "MAA-101" for e in entities)


def test_failed_import_preserves_active_workspace():
    """
    Verify safe replacement guardrail: If an import payload fails validation,
    the current active workspace remains unchanged (no corrupt or empty state).
    """
    # Ensure current is Chennai
    set_active_dataset("chennai-tnagar")
    assert get_active_dataset_id() == "chennai-tnagar"

    # Attempt import with empty/invalid payload
    bad_payload = {
        "dataset_id": "invalid-dataset",
        "city": "",
        "aoi": "",
        "replace_active": True,
        "entities": [],
    }

    res = client.post("/api/datasets/import", json=bad_payload)
    assert res.status_code == 400
    assert "Missing required dataset parameters" in res.json()["detail"]

    # Active dataset must still be Chennai
    assert get_active_dataset_id() == "chennai-tnagar"


def test_switch_back_to_bengaluru():
    """Verify switching active workspace back to Bengaluru restores Bengaluru scoping."""
    switch_res = client.post("/api/datasets/active", json={"dataset_id": "bengaluru-ward112"})
    assert switch_res.status_code == 200
    assert switch_res.json()["active_dataset"]["city"] == "Bengaluru"
    assert "bengaluru" in get_active_dataset_id()

    # Infrastructure reverts to Bengaluru
    infra_res = client.get("/api/infrastructure/features?layer_type=road")
    assert infra_res.status_code == 200
    infra_features = infra_res.json()["features"]
    road_names = [f["properties"]["metadata"].get("road_name") for f in infra_features]
    assert any("Old Airport" in str(r) or "100 Feet" in str(r) for r in road_names)
