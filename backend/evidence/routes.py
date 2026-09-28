"""
backend/evidence/routes.py

FastAPI endpoints for Enhancement 09: Unified Reconciliation Evidence & Explainability.

Endpoints:
- GET /api/parcels/{parcel_uuid}/evidence
- GET /api/reconciliation/{reconciliation_id}/evidence
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from backend.evidence.models import ReconciliationEvidence
from backend.evidence.service import get_unified_evidence_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reconciliation-evidence"])


@router.get("/api/parcels/{parcel_uuid}/evidence", response_model=ReconciliationEvidence)
def get_parcel_unified_evidence(parcel_uuid: str):
    """
    GET /api/parcels/{parcel_uuid}/evidence

    Synthesizes the complete 9-pillar Unified Reconciliation Evidence object for a parcel:
    1. Source Evidence
    2. Geometric Evidence
    3. Matching Evidence (8 independent signals)
    4. Confidence Score & Centralized Policy Evaluation
    5. Ground Truth (GNSS RTK / CORS)
    6. Historical Evidence & Version Continuity
    7. Infrastructure / Utility Crossing Overlap
    8. Review & State Machine Audit Trail
    9. Final Decision & Administrative Attribution
    """
    service = get_unified_evidence_service()
    evidence = service.get_parcel_evidence(parcel_uuid)
    if not evidence:
        raise HTTPException(status_code=404, detail=f"No reconciliation evidence found for parcel '{parcel_uuid}'.")
    return evidence


@router.get("/api/reconciliation/{reconciliation_id}/evidence", response_model=ReconciliationEvidence)
def get_reconciliation_evidence_by_id(reconciliation_id: str):
    """
    GET /api/reconciliation/{reconciliation_id}/evidence

    Retrieves reconciliation evidence by reconciliation ID or parcel UUID reference.
    """
    # Strip REC- prefix if present to find parcel
    raw_id = reconciliation_id.replace("REC-", "")
    service = get_unified_evidence_service()
    evidence = service.get_parcel_evidence(raw_id)
    if not evidence:
        # Try finding in registry by prefix
        for p in service.id_service._parcels.values():
            if p.parcel_uuid.upper().startswith(raw_id.upper()) or raw_id in p.source_ids:
                evidence = service.get_parcel_evidence(p.parcel_uuid)
                break

    if not evidence:
        raise HTTPException(status_code=404, detail=f"Reconciliation evidence '{reconciliation_id}' not found.")
    return evidence
