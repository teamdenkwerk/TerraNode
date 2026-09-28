"""
backend/infrastructure/intersection.py

Exact metric spatial intersection and proximity engine for parcel vs infrastructure features.
All distance, length, and area calculations strictly execute in projected metric UTM CRS.
Zero distance/area math is ever evaluated on angular degrees (EPSG:4326).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry

from backend.crs.transformer import determine_utm_crs, reproject_geometry
from backend.infrastructure.models import (
    InfrastructureFeature,
    InfrastructureIntersectionResult,
    InfrastructureType,
    IntersectionTerminology,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate_single_intersection(
    parcel_geom_4326: BaseGeometry,
    infra_feature: InfrastructureFeature,
    infra_geom_4326: BaseGeometry,
    projected_crs: Optional[str] = None,
) -> InfrastructureIntersectionResult:
    """
    Computes precise metric intersection and proximity between parcel and infrastructure feature.
    """
    # Determine appropriate UTM zone if not provided
    centroid = parcel_geom_4326.centroid
    if not projected_crs:
        projected_crs, _ = determine_utm_crs(centroid.x, centroid.y)

    # Reproject to metric UTM CRS
    p_utm = reproject_geometry(parcel_geom_4326, from_crs="EPSG:4326", to_crs=projected_crs)
    i_utm = reproject_geometry(infra_geom_4326, from_crs="EPSG:4326", to_crs=projected_crs)

    parcel_area_m2 = p_utm.area if not p_utm.is_empty else 1.0

    intersects = p_utm.intersects(i_utm)

    if intersects:
        inter_geom = p_utm.intersection(i_utm)
        inter_len_m = 0.0
        inter_area_m2 = 0.0
        inter_pct = 0.0

        geom_type = inter_geom.geom_type
        if "Line" in geom_type:
            inter_len_m = round(float(inter_geom.length), 2)
            # Line intersection has 0 area
            inter_area_m2 = 0.0
            inter_pct = round((inter_len_m / max(1.0, p_utm.length)) * 100.0, 2)
        elif "Polygon" in geom_type:
            inter_area_m2 = round(float(inter_geom.area), 2)
            inter_len_m = round(float(inter_geom.length), 2)
            inter_pct = round((inter_area_m2 / max(0.1, parcel_area_m2)) * 100.0, 2)
        elif "GeometryCollection" in geom_type:
            # Handle collection with both lines and polygons
            poly_parts = [g for g in inter_geom.geoms if "Polygon" in g.geom_type]
            line_parts = [g for g in inter_geom.geoms if "Line" in g.geom_type]
            if poly_parts:
                inter_area_m2 = round(float(sum(p.area for p in poly_parts)), 2)
                inter_pct = round((inter_area_m2 / max(0.1, parcel_area_m2)) * 100.0, 2)
            if line_parts:
                inter_len_m = round(float(sum(l.length for l in line_parts)), 2)

        # Neutral status selection
        if infra_feature.infrastructure_type in (InfrastructureType.WATER, InfrastructureType.ELECTRICITY, InfrastructureType.PUBLIC_UTILITY):
            status = IntersectionTerminology.UTILITY_INTERSECTION.value
        elif "Polygon" in geom_type and inter_area_m2 > 0:
            status = IntersectionTerminology.OVERLAP_DETECTED.value
        else:
            status = IntersectionTerminology.INTERSECTION_DETECTED.value

        return InfrastructureIntersectionResult(
            infrastructure_type=infra_feature.infrastructure_type.value,
            infrastructure_id=infra_feature.infrastructure_id,
            intersection_exists=True,
            intersection_status=status,
            intersection_length_m=inter_len_m,
            intersection_area_m2=inter_area_m2,
            intersection_percentage=inter_pct,
            minimum_distance_m=0.0,
            source_dataset=infra_feature.source_dataset_id,
            source_feature_id=infra_feature.source_feature_id,
            source_name=infra_feature.source_name,
            verification_status=infra_feature.verification_status.value,
            calculation_timestamp=_now_iso(),
            details={
                "projected_crs": projected_crs,
                "intersection_geom_type": geom_type,
                "metadata": infra_feature.metadata,
            },
        )
    else:
        # Distance calculation
        min_dist_m = round(float(p_utm.distance(i_utm)), 2)
        if min_dist_m < 25.0:
            status = IntersectionTerminology.PROXIMITY_DETECTED.value
        else:
            status = IntersectionTerminology.NO_INTERSECTION.value

        return InfrastructureIntersectionResult(
            infrastructure_type=infra_feature.infrastructure_type.value,
            infrastructure_id=infra_feature.infrastructure_id,
            intersection_exists=False,
            intersection_status=status,
            intersection_length_m=0.0,
            intersection_area_m2=0.0,
            intersection_percentage=0.0,
            minimum_distance_m=min_dist_m,
            source_dataset=infra_feature.source_dataset_id,
            source_feature_id=infra_feature.source_feature_id,
            source_name=infra_feature.source_name,
            verification_status=infra_feature.verification_status.value,
            calculation_timestamp=_now_iso(),
            details={
                "projected_crs": projected_crs,
                "proximity_threshold_m": 25.0,
                "metadata": infra_feature.metadata,
            },
        )
