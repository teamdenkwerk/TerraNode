"""
backend/schemas.py

Response models. Field names/types match db/schema.sql's canonical_entities
columns exactly — check schema.sql if you're adding a field, don't guess
at what's available.
"""

from typing import Any, Optional

from pydantic import BaseModel


class EntitySummary(BaseModel):
    """Full-detail entity — used by GET /entities (zoomed-in view)."""
    canonical_uid: str
    geometry: dict[str, Any]  # GeoJSON geometry, already reprojected to EPSG:4326
    area_m2: Optional[float]
    source_count: int
    sources: list[str]
    confidence_score: float
    needs_review: bool


class EntityDetail(EntitySummary):
    """Adds the score breakdown — used by GET /entities/{id}."""
    member_feature_ids: list[int]
    avg_match_score: Optional[float]   # None if this entity was never matched (single source)
    avg_iou_agreement: Optional[float]  # None for the same reason
    tile_id: Optional[str]


class ClusteredCell(BaseModel):
    """One grid cell — used by GET /entities/clustered (zoomed-out view)."""
    lon: float
    lat: float
    count: int
    avg_confidence: float
    
class ResolveRequest(BaseModel):
    status: str  # "approved" | "rejected" | "edited"
    note: str | None = None

class ResolveResponse(BaseModel):
    canonical_uid: str
    resolved_status: str

class UploadResponse(BaseModel):
    filename: str
    stored_path: str
    status: str
    dataset_id: Optional[str] = None
    city: Optional[str] = None
    aoi: Optional[str] = None
    crs_detected: Optional[str] = None
    crs_valid: bool = True
    bbox: Optional[list[float]] = None
    center: Optional[list[float]] = None
    geometry_type: Optional[str] = None
    features_count: int = 0
    detection_message: Optional[str] = None
    error_reason: Optional[str] = None


class DatasetInfo(BaseModel):
    dataset_id: str
    name: str
    city: str
    city_id: str
    aoi: str
    aoi_id: str
    sources: list[str]
    crs: str
    crs_status: str
    bbox: list[float]
    center: list[float]
    default_zoom: int = 16
    features_count: int = 0
    is_reference: bool = False
    upload_date: str
    version: str = "v1.0"
    
class ReconcileRequest(BaseModel):
    bbox: list[float] | None = None          # [min_lon, min_lat, max_lon, max_lat]
    uploaded_file_path: str | None = None
    dataset_id: str | None = None

class ReconcileResponse(BaseModel):
    run_id: int
    status: str
    raw_feature_count: Optional[int] = None
    canonical_entity_count: Optional[int] = None
    review_queue_count: Optional[int] = None