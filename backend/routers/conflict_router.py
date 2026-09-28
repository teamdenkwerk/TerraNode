"""
backend/routers/conflict_router.py

TERRANODE FEATURE 05 — CONFLICT LIFECYCLE REST API

Endpoints:
  GET  /api/conflicts
  POST /api/conflicts
  GET  /api/conflicts/{id}
  POST /api/conflicts/{id}/transition
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from backend.conflicts.state_machine import (
    ConflictNotFoundError,
    ConflictRecord,
    ConflictState,
    CreateConflictRequest,
    InvalidTransitionError,
    TransitionRequest,
    get_conflict_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conflicts", tags=["conflicts"])


@router.get("", response_model=List[Dict[str, Any]])
def list_conflicts(
    state: Optional[ConflictState] = Query(None, description="Filter by current conflict state"),
    severity: Optional[str] = Query(None, description="Filter by severity: HIGH, MEDIUM, LOW"),
    parcel_uuid: Optional[str] = Query(None, description="Filter by parcel UUID or source ID"),
):
    """
    GET /api/conflicts

    Lists all active and historical conflicts with their current state and allowed transitions.
    """
    service = get_conflict_service()
    conflicts = service.list_conflicts(state=state, severity=severity, parcel_uuid=parcel_uuid)
    return [c.to_dict() for c in conflicts]


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_conflict(request: CreateConflictRequest):
    """
    POST /api/conflicts

    Registers a new conflict in DETECTED state.
    """
    service = get_conflict_service()
    record = service.create_conflict(request)
    return record.to_dict()


@router.get("/{conflict_id}", response_model=Dict[str, Any])
def get_conflict_by_id(conflict_id: str):
    """
    GET /api/conflicts/{id}

    Retrieves a conflict record by its conflict_id or parcel reference.
    Includes current state, allowed next transitions, and full immutable audit timeline.
    """
    service = get_conflict_service()
    try:
        record = service.get_conflict(conflict_id)
        return record.to_dict()
    except ConflictNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Error retrieving conflict '%s': %s", conflict_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{conflict_id}/transition", response_model=Dict[str, Any])
def transition_conflict(conflict_id: str, request: TransitionRequest):
    """
    POST /api/conflicts/{id}/transition

    Executes a verified state transition on a conflict.
    Validates against the finite state machine transition table.

    Rejects invalid transitions with HTTP 400 Bad Request.
    Records parcel_uuid, previous_state, new_state, actor, timestamp, reason, and evidence.
    """
    service = get_conflict_service()
    try:
        updated = service.transition(conflict_id, request)
        return updated.to_dict()
    except ConflictNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_STATE_TRANSITION",
                "message": str(e),
                "current_state": e.current_state.value,
                "requested_state": e.requested_state.value,
                "allowed_transitions": sorted([s.value for s in e.allowed_states]),
            },
        )
    except Exception as e:
        logger.error("Error transitioning conflict '%s': %s", conflict_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
