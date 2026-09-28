"""
backend/identity/models.py

TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY DATA MODELS

Defines the permanent parcel identity record, source provenance snapshots,
lineage tracking, and API resolution request/response schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParcelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RECONCILED = "RECONCILED"
    IDENTITY_UNCERTAIN = "IDENTITY_UNCERTAIN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DISPUTED = "DISPUTED"


class ResolutionAction(str, Enum):
    NEW_PARCEL_CREATED = "NEW_PARCEL_CREATED"
    MATCHED_EXISTING = "MATCHED_EXISTING"
    SURVEY_NUMBER_EVOLVED = "SURVEY_NUMBER_EVOLVED"
    MUNICIPAL_ID_EVOLVED = "MUNICIPAL_ID_EVOLVED"
    GEOMETRY_REVISED = "GEOMETRY_REVISED"
    DUPLICATE_SOURCE_RECORD = "DUPLICATE_SOURCE_RECORD"
    IDENTITY_UNCERTAIN = "IDENTITY_UNCERTAIN"


class SourceRecordSnapshot(BaseModel):
    """Immutable snapshot of an ingested government or survey source record."""
    source_record_id: str
    source_dataset: str
    source_id: str
    survey_number: Optional[str] = None
    municipal_id: Optional[str] = None
    geometry_version: str = "v1.0"
    recorded_at: str
    match_evidence: Dict[str, Any] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class LineageEvent(BaseModel):
    """Cryptographically or temporally ordered audit event in a parcel's identity lifecycle."""
    event_id: str
    event_type: str
    timestamp: str
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class ParcelIdentityRecord(BaseModel):
    """
    Authoritative internal representation of a land parcel in TerraNode.
    Maintains a stable internal identity independent of mutable government identifiers.
    """
    parcel_uuid: str = Field(..., description="Permanent internal UUID")
    source_ids: List[str] = Field(default_factory=list, description="Historical external source IDs")
    survey_numbers: List[str] = Field(default_factory=list, description="Historical cadastral survey numbers")
    municipal_ids: List[str] = Field(default_factory=list, description="Historical municipal property tax / PID numbers")
    current_geometry_version: str = Field(default="v1.0", description="Geometry version increment counter")
    status: str = Field(default=ParcelStatus.ACTIVE.value, description="Lifecycle status")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    updated_at: str = Field(..., description="ISO 8601 UTC last update timestamp")

    # Spatial attributes
    geometry: Dict[str, Any] = Field(..., description="Canonical GeoJSON geometry")
    centroid: List[float] = Field(default_factory=list, description="[latitude, longitude]")
    area_m2: float = Field(default=0.0, description="Metric area in square meters")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    needs_review: bool = Field(default=False)
    review_reason: Optional[str] = None

    # Full Lineage
    source_records: List[SourceRecordSnapshot] = Field(default_factory=list)
    lineage: List[LineageEvent] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class ResolveIdentityRequest(BaseModel):
    """Input representation of an incoming parcel record requiring identity resolution."""
    source_dataset: str = Field(default="default_ingestion", description="Source layer name or dataset ID")
    source_id: str = Field(..., description="Identifier in source file, e.g. CAD-1001 or row index")
    survey_number: Optional[str] = Field(None, description="Cadastral survey / CTS number if present")
    municipal_id: Optional[str] = Field(None, description="Municipal property tax number / PID if present")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry object")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary attributes")


class IdentityResolutionResult(BaseModel):
    """Outcome of resolving an incoming record against the permanent parcel identity registry."""
    parcel_uuid: str
    resolution_action: ResolutionAction
    status: str
    current_geometry_version: str
    source_ids: List[str]
    survey_numbers: List[str]
    municipal_ids: List[str]
    iou: Optional[float] = None
    centroid_drift_m: Optional[float] = None
    confidence_score: float
    needs_review: bool
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class ResolveIdentityResponse(BaseModel):
    success: bool
    resolved_count: int
    results: List[IdentityResolutionResult]

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
