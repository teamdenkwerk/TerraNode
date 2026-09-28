"""
backend/infrastructure/routes.py

FastAPI endpoints for Enhancement 07: Infrastructure / Utility Crossing Intelligence.

Endpoints:
- GET /api/parcels/{parcel_uuid}/infrastructure-intersections
- GET /api/infrastructure/layers
- GET /api/infrastructure/features
- GET /api/infrastructure/features/{feature_id}
- GET /api/infrastructure/roads/{feature_id}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from backend.infrastructure.models import (
    InfrastructureLayerMeta,
    ParcelInfrastructureResponse,
)
from backend.infrastructure.service import get_infrastructure_service
from backend.infrastructure.repository import get_infrastructure_repository
from backend.dataset_manager import DATASET_CATALOG, get_active_dataset

logger = logging.getLogger(__name__)

router = APIRouter(tags=["infrastructure"])


def _resolve_city_for_dataset(dataset_id: str) -> str:
    if dataset_id in DATASET_CATALOG:
        return DATASET_CATALOG[dataset_id].get("city", "Bengaluru")
    d_low = dataset_id.lower()
    if "chennai" in d_low or "maa" in d_low or "tnagar" in d_low:
        return "Chennai"
    if "mumbai" in d_low or "bom" in d_low or "andheri" in d_low:
        return "Mumbai"
    if "delhi" in d_low or "del" in d_low or "ncr" in d_low:
        return "Delhi NCR"
    return "Bengaluru"


@router.get("/api/parcels/{parcel_uuid}/infrastructure-intersections", response_model=ParcelInfrastructureResponse)
def get_parcel_infrastructure_intersections(parcel_uuid: str):
    """
    GET /api/parcels/{parcel_uuid}/infrastructure-intersections

    Determines whether a reconciled parcel spatially intersects infrastructure or utility features.
    Computes exact metric length, area, percentage, and minimum distance in projected UTM coordinates.
    Strictly uses neutral terminology (no legal violations inferred).
    """
    service = get_infrastructure_service()
    try:
        return service.analyze_parcel(parcel_uuid)
    except Exception as e:
        logger.error("Error analyzing parcel infrastructure for %s: %s", parcel_uuid, e)
        raise HTTPException(status_code=500, detail=f"Infrastructure analysis failed: {str(e)}")


@router.get("/api/infrastructure/layers", response_model=List[InfrastructureLayerMeta])
def list_infrastructure_layers(city: Optional[str] = Query(None, description="Optional city filter")):
    """
    GET /api/infrastructure/layers

    Returns list of all supported infrastructure categories, feature counts,
    verification statuses, and transparent unavailability explanations.
    """
    target_city = city or get_active_dataset().get("city", "Bengaluru")
    repo = get_infrastructure_repository()
    return repo.get_layer_metadata(city=target_city)


@router.get("/datasets/{dataset_id}/infrastructure/layers", response_model=List[InfrastructureLayerMeta])
@router.get("/api/datasets/{dataset_id}/infrastructure/layers", response_model=List[InfrastructureLayerMeta])
def get_dataset_infrastructure_layers(dataset_id: str):
    """Returns infrastructure layers metadata scoped to the specified dataset."""
    city = _resolve_city_for_dataset(dataset_id)
    repo = get_infrastructure_repository()
    return repo.get_layer_metadata(city=city)


@router.get("/datasets/{dataset_id}/infrastructure/{layer_type}")
@router.get("/api/datasets/{dataset_id}/infrastructure/{layer_type}")
def get_dataset_infrastructure_by_type(dataset_id: str, layer_type: str):
    """Returns GeoJSON FeatureCollection for a specific infrastructure layer type scoped to dataset."""
    city = _resolve_city_for_dataset(dataset_id)
    repo = get_infrastructure_repository()
    return repo.get_all_features_geojson(layer_type, city=city)


@router.get("/datasets/{dataset_id}/parcels/{parcel_id}/infrastructure", response_model=ParcelInfrastructureResponse)
@router.get("/api/datasets/{dataset_id}/parcels/{parcel_id}/infrastructure", response_model=ParcelInfrastructureResponse)
def get_dataset_parcel_infrastructure(dataset_id: str, parcel_id: str):
    """Returns infrastructure intersection intelligence for a parcel in a specific dataset."""
    service = get_infrastructure_service()
    return service.analyze_parcel(parcel_id)


@router.post("/api/datasets/{dataset_id}/infrastructure/upload")
@router.post("/api/infrastructure/upload")
async def upload_infrastructure_layer(
    layer_type: str = Form(...),
    file: UploadFile = File(...),
    dataset_id: Optional[str] = "active",
    source_name: Optional[str] = Form(None),
):
    """
    Uploads a user-supplied GeoJSON dataset for a missing infrastructure layer (Tier 4).
    Validates geometries, normalizes coordinates, marks UNVERIFIED, and indexes with STRtree.
    """
    repo = get_infrastructure_repository()
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8")
        target_ds = dataset_id or get_active_dataset().get("dataset_id", "active")
        result = repo.import_user_layer(
            file_content=content_str,
            filename=file.filename or "upload.geojson",
            dataset_id=target_ds,
            layer_type=layer_type.lower(),
            source_name=source_name,
        )
        return result
    except Exception as e:
        logger.error("User infrastructure upload failed: %s", e)
        raise HTTPException(status_code=400, detail=f"Upload failed: {str(e)}")


@router.get("/api/infrastructure/features")
def get_infrastructure_features(
    layer_type: Optional[str] = Query(None, description="Optional filter by infrastructure type ('road', 'drainage', etc.)"),
    city: Optional[str] = Query(None, description="Optional city filter"),
    diagnostic: bool = Query(False, description="Include detailed spatial diagnostics"),
):
    """
    GET /api/infrastructure/features

    Returns GeoJSON FeatureCollection of verified infrastructure geometries
    for Leaflet map layer rendering, scoped to active city.
    """
    target_city = city or get_active_dataset().get("city", "Bengaluru")
    repo = get_infrastructure_repository()
    return repo.get_all_features_geojson(layer_type, city=target_city, diagnostic=diagnostic)


@router.get("/api/infrastructure/features/{feature_id}")
def get_infrastructure_feature_by_id(
    feature_id: str,
    city: Optional[str] = Query(None, description="Optional city filter"),
):
    """
    GET /api/infrastructure/features/{feature_id}

    Returns full spatial, metadata, and metric details of a single infrastructure feature.
    """
    target_city = city or get_active_dataset().get("city", "Bengaluru")
    repo = get_infrastructure_repository()
    feature = repo.get_feature_by_id(feature_id, city=target_city)
    if not feature:
        raise HTTPException(status_code=404, detail=f"Infrastructure feature '{feature_id}' not found in {target_city}")
    return feature


@router.get("/api/infrastructure/roads/{feature_id}")
def get_infrastructure_road_by_id(
    feature_id: str,
    city: Optional[str] = Query(None, description="Optional city filter"),
):
    """
    GET /api/infrastructure/roads/{feature_id}

    Road-specific endpoint alias returning complete geometry, width, authority,
    and diagnostic alignment parameters for a road centerline or corridor.
    """
    return get_infrastructure_feature_by_id(feature_id=feature_id, city=city)
