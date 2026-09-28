"""
tests/test_version_history.py

TERRANODE FEATURE 04 — PARCEL VERSION HISTORY & AUDIT LEDGER TESTS

Verifies:
1. Version creation & persistence across multiple milestones (Version 1 -> Version 2 -> Version 3)
2. Database constraint: Compound unique key (parcel_uuid, version_number) prevents duplicate versions (HTTP 409)
3. Monotonic versioning invariant
4. Mathematical geometry comparison between versions (area_change, boundary_change, centroid_shift)
5. Non-deletion invariant: Historical versions are never overwritten
6. REST API Endpoints:
   - GET /api/parcels/{uuid}/history
   - GET /api/parcels/{uuid}/versions/{version}
   - POST /api/parcels/{uuid}/new-version
"""

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.identity.version_history import (
    DuplicateVersionError,
    NewVersionRequest,
    ParcelVersionHistoryService,
    VersionNotFoundError,
)


@pytest.fixture
def temp_history_service():
    """Isolated ParcelVersionHistoryService with temporary disk storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "test_version_history.json"
        svc = ParcelVersionHistoryService(storage_path=storage, auto_seed=False)
        yield svc


@pytest.fixture
def client():
    return TestClient(app)


# Sample geometries
V1_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.6400, 12.9780],
            [77.6405, 12.9780],
            [77.6405, 12.9784],
            [77.6400, 12.9784],
            [77.6400, 12.9780],
        ]
    ],
}

# Version 2: Drone reconciliation (subtle adjustment, ~0.6m drift, 95% IoU)
V2_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.6400, 12.9780],
            [77.64051, 12.9780],
            [77.64051, 12.97841],
            [77.6400, 12.97841],
            [77.6400, 12.9780],
        ]
    ],
}

# Version 3: Surveyor-approved correction (refined vertices with RTK)
V3_GEOM = {
    "type": "Polygon",
    "coordinates": [
        [
            [77.6400, 12.9780],
            [77.64052, 12.9780],
            [77.64052, 12.97842],
            [77.6400, 12.97842],
            [77.6400, 12.9780],
        ]
    ],
}


# ---------------------------------------------------------------------------
# TEST 1: SEQUENTIAL VERSION CREATION (V1 -> V2 -> V3)
# ---------------------------------------------------------------------------

def test_sequential_version_creation(temp_history_service):
    """
    Verifies that multiple versions can be appended sequentially:
    - Version 1: Original cadastral geometry
    - Version 2: Drone reconciliation
    - Version 3: Surveyor-approved correction
    """
    parcel_uuid = "test-uuid-abc-123"

    # Version 1
    req1 = NewVersionRequest(
        geometry=V1_GEOM,
        source_datasets=["Survey of India Paper Map (1998)"],
        confidence=0.88,
        decision="ORIGINAL_INGESTION",
        review_status="APPROVED",
        reviewer="Revenue Department",
        change_reason="Original cadastral geometry digitization",
        version_number=1,
    )
    v1_rec, _ = temp_history_service.create_new_version(parcel_uuid, req1)
    assert v1_rec.version_number == 1
    assert v1_rec.decision == "ORIGINAL_INGESTION"

    # Version 2
    req2 = NewVersionRequest(
        geometry=V2_GEOM,
        source_datasets=["Survey of India", "Drone Orthophoto 2025"],
        confidence=0.92,
        decision="DRONE_RECONCILIATION",
        review_status="AUTO_VALIDATED",
        reviewer="TerraNode Consensus Engine",
        change_reason="High-resolution drone orthophoto reconciliation",
    )
    v2_rec, comp2 = temp_history_service.create_new_version(parcel_uuid, req2)
    assert v2_rec.version_number == 2
    assert v2_rec.decision == "DRONE_RECONCILIATION"
    assert comp2 is not None
    assert comp2.version_a == 1
    assert comp2.version_b == 2
    assert comp2.boundary_change.metric_iou > 0.90

    # Version 3
    req3 = NewVersionRequest(
        geometry=V3_GEOM,
        source_datasets=["Survey of India", "Drone Orthophoto", "Field RTK GNSS"],
        confidence=0.98,
        decision="SURVEYOR_APPROVED_CORRECTION",
        review_status="APPROVED",
        reviewer="Senior Surveyor Ramesh K.",
        change_reason="Field RTK GNSS verified boundary correction",
    )
    v3_rec, comp3 = temp_history_service.create_new_version(parcel_uuid, req3)
    assert v3_rec.version_number == 3
    assert v3_rec.decision == "SURVEYOR_APPROVED_CORRECTION"

    # Verify history timeline
    history = temp_history_service.get_history(parcel_uuid)
    assert history.total_versions == 3
    assert history.current_version == 3
    assert [v["version_number"] for v in history.timeline] == [1, 2, 3]


# ---------------------------------------------------------------------------
# TEST 2: DATABASE CONSTRAINT — DUPLICATE VERSION NUMBERS PREVENTED
# ---------------------------------------------------------------------------

def test_database_constraint_duplicate_version(temp_history_service):
    """
    CRITICAL CONSTRAINT: The compound key (parcel_uuid, version_number) MUST be unique.
    Attempting to re-insert an existing version number MUST raise DuplicateVersionError.
    """
    parcel_uuid = "test-uuid-constraint-1"

    req1 = NewVersionRequest(
        geometry=V1_GEOM,
        change_reason="Initial boundary",
        version_number=1,
    )
    temp_history_service.create_new_version(parcel_uuid, req1)

    # Attempt to insert version 1 again
    req_duplicate = NewVersionRequest(
        geometry=V2_GEOM,
        change_reason="Duplicate version attempt",
        version_number=1,
    )
    with pytest.raises(DuplicateVersionError) as exc_info:
        temp_history_service.create_new_version(parcel_uuid, req_duplicate)

    assert "DATABASE CONSTRAINT VIOLATION" in str(exc_info.value)
    assert "Duplicate version 1" in str(exc_info.value)


def test_database_constraint_monotonicity(temp_history_service):
    """
    Verifies that a new version cannot have a version number less than or equal to current max.
    """
    parcel_uuid = "test-uuid-monotonic-1"

    req1 = NewVersionRequest(geometry=V1_GEOM, change_reason="Initial v1", version_number=1)
    temp_history_service.create_new_version(parcel_uuid, req1)

    req2 = NewVersionRequest(geometry=V2_GEOM, change_reason="Next v2", version_number=2)
    temp_history_service.create_new_version(parcel_uuid, req2)

    # Attempt to insert version 1 when version 2 already exists
    req_old = NewVersionRequest(geometry=V3_GEOM, change_reason="Backdated version", version_number=1)
    with pytest.raises(DuplicateVersionError) as exc_info:
        temp_history_service.create_new_version(parcel_uuid, req_old)

    assert "CONSTRAINT VIOLATION" in str(exc_info.value) or "MONOTONICITY" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TEST 3: NON-DELETION INVARIANT — HISTORICAL VERSIONS ARE NEVER OVERWRITTEN
# ---------------------------------------------------------------------------

def test_historical_versions_never_overwritten(temp_history_service):
    """
    Verifies that inserting a new version leaves all previous versions completely intact.
    """
    parcel_uuid = "test-uuid-audit-trail"

    req1 = NewVersionRequest(geometry=V1_GEOM, change_reason="Original v1", reviewer="Officer A", version_number=1)
    temp_history_service.create_new_version(parcel_uuid, req1)

    req2 = NewVersionRequest(geometry=V2_GEOM, change_reason="Drone v2", reviewer="Officer B", version_number=2)
    temp_history_service.create_new_version(parcel_uuid, req2)

    # Verify Version 1 is still exactly as originally created
    v1_detail = temp_history_service.get_version_detail(parcel_uuid, 1)
    assert v1_detail["version_number"] == 1
    assert v1_detail["reviewer"] == "Officer A"
    assert v1_detail["change_reason"] == "Original v1"
    from shapely.geometry import shape
    assert shape(v1_detail["geometry"]).equals(shape(V1_GEOM))


# ---------------------------------------------------------------------------
# TEST 4: MATHEMATICAL GEOMETRY COMPARISON BETWEEN VERSIONS
# ---------------------------------------------------------------------------

def test_geometry_comparison_metrics(temp_history_service):
    """
    Verifies rigorous metric calculation of:
    - area_change (diff_m2, percent_change)
    - boundary_change (metric_iou, symmetric_difference_m2, has_boundary_change)
    - centroid_shift (distance_m, bearing_deg)
    """
    parcel_uuid = "test-uuid-comparison"

    req1 = NewVersionRequest(geometry=V1_GEOM, change_reason="Initial baseline version")
    temp_history_service.create_new_version(parcel_uuid, req1)

    req2 = NewVersionRequest(geometry=V2_GEOM, change_reason="Resurvey update version")
    _, comp = temp_history_service.create_new_version(parcel_uuid, req2)

    assert comp is not None
    # Area change
    assert comp.area_change.area_a_m2 > 2000.0
    assert comp.area_change.area_b_m2 > 2000.0
    assert comp.area_change.diff_m2 != 0.0

    # Boundary change
    assert 0.90 < comp.boundary_change.metric_iou < 1.0
    assert comp.boundary_change.symmetric_difference_m2 > 0.0
    assert comp.boundary_change.has_boundary_change is True

    # Centroid shift
    assert 0.1 < comp.centroid_shift.distance_m < 2.0
    assert comp.centroid_shift.bearing_deg is not None
    assert 0.0 <= comp.centroid_shift.bearing_deg <= 360.0


# ---------------------------------------------------------------------------
# TEST 5: REST API INTEGRATION
# ---------------------------------------------------------------------------

def test_api_version_history_workflow(client):
    """
    Full API integration test:
    1. Resolve parcel to establish permanent UUID
    2. GET /api/parcels/{uuid}/history
    3. POST /api/parcels/{uuid}/new-version
    4. GET /api/parcels/{uuid}/versions/{version} with comparison
    5. POST /api/parcels/{uuid}/new-version with duplicate version -> HTTP 409
    """
    # 1. Register baseline parcel with unique coordinate location
    import uuid
    uid_tag = uuid.uuid4().hex[:6]
    test_poly = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.6450, 12.9850],
                [77.6455, 12.9850],
                [77.6455, 12.9854],
                [77.6450, 12.9854],
                [77.6450, 12.9850],
            ]
        ],
    }
    test_poly_v2 = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.6450, 12.9850],
                [77.64551, 12.9850],
                [77.64551, 12.98541],
                [77.6450, 12.98541],
                [77.6450, 12.9850],
            ]
        ],
    }

    resolve_payload = {
        "source_dataset": "api_history_dataset",
        "source_id": f"API-HIST-{uid_tag}",
        "survey_number": f"104/A-{uid_tag}",
        "geometry": test_poly,
    }
    res = client.post("/api/parcels/identity/resolve", json=resolve_payload)
    assert res.status_code == 200
    parcel_uuid = res.json()["parcel_uuid"]

    # 2. Query history
    hist_res = client.get(f"/api/parcels/{parcel_uuid}/history")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["parcel_uuid"] == parcel_uuid
    init_ver = hist_data["current_version"]

    # 3. Add new version (Version init_ver + 1)
    target_ver = init_ver + 1
    new_v_payload = {
        "geometry": test_poly_v2,
        "source_datasets": ["Drone Aerial Survey 2025"],
        "confidence": 0.94,
        "decision": "DRONE_RECONCILIATION",
        "review_status": "AUTO_VALIDATED",
        "reviewer": "Drone Processing Engine",
        "change_reason": "High-resolution drone orthophoto alignment",
        "version_number": target_ver,
    }
    post_res = client.post(f"/api/parcels/{parcel_uuid}/new-version", json=new_v_payload)
    assert post_res.status_code == 200
    new_v_data = post_res.json()
    assert new_v_data["version_number"] == target_ver
    assert "comparison_with_previous" in new_v_data

    # 4. GET specific version detail
    v2_res = client.get(f"/api/parcels/{parcel_uuid}/versions/{target_ver}")
    assert v2_res.status_code == 200
    v2_data = v2_res.json()
    assert v2_data["version_number"] == target_ver
    assert v2_data["decision"] == "DRONE_RECONCILIATION"
    assert v2_data["reviewer"] == "Drone Processing Engine"
    assert "comparison_with_previous" in v2_data
    comp = v2_data["comparison_with_previous"]
    assert "area_change" in comp
    assert "boundary_change" in comp
    assert "centroid_shift" in comp

    # 5. Duplicate version constraint -> HTTP 409 Conflict
    dup_payload = {
        "geometry": V3_GEOM,
        "change_reason": "Attempting duplicate version",
        "version_number": target_ver,  # Duplicate!
    }
    dup_res = client.post(f"/api/parcels/{parcel_uuid}/new-version", json=dup_payload)
    assert dup_res.status_code == 409
    assert "CONSTRAINT VIOLATION" in dup_res.json()["detail"]


def test_api_version_not_found(client):
    """Verifies HTTP 404 for unknown version number."""
    res = client.get("/api/parcels/00000000-0000-0000-0000-000000000000/versions/99")
    assert res.status_code == 404
