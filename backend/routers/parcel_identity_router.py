"""
backend/routers/parcel_identity_router.py

TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY REST API ROUTER

Endpoints:
- POST /api/parcels/identity/resolve: Resolves incoming record(s) to permanent parcel_uuid
- GET /api/parcels/{parcel_uuid}: Retrieves complete parcel identity profile
- GET /api/parcels/{parcel_uuid}/sources: Retrieves all historical source provenance records
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Query, Request

from backend.identity.models import (
    IdentityResolutionResult,
    ParcelIdentityRecord,
    ResolveIdentityRequest,
    ResolveIdentityResponse,
)
from backend.identity.identity_service import get_identity_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parcels", tags=["parcel-identity"])


@router.post("/identity/resolve", response_model=Union[IdentityResolutionResult, ResolveIdentityResponse])
async def resolve_parcel_identity(payload: Dict[str, Any]):
    """
    POST /api/parcels/identity/resolve

    Resolves incoming parcel representation(s) against the permanent parcel identity registry.
    Continuity Rules:
    - Same-parcel re-upload / verified geometry: Preserves existing parcel_uuid.
    - Changed survey number with verified geometry: Preserves parcel_uuid, appends survey number.
    - Changed municipal ID with verified geometry: Preserves parcel_uuid, appends municipal ID.
    - Geometry revision: Preserves parcel_uuid, increments geometry version (e.g. v1.0 -> v2.0).
    - Continuity cannot be established: Marks as IDENTITY_UNCERTAIN and requires officer review.
    - Guardrail: Never merges parcels solely because names or IDs look similar.
    """
    service = get_identity_service()

    try:
        # Check if single record or batch
        if "records" in payload and isinstance(payload["records"], list):
            requests = [ResolveIdentityRequest(**rec) for rec in payload["records"]]
            return service.resolve_batch(requests)
        else:
            req = ResolveIdentityRequest(**payload)
            return service.resolve_identity(req)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error during parcel identity resolution: %s", e)
        raise HTTPException(status_code=500, detail=f"Identity resolution failed: {str(e)}")


@router.get("/{parcel_uuid}")
def get_parcel_by_uuid(parcel_uuid: str):
    """
    GET /api/parcels/{parcel_uuid}

    Retrieves permanent internal identity profile for a land parcel:
    - parcel_uuid
    - source_ids
    - survey_numbers
    - municipal_ids
    - current_geometry_version
    - status
    - created_at
    - updated_at
    - geometry, area_m2, centroid
    """
    service = get_identity_service()
    parcel = service.get_parcel(parcel_uuid)

    if not parcel:
        # Check if caller passed a canonical_uid like 'BLR-101'
        # Check if any parcel has this in source_ids
        for p in service._parcels.values():
            if parcel_uuid in p.source_ids:
                return p.to_dict()
        raise HTTPException(status_code=404, detail=f"Parcel with UUID '{parcel_uuid}' not found.")

    return parcel.to_dict()


@router.get("/{parcel_uuid}/sources")
def get_parcel_sources(parcel_uuid: str):
    """
    GET /api/parcels/{parcel_uuid}/sources

    Retrieves all historical source snapshots, contributing datasets,
    matching evidence, and chronological lineage events for a permanent parcel.
    """
    service = get_identity_service()
    data = service.get_parcel_sources(parcel_uuid)

    if not data:
        # Check by source_id lookup
        for p in service._parcels.values():
            if parcel_uuid in p.source_ids:
                return service.get_parcel_sources(p.parcel_uuid)
        raise HTTPException(status_code=404, detail=f"Parcel with UUID '{parcel_uuid}' not found.")

    return data


# ---------------------------------------------------------------------------
# FEATURE 04: PARCEL VERSION HISTORY & AUDIT LEDGER
# ---------------------------------------------------------------------------

from backend.identity.version_history import (
    DuplicateVersionError,
    GeometryComparisonResult,
    NewVersionRequest,
    ParcelHistoryResponse,
    ParcelVersionRecord,
    VersionNotFoundError,
    get_version_history_service,
)


@router.get("/{parcel_uuid}/history", response_model=ParcelHistoryResponse)
def get_parcel_version_history(parcel_uuid: str):
    """
    GET /api/parcels/{uuid}/history

    Retrieves full chronological version timeline for a parcel.
    Guarantees immutable historical record: Version 1 (Cadastral), Version 2 (Drone), Version 3 (RTK/Surveyor).
    """
    history_svc = get_version_history_service()
    try:
        return history_svc.get_history(parcel_uuid)
    except VersionNotFoundError as e:
        id_svc = get_identity_service()
        for p in id_svc._parcels.values():
            if parcel_uuid in p.source_ids:
                return history_svc.get_history(p.parcel_uuid)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving parcel history: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{parcel_uuid}/versions/{version}")
def get_parcel_version_detail(
    parcel_uuid: str,
    version: int,
    compare_with: Optional[int] = Query(None, description="Optional version number to compare against (defaults to version - 1)"),
):
    """
    GET /api/parcels/{uuid}/versions/{version}

    Retrieves specific version detail including geometry, reviewer, decision, change reason,
    and mathematical geometry comparison against previous version:
    - area_change (diff m², % change)
    - boundary_change (metric IoU, symmetric difference area)
    - centroid_shift (metric distance, directional bearing)
    """
    history_svc = get_version_history_service()
    try:
        return history_svc.get_version_detail(parcel_uuid, version, compare_with=compare_with)
    except VersionNotFoundError as e:
        id_svc = get_identity_service()
        for p in id_svc._parcels.values():
            if parcel_uuid in p.source_ids:
                return history_svc.get_version_detail(p.parcel_uuid, version, compare_with=compare_with)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving parcel version detail: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{parcel_uuid}/new-version")
def create_new_parcel_version(parcel_uuid: str, payload: Dict[str, Any]):
    """
    POST /api/parcels/{uuid}/new-version

    Appends an immutable new version to the parcel ledger.
    Database Constraint: Enforces compound unique key (parcel_uuid, version_number).
    Rejects duplicate versions with HTTP 409 Conflict.
    Calculates metric geometry differences against previous version.
    """
    history_svc = get_version_history_service()
    id_svc = get_identity_service()
    target_uuid = parcel_uuid
    for p in id_svc._parcels.values():
        if parcel_uuid in p.source_ids:
            target_uuid = p.parcel_uuid
            break

    try:
        req = NewVersionRequest(**payload)
        new_record, comp = history_svc.create_new_version(target_uuid, req)
        res_dict = new_record.to_dict()
        if comp:
            res_dict["comparison_with_previous"] = comp.to_dict()
        return res_dict
    except DuplicateVersionError as dve:
        raise HTTPException(status_code=409, detail=str(dve))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("Error creating new version for %s: %s", parcel_uuid, e)
        raise HTTPException(status_code=500, detail=f"Failed to record version: {str(e)}")
