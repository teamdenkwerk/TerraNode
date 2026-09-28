"""
backend/history/models.py

TERRANODE ENHANCEMENT 08 — HISTORICAL GROUND TRUTH & CHANGE EVIDENCE

Data models and schemas for immutable historical parcel records and spatial change evidence.
MANDATORY COMPLIANCE:
Describes OBSERVED SPATIAL CHANGE only.
Never infers ownership change, title change, or legal boundary change without authoritative administrative records.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HistoricalSourceType(str, Enum):
    OFFICIAL_CADASTRAL = "Official Cadastral"
    MUNICIPAL_GIS = "Municipal GIS"
    DRONE_ORI = "Drone ORI"
    SURVEY_RECORDS = "Survey Records"
    CORS_RTK = "CORS / RTK Survey"
    HISTORICAL_VERIFIED = "Verified Historical Dataset"


class HistoricalVerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REFERENCE_ONLY = "REFERENCE_ONLY"


class HistoricalVersionSnapshot(BaseModel):
    """Represents a dated, verified geometric version of a parcel entity."""
    version_number: int
    source_type: str = Field(..., description="e.g. Official Cadastral, Municipal GIS, Drone ORI, CORS / RTK Survey")
    source_name: str
    source_date: str
    verification_status: str = "VERIFIED"
    area_m2: float
    centroid: List[float] = Field(..., description="[lat, lon]")
    geometry: Dict[str, Any]
    geometry_crs: str = "EPSG:4326"
    change_reason: Optional[str] = None
    decision: Optional[str] = None
    reviewer: Optional[str] = None
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class HistoricalComparisonDetails(BaseModel):
    area_change_m2: float
    area_change_percentage: float
    centroid_shift_m: float
    iou: float
    boundary_change: str  # "Detected" or "Not Detected"
    geometry_overlap_m2: float
    source_agreement: str
    symmetric_difference_m2: float


class HistoricalComparisonResponse(BaseModel):
    parcel_uuid: str
    version_a: HistoricalVersionSnapshot
    version_b: HistoricalVersionSnapshot
    comparison: HistoricalComparisonDetails

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class HistoricalTimelineResponse(BaseModel):
    parcel_uuid: str
    has_historical_data: bool
    message: Optional[str] = None
    required_dataset: Optional[str] = None
    total_versions: int = 0
    timeline: List[HistoricalVersionSnapshot] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()
