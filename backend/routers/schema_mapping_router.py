"""
backend/routers/schema_mapping_router.py

TERRANODE FEATURE 01: SMART SCHEMA MAPPING API ROUTER

Endpoints:
- POST /api/schema/mapping
- GET /api/schema/mapping/{dataset_id}
- POST /api/schema/mapping/{dataset_id}/confirm
- GET /api/datasets/{dataset_id}/schema
- POST /api/datasets/{dataset_id}/schema/mapping
- GET /api/datasets/{dataset_id}/schema/mapping
- POST /api/datasets/{dataset_id}/schema/validate
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Body

from backend.schema_mapping.mapping_models import (
    ConfirmMappingRequest,
    ConfirmedSchemaRecord,
    SchemaMappingRequest,
    SchemaMappingResponse,
)
from backend.schema_mapping.mapping_service import SchemaMappingService

router = APIRouter(tags=["schema-mapping"])
logger = logging.getLogger(__name__)

_SERVICE = SchemaMappingService()


@router.post("/api/schema/mapping", response_model=SchemaMappingResponse)
def generate_schema_mapping(body: SchemaMappingRequest):
    """
    Inspects columns from request payload, uploaded dataset file, or dataset ID,
    normalizes attribute names, runs configurable semantic dictionary matching,
    and returns suggestions with mathematically derived confidence scores.
    """
    dataset_id = body.dataset_id or "uploaded_dataset"
    try:
        response = _SERVICE.inspect_and_suggest(
            dataset_id=dataset_id,
            file_path=body.file_path,
            columns=body.columns,
            sample_records=body.sample_records,
        )
        return response
    except Exception as e:
        logger.error("Error generating schema mapping: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to generate schema mapping: {str(e)}")


@router.get("/api/schema/mapping/{dataset_id}", response_model=SchemaMappingResponse)
def get_schema_mapping_for_dataset(dataset_id: str):
    """
    Returns the schema mapping for a specific dataset, including confirmed mappings if previously saved.
    """
    try:
        response = _SERVICE.inspect_and_suggest(dataset_id=dataset_id)
        return response
    except Exception as e:
        logger.error("Error retrieving schema mapping for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve schema mapping: {str(e)}")


@router.post("/api/schema/mapping/{dataset_id}/confirm", response_model=ConfirmedSchemaRecord)
def confirm_schema_mapping(dataset_id: str, body: ConfirmMappingRequest):
    """
    Persists manual officer confirmation or rejection of suggested field mappings
    with dataset versioning and an immutable audit trail.
    """
    try:
        record = _SERVICE.confirm_mapping(dataset_id=dataset_id, request=body)
        return record
    except Exception as e:
        logger.error("Error confirming schema mapping for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to confirm schema mapping: {str(e)}")


# ---------------------------------------------------------------------------
# Problem Statement API Conformance: /api/datasets/{dataset_id}/schema/...
# ---------------------------------------------------------------------------

@router.get("/api/datasets/{dataset_id}/schema")
@router.get("/datasets/{dataset_id}/schema")
def get_dataset_schema(dataset_id: str):
    """
    GET /datasets/{dataset_id}/schema
    Retrieves the detected schema attributes and canonical mappings for dataset.
    """
    try:
        return _SERVICE.inspect_and_suggest(dataset_id=dataset_id)
    except Exception as e:
        logger.error("Error in get_dataset_schema for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/datasets/{dataset_id}/schema/mapping")
@router.get("/datasets/{dataset_id}/schema/mapping")
def get_dataset_schema_mapping(dataset_id: str):
    """
    GET /datasets/{dataset_id}/schema/mapping
    Retrieves the active schema mapping suggestions and saved confirmations.
    """
    try:
        return _SERVICE.inspect_and_suggest(dataset_id=dataset_id)
    except Exception as e:
        logger.error("Error in get_dataset_schema_mapping for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/datasets/{dataset_id}/schema/mapping")
@router.post("/datasets/{dataset_id}/schema/mapping")
def post_dataset_schema_mapping(
    dataset_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """
    POST /datasets/{dataset_id}/schema/mapping
    Saves or generates an updated mapping for the dataset with officer attribution.
    """
    try:
        mappings = payload.get("mappings")
        if mappings:
            req = ConfirmMappingRequest(
                dataset_version=payload.get("dataset_version", "v1.0"),
                confirmed_by=payload.get("confirmed_by", "Field / Land Officer"),
                mappings=mappings,
                notes=payload.get("notes"),
            )
            return _SERVICE.confirm_mapping(dataset_id=dataset_id, request=req)
        else:
            return _SERVICE.inspect_and_suggest(
                dataset_id=dataset_id,
                columns=payload.get("columns"),
                sample_records=payload.get("sample_records"),
            )
    except Exception as e:
        logger.error("Error in post_dataset_schema_mapping for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/datasets/{dataset_id}/schema/validate")
@router.post("/datasets/{dataset_id}/schema/validate")
def validate_dataset_schema(
    dataset_id: str,
    payload: Dict[str, Any] = Body(...),
):
    """
    POST /datasets/{dataset_id}/schema/validate
    Validates completeness of mapped schema (identifier presence, area, geometry).
    """
    try:
        mappings = payload.get("mappings") or {}
        return _SERVICE.validate_schema_mapping(dataset_id=dataset_id, mappings=mappings)
    except Exception as e:
        logger.error("Error in validate_dataset_schema for %s: %s", dataset_id, e)
        raise HTTPException(status_code=500, detail=str(e))
