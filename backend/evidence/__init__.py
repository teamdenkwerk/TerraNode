"""
backend/evidence module
Enhancement 09: Unified Reconciliation Evidence & Explainability
"""

from backend.evidence.models import (
    ConfidenceEvidence,
    FinalDecisionCard,
    GeometricEvidence,
    GroundTruthEvidence,
    HistoricalEvidenceSummary,
    InfrastructureEvidenceSummary,
    MatchingEvidence,
    ReconciliationEvidence,
    ReviewEvent,
    SourceEvidenceItem,
)
from backend.evidence.service import (
    UnifiedEvidenceService,
    get_unified_evidence_service,
)
from backend.evidence.routes import router as evidence_router

__all__ = [
    "ConfidenceEvidence",
    "FinalDecisionCard",
    "GeometricEvidence",
    "GroundTruthEvidence",
    "HistoricalEvidenceSummary",
    "InfrastructureEvidenceSummary",
    "MatchingEvidence",
    "ReconciliationEvidence",
    "ReviewEvent",
    "SourceEvidenceItem",
    "UnifiedEvidenceService",
    "get_unified_evidence_service",
    "evidence_router",
]
