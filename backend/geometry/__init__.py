"""
backend/geometry package
"""
from backend.geometry.validator import (
    GeometryValidationResult,
    validate_and_repair_geometry,
    MAX_ALLOWABLE_AREA_CHANGE_PERCENT,
)

__all__ = [
    "GeometryValidationResult",
    "validate_and_repair_geometry",
    "MAX_ALLOWABLE_AREA_CHANGE_PERCENT",
]
