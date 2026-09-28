"""
tests/test_parcel_identity.py

TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY TEST SUITE

Verifies:
1. Deterministic permanent UUID issuance
2. Same parcel re-upload (preserves parcel_uuid)
3. Changed survey number (preserves parcel_uuid, appends to survey_numbers)
4. Changed municipal ID (preserves parcel_uuid, appends to municipal_ids)
5. Geometry revision (preserves parcel_uuid, advances current_geometry_version v1.0 -> v2.0)
6. Duplicate source records detection
7. Uncertain identity flagging (status="IDENTITY_UNCERTAIN", needs_review=True)
8. Guardrail: Never merge parcels solely because names or IDs look similar
9. REST API Endpoints:
   - POST /api/parcels/identity/resolve
   - GET /api/parcels/{parcel_uuid}
   - GET /api/parcels/{parcel_uuid}/sources
"""

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.identity.models import (
    ParcelIdentityRecord,
    ParcelStatus,
    ResolutionAction,
    ResolveIdentityRequest,
)
from backend.identity.identity_service import ParcelIdentityService


@pytest.fixture
def temp_service():
    """Isolated ParcelIdentityService instance with temporary disk storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = Path(tmpdir) / "test_parcels.json"
        svc = ParcelIdentityService(storage_path=storage, auto_seed=False)
        yield svc


@pytest.fixture
def client():
    return TestClient(app)


# Base 50m x 40m polygon in Bengaluru (Ward 112 / Domlur area)
BASE_GEOM = {
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


# ---------------------------------------------------------------------------
# TEST 1: NEW PARCEL REGISTRATION
# ---------------------------------------------------------------------------

def test_new_parcel_registration(temp_service):
    """Verifies that an unseen land parcel receives a deterministic permanent parcel_uuid."""
    req = ResolveIdentityRequest(
        source_dataset="cadastre_2024",
        source_id="CAD-101",
        survey_number="101/A",
        municipal_id="PID-DOM-101",
        geometry=BASE_GEOM,
    )
    result = temp_service.resolve_identity(req)

    assert result.resolution_action == ResolutionAction.NEW_PARCEL_CREATED
    assert result.status == ParcelStatus.ACTIVE.value
    assert result.current_geometry_version == "v1.0"
    assert "CAD-101" in result.source_ids
    assert "101/A" in result.survey_numbers
    assert "PID-DOM-101" in result.municipal_ids
    assert result.needs_review is False

    # Verify retrieval from service
    saved = temp_service.get_parcel(result.parcel_uuid)
    assert saved is not None
    assert saved.parcel_uuid == result.parcel_uuid
    assert saved.created_at is not None
    assert saved.updated_at is not None


# ---------------------------------------------------------------------------
# TEST 2: SAME PARCEL RE-UPLOAD
# ---------------------------------------------------------------------------

def test_same_parcel_reupload(temp_service):
    """
    CRITICAL: Re-processing the exact same parcel MUST NOT generate a new random UUID.
    It must retrieve and preserve the existing parcel_uuid.
    """
    req1 = ResolveIdentityRequest(
        source_dataset="cadastre_2024",
        source_id="CAD-101",
        survey_number="101/A",
        municipal_id="PID-101",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req1)
    original_uuid = res1.parcel_uuid

    # Re-upload same parcel
    req2 = ResolveIdentityRequest(
        source_dataset="cadastre_2024",
        source_id="CAD-101",
        survey_number="101/A",
        municipal_id="PID-101",
        geometry=BASE_GEOM,
    )
    res2 = temp_service.resolve_identity(req2)

    assert res2.parcel_uuid == original_uuid
    assert res2.resolution_action == ResolutionAction.DUPLICATE_SOURCE_RECORD


# ---------------------------------------------------------------------------
# TEST 3: CHANGED SURVEY NUMBER WITH VERIFIED GEOMETRIC CONTINUITY
# ---------------------------------------------------------------------------

def test_changed_survey_number(temp_service):
    """
    When the government survey number changes between dataset revisions
    (e.g. '101/A' -> '101/A-REV') but geometry establishes continuity,
    preserve parcel_uuid and record both survey numbers.
    """
    req1 = ResolveIdentityRequest(
        source_dataset="cadastre_2024",
        source_id="CAD-101",
        survey_number="101/A",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req1)
    target_uuid = res1.parcel_uuid

    # New dataset from revenue department uses evolved survey number
    req2 = ResolveIdentityRequest(
        source_dataset="revenue_survey_2025",
        source_id="REV-2025-99",
        survey_number="101/A-REV",
        geometry=BASE_GEOM,
    )
    res2 = temp_service.resolve_identity(req2)

    assert res2.parcel_uuid == target_uuid
    assert res2.resolution_action == ResolutionAction.SURVEY_NUMBER_EVOLVED
    assert "101/A" in res2.survey_numbers
    assert "101/A-REV" in res2.survey_numbers
    assert "REV-2025-99" in res2.source_ids

    # Verify parcel lineage recorded event
    saved = temp_service.get_parcel(target_uuid)
    event_types = [ev.event_type for ev in saved.lineage]
    assert "SURVEY_NUMBER_EVOLVED" in event_types


# ---------------------------------------------------------------------------
# TEST 4: CHANGED MUNICIPAL ID WITH VERIFIED GEOMETRIC CONTINUITY
# ---------------------------------------------------------------------------

def test_changed_municipal_id(temp_service):
    """
    When municipal property ID changes (e.g. 'PID-OLD' -> 'PID-2026-NEW')
    with verified geometric continuity, preserve parcel_uuid and track all municipal IDs.
    """
    req1 = ResolveIdentityRequest(
        source_dataset="municipal_2023",
        source_id="MUN-01",
        municipal_id="PID-OLD-01",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req1)
    target_uuid = res1.parcel_uuid

    req2 = ResolveIdentityRequest(
        source_dataset="municipal_2026",
        source_id="MUN-02",
        municipal_id="PID-2026-NEW",
        geometry=BASE_GEOM,
    )
    res2 = temp_service.resolve_identity(req2)

    assert res2.parcel_uuid == target_uuid
    assert res2.resolution_action == ResolutionAction.MUNICIPAL_ID_EVOLVED
    assert "PID-OLD-01" in res2.municipal_ids
    assert "PID-2026-NEW" in res2.municipal_ids


# ---------------------------------------------------------------------------
# TEST 5: GEOMETRY REVISION
# ---------------------------------------------------------------------------

def test_geometry_revision(temp_service):
    """
    When a resurvey or boundary adjustment occurs with verified continuity
    (IoU >= 0.70, drift < 2.0m), preserve parcel_uuid, advance geometry version to v2.0,
    and update current geometry while retaining previous in source snapshots.
    """
    req1 = ResolveIdentityRequest(
        source_dataset="initial_cadastre",
        source_id="CAD-INIT",
        survey_number="101/A",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req1)
    target_uuid = res1.parcel_uuid
    assert res1.current_geometry_version == "v1.0"

    # Resurvey geometry with ~1m vertex adjustment (IoU ~ 95.6%, drift ~ 0.77m)
    resurvey_geom = {
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

    req2 = ResolveIdentityRequest(
        source_dataset="resurvey_2026",
        source_id="CAD-RESURVEY",
        survey_number="101/A",
        geometry=resurvey_geom,
    )
    res2 = temp_service.resolve_identity(req2)

    assert res2.parcel_uuid == target_uuid
    assert res2.resolution_action == ResolutionAction.GEOMETRY_REVISED
    assert res2.current_geometry_version == "v2.0"

    saved = temp_service.get_parcel(target_uuid)
    assert saved.current_geometry_version == "v2.0"
    assert len(saved.source_records) == 2
    # Verify both geometry versions are traceable in source records
    assert saved.source_records[0].geometry_version == "v1.0"
    assert saved.source_records[1].geometry_version == "v2.0"


# ---------------------------------------------------------------------------
# TEST 6: DUPLICATE SOURCE RECORDS
# ---------------------------------------------------------------------------

def test_duplicate_source_records(temp_service):
    """Verifies that re-submitting the exact same source record is handled idempotently."""
    req = ResolveIdentityRequest(
        source_dataset="survey_of_india",
        source_id="SOI-2024-998",
        survey_number="998",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req)
    res2 = temp_service.resolve_identity(req)

    assert res1.parcel_uuid == res2.parcel_uuid
    assert res2.resolution_action == ResolutionAction.DUPLICATE_SOURCE_RECORD
    saved = temp_service.get_parcel(res1.parcel_uuid)
    # Does not bloat source_ids with duplicate entries
    assert saved.source_ids == ["SOI-2024-998"]


# ---------------------------------------------------------------------------
# TEST 7: UNCERTAIN IDENTITY
# ---------------------------------------------------------------------------

def test_uncertain_identity(temp_service):
    """
    When spatial continuity cannot be established (e.g. Centroid Drift > 2.0m
    violates authoritative reconciliation policy), the record must be marked
    as 'IDENTITY_UNCERTAIN' and require human review.
    """
    req1 = ResolveIdentityRequest(
        source_dataset="baseline",
        source_id="BASE-01",
        survey_number="101/A",
        geometry=BASE_GEOM,
    )
    res1 = temp_service.resolve_identity(req1)

    # Shifted polygon with drift = 4.65 meters (violates < 2.0m policy threshold)
    shifted_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.64003, 12.97803],
                [77.64053, 12.97803],
                [77.64053, 12.97843],
                [77.64003, 12.97843],
                [77.64003, 12.97803],
            ]
        ],
    }

    req2 = ResolveIdentityRequest(
        source_dataset="disputed_layer",
        source_id="DISP-01",
        survey_number="101/A",
        geometry=shifted_geom,
    )
    res2 = temp_service.resolve_identity(req2)

    assert res2.resolution_action == ResolutionAction.IDENTITY_UNCERTAIN
    assert res2.status == ParcelStatus.IDENTITY_UNCERTAIN.value
    assert res2.needs_review is True
    assert "violates authoritative policy" in res2.message


# ---------------------------------------------------------------------------
# TEST 8: GUARDRAIL — NEVER MERGE SOLELY BECAUSE NAMES OR IDS LOOK SIMILAR
# ---------------------------------------------------------------------------

def test_guardrail_never_merge_solely_on_id_similarity(temp_service):
    """
    CRITICAL SAFETY GUARDRAIL:
    Two parcels have identical survey numbers ('Plot-1'), but their geometries
    are in completely different physical locations (1 km away).
    The system MUST NOT merge them into the same parcel_uuid!
    """
    # Parcel A in Domlur (lon 77.64, lat 12.978)
    req_a = ResolveIdentityRequest(
        source_dataset="ward112",
        source_id="PLOT-DOM-1",
        survey_number="Plot-1",
        geometry=BASE_GEOM,
    )
    res_a = temp_service.resolve_identity(req_a)

    # Parcel B in Indiranagar (lon 77.65, lat 12.988 — ~1.5 km away) with identical name!
    far_geom = {
        "type": "Polygon",
        "coordinates": [
            [
                [77.6500, 12.9880],
                [77.6505, 12.9880],
                [77.6505, 12.9884],
                [77.6500, 12.9884],
                [77.6500, 12.9880],
            ]
        ],
    }
    req_b = ResolveIdentityRequest(
        source_dataset="ward113",
        source_id="PLOT-IND-1",
        survey_number="Plot-1",  # Same name!
        geometry=far_geom,
    )
    res_b = temp_service.resolve_identity(req_b)

    # MUST have distinct permanent parcel_uuids
    assert res_a.parcel_uuid != res_b.parcel_uuid
    assert res_b.resolution_action == ResolutionAction.NEW_PARCEL_CREATED


# ---------------------------------------------------------------------------
# TEST 9: REST API INTEGRATION
# ---------------------------------------------------------------------------

def test_api_resolve_and_get_parcel(client):
    """Verifies POST /api/parcels/identity/resolve and GET /api/parcels/{parcel_uuid}."""
    payload = {
        "source_dataset": "api_test_dataset",
        "source_id": "API-CAD-99",
        "survey_number": "SY-999/1",
        "municipal_id": "PID-999",
        "geometry": BASE_GEOM,
    }
    res = client.post("/api/parcels/identity/resolve", json=payload)
    assert res.status_code == 200
    data = res.json()

    parcel_uuid = data["parcel_uuid"]
    assert parcel_uuid is not None
    assert "source_ids" in data
    assert "survey_numbers" in data
    assert "municipal_ids" in data
    assert "current_geometry_version" in data
    assert "status" in data

    # Retrieve full parcel
    get_res = client.get(f"/api/parcels/{parcel_uuid}")
    assert get_res.status_code == 200
    parcel_data = get_res.json()

    # Confirm all 8 required stored fields exist
    assert parcel_data["parcel_uuid"] == parcel_uuid
    assert "source_ids" in parcel_data
    assert "survey_numbers" in parcel_data
    assert "municipal_ids" in parcel_data
    assert "current_geometry_version" in parcel_data
    assert "status" in parcel_data
    assert "created_at" in parcel_data
    assert "updated_at" in parcel_data


def test_api_get_parcel_sources(client):
    """Verifies GET /api/parcels/{parcel_uuid}/sources returns full historical provenance."""
    # Register parcel
    payload = {
        "source_dataset": "lineage_dataset_v1",
        "source_id": "LIN-01",
        "survey_number": "100/1",
        "geometry": BASE_GEOM,
    }
    res = client.post("/api/parcels/identity/resolve", json=payload)
    assert res.status_code == 200
    p_uuid = res.json()["parcel_uuid"]

    # Evolve survey number
    payload2 = {
        "source_dataset": "lineage_dataset_v2",
        "source_id": "LIN-02",
        "survey_number": "100/1-REV",
        "geometry": BASE_GEOM,
    }
    client.post("/api/parcels/identity/resolve", json=payload2)

    # Query sources endpoint
    src_res = client.get(f"/api/parcels/{p_uuid}/sources")
    assert src_res.status_code == 200
    sources_data = src_res.json()

    assert sources_data["parcel_uuid"] == p_uuid
    assert sources_data["total_sources"] >= 2
    assert len(sources_data["sources"]) >= 2
    assert len(sources_data["lineage"]) >= 1


def test_api_parcel_not_found(client):
    """Verifies 404 for unknown parcel_uuid."""
    res = client.get("/api/parcels/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
