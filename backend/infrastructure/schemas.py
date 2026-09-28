"""
backend/infrastructure/schemas.py

Pydantic schemas for infrastructure query parameters and responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.infrastructure.models import (
    InfrastructureIntersectionResult,
    InfrastructureLayerMeta,
    InfrastructureSummary,
    ParcelInfrastructureResponse,
)

__all__ = [
    "InfrastructureIntersectionResult",
    "InfrastructureLayerMeta",
    "InfrastructureSummary",
    "ParcelInfrastructureResponse",
]
