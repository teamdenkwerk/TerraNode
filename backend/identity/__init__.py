"""
backend/identity/__init__.py

TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY SYSTEM
"""

from backend.identity.models import (
    ParcelIdentityRecord,
    SourceRecordSnapshot,
    LineageEvent,
    ParcelStatus,
    ResolutionAction,
    ResolveIdentityRequest,
    IdentityResolutionResult,
    ResolveIdentityResponse,
)
from backend.identity.identity_service import (
    ParcelIdentityService,
    get_identity_service,
    TERRANODE_NAMESPACE,
)

__all__ = [
    "ParcelIdentityRecord",
    "SourceRecordSnapshot",
    "LineageEvent",
    "ParcelStatus",
    "ResolutionAction",
    "ResolveIdentityRequest",
    "IdentityResolutionResult",
    "ResolveIdentityResponse",
    "ParcelIdentityService",
    "get_identity_service",
    "TERRANODE_NAMESPACE",
]
