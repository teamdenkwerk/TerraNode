"""
backend/infrastructure/models.py

TERRANODE ENHANCEMENT 07 — INFRASTRUCTURE & UTILITY CROSSING INTELLIGENCE

Data models and schemas for infrastructure representations, spatial intersections,
and verification states.

MANDATORY COMPLIANCE:
This is NOT a legal enforcement system. Uses strictly neutral spatial terminology:
- "Spatial Intersection Detected"
- "Infrastructure Overlap"
- "Utility Intersection"
- "Proximity Detected"
- "No Intersection Detected"
- "Data Unavailable"

Never asserts legal violations or unauthorized construction without authoritative administrative evidence.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class InfrastructureType(str, Enum):
    ROAD = "road"
    DRAINAGE = "drainage"
    WATER = "water"
    ELECTRICITY = "electricity"
    RAILWAY = "railway"
    PUBLIC_UTILITY = "public_utility"


class IntersectionTerminology(str, Enum):
    INTERSECTION_DETECTED = "Spatial Intersection Detected"
    OVERLAP_DETECTED = "Infrastructure Overlap"
    UTILITY_INTERSECTION = "Utility Intersection"
    PROXIMITY_DETECTED = "Proximity Detected"
    NO_INTERSECTION = "No Intersection Detected"
    DATA_UNAVAILABLE = "Data Unavailable"


class InfrastructureFeature(BaseModel):
    """Normalized infrastructure feature representation."""
    infrastructure_id: str
    infrastructure_type: InfrastructureType
    source_dataset_id: str
    source_feature_id: str
    source_name: str
    source_date: str
    geometry: Dict[str, Any]
    geometry_crs: str = "EPSG:4326"
    verification_status: VerificationStatus = VerificationStatus.VERIFIED
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class InfrastructureIntersectionResult(BaseModel):
    """Calculated spatial relationship between a parcel and an infrastructure feature."""
    infrastructure_type: str
    infrastructure_id: Optional[str] = None
    intersection_exists: bool
    intersection_status: str
    intersection_length_m: float = 0.0
    intersection_area_m2: float = 0.0
    intersection_percentage: float = 0.0
    minimum_distance_m: float = 0.0
    source_dataset: Optional[str] = None
    source_feature_id: Optional[str] = None
    source_name: Optional[str] = None
    verification_status: Optional[str] = None
    calculation_timestamp: str
    details: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class InfrastructureSummary(BaseModel):
    detected: int = 0
    not_detected: int = 0
    unavailable: int = 0


class ParcelInfrastructureResponse(BaseModel):
    """Full API response for GET /api/parcels/{parcel_uuid}/infrastructure-intersections."""
    parcel_uuid: str
    summary: InfrastructureSummary
    results: List[InfrastructureIntersectionResult]
    execution_time_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class InfrastructureLayerMeta(BaseModel):
    """Metadata describing an infrastructure layer in the GIS catalog."""
    type: str
    display_name: str
    feature_count: int
    is_available: bool
    verification_status: str
    sources: List[str]
    unavailability_reason: Optional[str] = None
