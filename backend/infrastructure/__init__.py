"""
backend/infrastructure module
Enhancement 07: Infrastructure / Utility Crossing Intelligence
"""

from backend.infrastructure.models import (
    InfrastructureFeature,
    InfrastructureIntersectionResult,
    InfrastructureLayerMeta,
    InfrastructureSummary,
    InfrastructureType,
    IntersectionTerminology,
    ParcelInfrastructureResponse,
    VerificationStatus,
)
from backend.infrastructure.service import (
    InfrastructureIntelligenceService,
    get_infrastructure_service,
)
from backend.infrastructure.repository import (
    InfrastructureRepository,
    get_infrastructure_repository,
)
from backend.infrastructure.routes import router as infrastructure_router

__all__ = [
    "InfrastructureFeature",
    "InfrastructureIntersectionResult",
    "InfrastructureLayerMeta",
    "InfrastructureSummary",
    "InfrastructureType",
    "IntersectionTerminology",
    "ParcelInfrastructureResponse",
    "VerificationStatus",
    "InfrastructureIntelligenceService",
    "get_infrastructure_service",
    "InfrastructureRepository",
    "get_infrastructure_repository",
    "infrastructure_router",
]
