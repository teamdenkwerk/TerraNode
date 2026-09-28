"""
backend/schema_mapping/mapping_models.py

TERRANODE FEATURE 01: SMART SCHEMA MAPPING MODELS

Defines data models, canonical fields, mapping statuses, and request/response payloads.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CanonicalField(str, Enum):
    PARCEL_ID = "parcel_id"
    PARCEL_IDENTIFIER = "parcel_identifier"
    DATASET_ID = "dataset_id"
    SOURCE_ID = "source_id"
    SOURCE_RECORD_ID = "source_record_id"
    SURVEY_NUMBER = "survey_number"
    SURVEY_IDENTIFIER = "survey_identifier"
    PROPERTY_ID = "property_id"
    PROPERTY_IDENTIFIER = "property_identifier"
    OWNER_NAME = "owner_name"
    OWNER_REFERENCE = "owner_reference"
    AREA = "area"
    LAND_USE = "land_use"
    LOCALITY = "locality"
    WARD = "ward"
    ZONE = "zone"
    GEOMETRY = "geometry"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    SOURCE = "source"
    DATE = "date"
    VALID_FROM = "valid_from"
    VALID_TO = "valid_to"
    VERSION_ID = "version_id"


class MappingStatus(str, Enum):
    SUGGESTED = "suggested"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    LOW_CONFIDENCE = "low_confidence"
    CONFLICTING = "conflicting"
    UNMAPPED = "unmapped"


class MatchType(str, Enum):
    EXACT = "EXACT"
    SYNONYM = "SYNONYM"
    ABBREVIATION = "ABBREVIATION"
    TOKEN_OVERLAP = "TOKEN_OVERLAP"
    FUZZY_STRING = "FUZZY_STRING"
    UNKNOWN = "UNKNOWN"


class FieldMappingSuggestion(BaseModel):
    source_field: str = Field(..., description="Original raw column name from source dataset")
    normalized_source_field: str = Field(..., description="Sanitized, tokenized, and abbreviation-expanded form")
    suggested_canonical_field: Optional[str] = Field(None, description="Suggested TerraNode canonical field")
    target_field: Optional[str] = Field(None, description="Mapped canonical target field name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Mathematically derived mapping confidence")
    mapping_confidence: Optional[float] = Field(None, description="Alias for confidence score")
    match_type: MatchType = Field(..., description="Method used to derive mapping match")
    mapping_method: str = Field("exact_match", description="Method: exact, normalized, synonym, alias, token")
    data_type: str = Field("string", description="Field data type: string, numeric, date, geometry")
    status: MappingStatus = Field(..., description="Current status: suggested, low_confidence, confirmed, rejected")
    is_low_confidence: bool = Field(False, description="Flagged true if confidence is below safe automatic threshold")
    is_conflicting: bool = Field(False, description="Flagged true if multiple source fields compete for the same canonical field")
    sample_values: List[Any] = Field(default_factory=list, description="Sample values extracted from dataset")
    decision_reason: str = Field(..., description="Explanation of why this mapping was suggested or flagged")
    dataset_id: Optional[str] = None
    source_id: Optional[str] = None


class SchemaMappingRequest(BaseModel):
    dataset_id: Optional[str] = None
    dataset_name: Optional[str] = None
    file_path: Optional[str] = None
    columns: Optional[List[str]] = None
    sample_records: Optional[List[Dict[str, Any]]] = None


class SchemaMappingResponse(BaseModel):
    success: bool = True
    dataset_id: str
    dataset_version: str = "v1.0"
    total_fields: int
    mapped_fields_count: int
    unmapped_fields_count: int
    low_confidence_fields_count: int
    conflicting_fields_count: int
    mappings: List[FieldMappingSuggestion]
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfirmMappingRequest(BaseModel):
    dataset_version: str = "v1.0"
    confirmed_by: str = "Field / Land Officer"
    # mapping dict of: source_field -> canonical_field (or null to reject/unmap)
    mappings: Dict[str, Optional[str]]
    notes: Optional[str] = None


class ConfirmedSchemaRecord(BaseModel):
    dataset_id: str
    dataset_version: str
    confirmed_by: str
    confirmed_at: str
    mappings: Dict[str, Optional[str]]
    notes: Optional[str] = None
    applied_to_dataset: bool = True
