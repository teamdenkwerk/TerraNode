"""
backend/geometry/validator.py

PHASE 4: REAL GEOMETRY QUALITY ENGINE

Robust Shapely-based geometry validation and safe repair engine.
Ensures zero silent data corruption or unverified buffer(0) operations.

Features:
- Validates topological soundness (is_valid, is_empty, is_closed)
- Explains specific topological anomalies (self-intersection, nested holes)
- Executes disciplined repair via shapely.make_valid with fallbacks
- Calculates exact area changes and rejects repairs with area drift > 5%
- Detects geometry collapse (e.g. polygon collapsing into point/line)
- Returns structured GeometryValidationResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

logger = logging.getLogger(__name__)

# Maximum allowable area alteration before a repair is classified as unsafe
MAX_ALLOWABLE_AREA_CHANGE_PERCENT = 5.0


@dataclass
class GeometryValidationResult:
    is_valid: bool
    was_repaired: bool
    repair_method: Optional[str]
    original_area: float
    repaired_area: float
    area_change_percent: float
    geometry_type: str
    warning: Optional[str] = None
    error: Optional[str] = None
    repaired_geometry: Optional[BaseGeometry] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "was_repaired": self.was_repaired,
            "repair_method": self.repair_method,
            "original_area": round(self.original_area, 4),
            "repaired_area": round(self.repaired_area, 4),
            "area_change_percent": round(self.area_change_percent, 2),
            "geometry_type": self.geometry_type,
            "warning": self.warning,
            "error": self.error,
        }


def _extract_pure_polygonal(geom: BaseGeometry) -> Optional[BaseGeometry]:
    """Extracts polygons from MultiPolygon or GeometryCollection, discarding collapsed artifacts."""
    if isinstance(geom, Polygon):
        return geom if not geom.is_empty and geom.area > 0 else None
    if isinstance(geom, MultiPolygon):
        valid_parts = [p for p in geom.geoms if not p.is_empty and p.area > 0]
        if not valid_parts:
            return None
        return MultiPolygon(valid_parts) if len(valid_parts) > 1 else valid_parts[0]
    if isinstance(geom, GeometryCollection):
        polys = [g for g in geom.geoms if isinstance(g, (Polygon, MultiPolygon)) and not g.is_empty and g.area > 0]
        if not polys:
            return None
        if len(polys) == 1:
            return polys[0]
        flattened = []
        for p in polys:
            if isinstance(p, Polygon):
                flattened.append(p)
            elif isinstance(p, MultiPolygon):
                flattened.extend(p.geoms)
        return MultiPolygon(flattened) if len(flattened) > 1 else flattened[0]
    return None


def validate_and_repair_geometry(
    geom: BaseGeometry,
    max_area_change_pct: float = MAX_ALLOWABLE_AREA_CHANGE_PERCENT,
) -> GeometryValidationResult:
    """
    Validates and safely repairs a Shapely geometry without blind buffer(0).
    Rejects repairs that alter the area by more than max_area_change_pct or collapse geometry.
    """
    if geom is None:
        return GeometryValidationResult(
            is_valid=False,
            was_repaired=False,
            repair_method=None,
            original_area=0.0,
            repaired_area=0.0,
            area_change_percent=0.0,
            geometry_type="None",
            error="Geometry is null",
        )

    gtype = geom.geom_type
    if geom.is_empty:
        return GeometryValidationResult(
            is_valid=False,
            was_repaired=False,
            repair_method=None,
            original_area=0.0,
            repaired_area=0.0,
            area_change_percent=0.0,
            geometry_type=gtype,
            error="Geometry is empty",
        )

    orig_area = float(geom.area) if hasattr(geom, "area") else 0.0

    # 1. Check if already valid
    if geom.is_valid:
        if orig_area <= 0 and gtype in ("Polygon", "MultiPolygon"):
            return GeometryValidationResult(
                is_valid=False,
                was_repaired=False,
                repair_method=None,
                original_area=0.0,
                repaired_area=0.0,
                area_change_percent=0.0,
                geometry_type=gtype,
                error="Zero-area degenerate polygon",
            )
        return GeometryValidationResult(
            is_valid=True,
            was_repaired=False,
            repair_method=None,
            original_area=orig_area,
            repaired_area=orig_area,
            area_change_percent=0.0,
            geometry_type=gtype,
            repaired_geometry=geom,
        )

    # 2. Geometry is invalid — record the exact violation
    validity_reason = explain_validity(geom)
    logger.debug("Geometry validity issue: %s", validity_reason)

    # 3. Attempt disciplined repair
    repaired = None
    method = None

    try:
        from shapely import make_valid
        repaired = make_valid(geom)
        method = "shapely.make_valid"
    except (ImportError, Exception):
        try:
            repaired = geom.buffer(0)
            method = "buffer(0)"
        except Exception as e:
            return GeometryValidationResult(
                is_valid=False,
                was_repaired=False,
                repair_method=None,
                original_area=orig_area,
                repaired_area=0.0,
                area_change_percent=100.0,
                geometry_type=gtype,
                error=f"Unrepairable geometry violation: {validity_reason} ({str(e)})",
            )

    if repaired is None or repaired.is_empty:
        return GeometryValidationResult(
            is_valid=False,
            was_repaired=False,
            repair_method=method,
            original_area=orig_area,
            repaired_area=0.0,
            area_change_percent=100.0,
            geometry_type=gtype,
            error=f"Geometry collapsed to empty during repair: {validity_reason}",
        )

    # If original was a polygon, clean up mixed geometries from make_valid
    if gtype in ("Polygon", "MultiPolygon"):
        cleaned = _extract_pure_polygonal(repaired)
        if cleaned is None or cleaned.is_empty:
            return GeometryValidationResult(
                is_valid=False,
                was_repaired=False,
                repair_method=method,
                original_area=orig_area,
                repaired_area=0.0,
                area_change_percent=100.0,
                geometry_type=gtype,
                error=f"Polygon collapsed to non-polygonal dimension during repair: {validity_reason}",
            )
        repaired = cleaned

    repaired_area = float(repaired.area)
    if orig_area > 0:
        area_change = abs(repaired_area - orig_area) / orig_area * 100.0
    else:
        area_change = 0.0

    # 4. Check for unsafe area divergence
    if area_change > max_area_change_pct:
        return GeometryValidationResult(
            is_valid=False,
            was_repaired=False,
            repair_method=method,
            original_area=orig_area,
            repaired_area=repaired_area,
            area_change_percent=area_change,
            geometry_type=repaired.geom_type,
            error=f"Unsafe repair rejected: area altered by {area_change:.2f}% (exceeds threshold {max_area_change_pct:.1f}%). Original issue: {validity_reason}",
        )

    # 5. Successfully and safely repaired
    return GeometryValidationResult(
        is_valid=True,
        was_repaired=True,
        repair_method=method,
        original_area=orig_area,
        repaired_area=repaired_area,
        area_change_percent=area_change,
        geometry_type=repaired.geom_type,
        warning=f"Topological issue '{validity_reason}' repaired safely using {method} (area shift: {area_change:.2f}%).",
        repaired_geometry=repaired,
    )
