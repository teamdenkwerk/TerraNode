"""
backend/history/routes.py

FastAPI routes for Enhancement 08: Historical Ground Truth & Change Evidence.

Endpoints:
- GET /api/parcels/{parcel_uuid}/timeline
- GET /api/parcels/{parcel_uuid}/compare
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query

from backend.history.models import (
    HistoricalComparisonResponse,
    HistoricalTimelineResponse,
)
from backend.history.service import get_historical_evidence_service
from backend.identity.version_history import VersionNotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parcels", tags=["historical-evidence"])


@router.get("/{parcel_uuid}/timeline", response_model=HistoricalTimelineResponse)
def get_parcel_timeline(parcel_uuid: str):
    """
    GET /api/parcels/{parcel_uuid}/timeline

    Retrieves full chronological timeline of verified historical parcel versions.
    If historical data is missing, clearly returns 'No verified historical dataset available'
    with required dataset specification.
    """
    service = get_historical_evidence_service()
    try:
        return service.get_timeline(parcel_uuid)
    except Exception as e:
        logger.error("Error retrieving timeline for %s: %s", parcel_uuid, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{parcel_uuid}/compare", response_model=HistoricalComparisonResponse)
def compare_parcel_versions(
    parcel_uuid: str,
    version_a: int = Query(..., description="First version number to compare"),
    version_b: int = Query(..., description="Second version number to compare"),
):
    """
    GET /api/parcels/{parcel_uuid}/compare?version_a=1&version_b=3

    Compares two specific historical versions of a parcel.
    Calculates metric area change, % change, centroid shift in meters,
    metric IoU, boundary difference detection, and source agreement.
    """
    service = get_historical_evidence_service()
    try:
        return service.compare_versions(parcel_uuid, version_a, version_b)
    except VersionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error comparing versions for %s: %s", parcel_uuid, e)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")
