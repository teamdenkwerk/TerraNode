"""
backend/routers/change_detection_router.py

TERRANODE FEATURE 03: OBSERVED SPATIAL CHANGE DETECTION ROUTER

Endpoints:
- GET /api/datasets/{dataset_id}/changes
- GET /api/datasets/{dataset_id}/changes/{change_id}
- POST /api/datasets/{dataset_id}/changes/compare
- GET /api/datasets/{dataset_id}/parcels/{parcel_id}/history
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Body

from backend.history.change_detection import (
    ChangeDetectionEngine,
    ChangeDetectionReport,
    ObservedChangeItem,
)
from backend.history.service import get_historical_evidence_service

router = APIRouter(tags=["change-detection"])
logger = logging.getLogger(__name__)

_ENGINE = ChangeDetectionEngine()


@router.get("/api/datasets/{dataset_id}/changes", response_model=ChangeDetectionReport)
@router.get("/datasets/{dataset_id}/changes", response_model=ChangeDetectionReport)
def get_dataset_changes(
    dataset_id: str,
    version_a: Optional[str] = Query(None, description="Previous version identifier or label"),
    version_b: Optional[str] = Query(None, description="Current version identifier or label"),
):
    """
    GET /datasets/{dataset_id}/changes
    Compares the current dataset against baseline/previous survey records.
    Returns:
    - summary (records compared, no significant change, changed, new, missing, needs verification)
    - list of ObservedChangeItems with exact metric IoU, centroid drift (m), area difference,
      and supporting source evidence.
    """
    try:
        report = _ENGINE.analyze_dataset_changes(dataset_id, version_a, version_b)
        return report
    except Exception as e:
        logger.error("Error in get_dataset_changes for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to detect dataset changes: {str(e)}")


@router.get("/api/datasets/{dataset_id}/changes/{change_id}")
@router.get("/datasets/{dataset_id}/changes/{change_id}")
def get_change_by_id(dataset_id: str, change_id: str):
    """
    GET /datasets/{dataset_id}/changes/{change_id}
    Retrieves full geometric and attribute details of a single observed spatial change.
    """
    try:
        report = _ENGINE.analyze_dataset_changes(dataset_id)
        for c in report.changes:
            if c.change_id == change_id or c.parcel_id == change_id:
                return c
        raise HTTPException(status_code=404, detail=f"Change '{change_id}' not found in dataset '{dataset_id}'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_change_by_id: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/datasets/{dataset_id}/changes/compare")
@router.post("/datasets/{dataset_id}/changes/compare")
def compare_dataset_versions(
    dataset_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """
    POST /datasets/{dataset_id}/changes/compare
    Executes on-demand geometric comparison between any two versions or layers.
    """
    ver_a = payload.get("version_a") or payload.get("previous_version")
    ver_b = payload.get("version_b") or payload.get("current_version")
    try:
        report = _ENGINE.analyze_dataset_changes(dataset_id, ver_a, ver_b)
        return report
    except Exception as e:
        logger.error("Error comparing versions: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/datasets/{dataset_id}/parcels/{parcel_id}/history")
@router.get("/datasets/{dataset_id}/parcels/{parcel_id}/history")
def get_parcel_history(dataset_id: str, parcel_id: str):
    """
    GET /datasets/{dataset_id}/parcels/{parcel_id}/history
    Retrieves the complete immutable version history and observed spatial change audit for a parcel.
    """
    service = get_historical_evidence_service()
    try:
        timeline = service.get_timeline(parcel_id)
        return timeline
    except Exception as e:
        logger.error("Error in get_parcel_history for %s: %s", parcel_id, e)
        raise HTTPException(status_code=500, detail=str(e))
