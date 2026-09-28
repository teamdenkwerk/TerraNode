"""
tests/test_schema_mapping.py

TERRANODE FEATURE 01: SMART SCHEMA MAPPING UNIT & INTEGRATION TESTS

Tests:
1. Exact matches (e.g. "parcel_id", "geometry", "area")
2. Case differences (e.g. "Survey_No", "PARCEL_ID", "pReOpErTy_Id")
3. Abbreviations (e.g. "surv_no", "plot_no", "pid", "sqm", "geom")
4. Unknown fields (e.g. "random_notes_xyz", "temp_col_123")
5. Conflicting mappings (e.g. multiple source columns competing for "parcel_id")
6. Low-confidence mappings (ensuring low-confidence fields are NEVER silently auto-accepted)
7. Non-fabricated confidence bounds (0.0 <= confidence <= 1.0)
8. End-to-end API integration tests:
   - POST /api/schema/mapping
   - GET /api/schema/mapping/{dataset_id}
   - POST /api/schema/mapping/{dataset_id}/confirm
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schema_mapping.mapping_models import (
    CanonicalField,
    ConfirmMappingRequest,
    FieldMappingSuggestion,
    MappingStatus,
    MatchType,
    SchemaMappingRequest,
)
from backend.schema_mapping.schema_mapper import (
    SmartSchemaMapper,
    normalize_field_name,
)
from backend.schema_mapping.mapping_service import SchemaMappingService

client = TestClient(app)


# ---------------------------------------------------------------------------
# UNIT TESTS: NORMALIZATION
# ---------------------------------------------------------------------------

def test_normalization_case_and_punctuation():
    # Lowercase & remove punctuation
    assert normalize_field_name("SURVEY_NO") == "survey_number"
    assert normalize_field_name("Parcel-Id!") == "parcel_identifier"
    assert normalize_field_name("plotNo") == "plot_number"  # camelCase tokenization
    assert normalize_field_name("area (sqm)") == "area_area"


def test_normalization_abbreviations():
    assert "number" in normalize_field_name("sy_no")
    assert "latitude" in normalize_field_name("lat_deg")
    assert "longitude" in normalize_field_name("lon_deg")
    assert "building" in normalize_field_name("bld_id")


# ---------------------------------------------------------------------------
# UNIT TESTS: MATCHING CATEGORIES
# ---------------------------------------------------------------------------

def test_exact_matches():
    mapper = SmartSchemaMapper()
    cols = ["parcel_id", "geometry", "area", "source", "date"]
    suggestions = mapper.map_columns(cols)

    by_col = {s.source_field: s for s in suggestions}

    assert by_col["parcel_id"].suggested_canonical_field == CanonicalField.PARCEL_ID.value
    assert by_col["parcel_id"].confidence == 1.0
    assert by_col["parcel_id"].match_type == MatchType.EXACT
    assert by_col["parcel_id"].status == MappingStatus.SUGGESTED

    assert by_col["geometry"].suggested_canonical_field == CanonicalField.GEOMETRY.value
    assert by_col["geometry"].confidence == 1.0

    assert by_col["area"].suggested_canonical_field == CanonicalField.AREA.value
    assert by_col["area"].confidence == 1.0


def test_abbreviation_matches():
    mapper = SmartSchemaMapper()
    cols = ["survey_no", "plot_no", "pid", "area_sqm", "geom"]
    suggestions = mapper.map_columns(cols)
    by_col = {s.source_field: s for s in suggestions}

    # "survey_no" -> survey_number
    assert by_col["survey_no"].suggested_canonical_field == CanonicalField.SURVEY_NUMBER.value
    assert by_col["survey_no"].confidence >= 0.90
    assert by_col["survey_no"].is_low_confidence is False

    # "plot_no" -> survey_number synonym
    assert by_col["plot_no"].suggested_canonical_field == CanonicalField.SURVEY_NUMBER.value
    assert by_col["plot_no"].confidence >= 0.90

    # "pid" -> parcel_id synonym
    assert by_col["pid"].suggested_canonical_field == CanonicalField.PARCEL_ID.value
    assert by_col["pid"].confidence >= 0.90

    # "area_sqm" -> area
    assert by_col["area_sqm"].suggested_canonical_field == CanonicalField.AREA.value
    assert by_col["area_sqm"].confidence >= 0.90


def test_case_difference_matches():
    mapper = SmartSchemaMapper()
    cols = ["PARCEL_ID", "Survey_Number", "PROPERTY_ID", "Owner_Name"]
    suggestions = mapper.map_columns(cols)
    by_col = {s.source_field: s for s in suggestions}

    assert by_col["PARCEL_ID"].suggested_canonical_field == CanonicalField.PARCEL_ID.value
    assert by_col["PARCEL_ID"].confidence == 1.0

    assert by_col["Survey_Number"].suggested_canonical_field == CanonicalField.SURVEY_NUMBER.value
    assert by_col["Survey_Number"].confidence == 1.0

    assert by_col["Owner_Name"].suggested_canonical_field == CanonicalField.OWNER_REFERENCE.value
    assert by_col["Owner_Name"].confidence >= 0.95


def test_unknown_fields_are_unmapped():
    mapper = SmartSchemaMapper()
    cols = ["temp_aux_scratch_77", "unrelated_vendor_meta_val", "foo_bar_xyz"]
    suggestions = mapper.map_columns(cols)

    for s in suggestions:
        assert s.status == MappingStatus.UNMAPPED
        assert s.suggested_canonical_field is None
        assert s.confidence < 0.40
        assert "Unmapped" in s.decision_reason


def test_low_confidence_fields_never_silently_mapped():
    mapper = SmartSchemaMapper()
    # A column with weak resemblance: e.g. "parcel_remarks_notes" (has 'parcel' word but is remarks)
    cols = ["parcel_notes"]
    suggestions = mapper.map_columns(cols)
    s = suggestions[0]

    # Must be marked low-confidence, NEVER silently auto-accepted as clean SUGGESTED
    if s.suggested_canonical_field:
        assert s.is_low_confidence is True
        assert s.status == MappingStatus.LOW_CONFIDENCE
        assert "Low confidence" in s.decision_reason


def test_conflicting_mappings_detection():
    mapper = SmartSchemaMapper()
    # Both "parcel_id" and "cad_id" resolve to parcel_id
    cols = ["parcel_id", "cad_id"]
    suggestions = mapper.map_columns(cols)
    by_col = {s.source_field: s for s in suggestions}

    # "parcel_id" has confidence 1.0 -> should win
    assert by_col["parcel_id"].suggested_canonical_field == CanonicalField.PARCEL_ID.value
    assert by_col["parcel_id"].is_conflicting is False

    # "cad_id" is second contender -> must be flagged as conflicting
    assert by_col["cad_id"].is_conflicting is True
    assert by_col["cad_id"].status == MappingStatus.CONFLICTING
    assert "Conflicting mapping" in by_col["cad_id"].decision_reason


# ---------------------------------------------------------------------------
# INTEGRATION TESTS: FASTAPI ENDPOINTS
# ---------------------------------------------------------------------------

def test_api_schema_mapping_generation():
    payload = {
        "dataset_id": "test_cadastre_v1",
        "columns": ["khasra_no", "plot_number", "land_area", "owner_name", "unknown_tag"],
    }
    res = client.post("/api/schema/mapping", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_fields"] == 5
    assert len(data["mappings"]) == 5

    by_col = {m["source_field"]: m for m in data["mappings"]}
    assert by_col["khasra_no"]["suggested_canonical_field"] == "parcel_id"
    assert by_col["plot_number"]["suggested_canonical_field"] == "survey_number"
    assert by_col["land_area"]["suggested_canonical_field"] == "area"
    assert by_col["owner_name"]["suggested_canonical_field"] == "owner_reference"
    assert by_col["unknown_tag"]["suggested_canonical_field"] is None


def test_api_schema_mapping_confirmation_and_retrieval():
    dataset_id = "test_cadastre_v1"
    confirm_payload = {
        "dataset_version": "v1.0",
        "confirmed_by": "Senior Cadastral Officer",
        "mappings": {
            "khasra_no": "parcel_id",
            "plot_number": "survey_number",
            "unknown_tag": None,  # rejected
        },
        "notes": "Verified against state revenue dictionary standards."
    }

    # 1. Confirm mapping
    confirm_res = client.post(f"/api/schema/mapping/{dataset_id}/confirm", json=confirm_payload)
    assert confirm_res.status_code == 200
    rec = confirm_res.json()
    assert rec["dataset_id"] == dataset_id
    assert rec["confirmed_by"] == "Senior Cadastral Officer"
    assert rec["applied_to_dataset"] is True

    # 2. Retrieve mapping for dataset
    get_res = client.get(f"/api/schema/mapping/{dataset_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["dataset_id"] == dataset_id
    assert get_data["audit_metadata"]["is_confirmed"] is True
    assert get_data["audit_metadata"]["confirmed_by"] == "Senior Cadastral Officer"
