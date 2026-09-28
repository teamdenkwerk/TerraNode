"""
backend/ml/features.py

PHASE 8: ML-READY FEATURE EXTRACTION PIPELINE

Extracts strictly non-leaking geometric, topological, and inter-source features
from candidate parcel pairs and consensus clusters.

Features Extracted (12 Total):
1. iou: Geometric Intersection-over-Union [0, 1]
2. centroid_drift_m: Distance between centroids in meters
3. area_difference_pct: Relative difference in area (%)
4. perimeter_difference_pct: Relative difference in boundary length (%)
5. shape_compactness_a: Polsby-Popper compactness of geometry A
6. shape_compactness_b: Polsby-Popper compactness of geometry B
7. vertex_count_a: Number of boundary vertices in A
8. vertex_count_b: Number of boundary vertices in B
9. overlap_ratio_a: Intersection area divided by area A
10. overlap_ratio_b: Intersection area divided by area B
11. source_count: Number of independent sources
12. extraction_quality: Source AI/survey extraction confidence [0, 1]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from shapely.geometry.base import BaseGeometry
from matching.similarity import iou, centroid_distance


@dataclass
class ParcelFeatureVector:
    iou: float
    centroid_drift_m: float
    area_difference_pct: float
    perimeter_difference_pct: float
    shape_compactness_a: float
    shape_compactness_b: float
    vertex_count_a: int
    vertex_count_b: int
    overlap_ratio_a: float
    overlap_ratio_b: float
    source_count: int
    extraction_quality: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_feature_list(self) -> List[float]:
        return [
            self.iou,
            self.centroid_drift_m,
            self.area_difference_pct,
            self.perimeter_difference_pct,
            self.shape_compactness_a,
            self.shape_compactness_b,
            float(self.vertex_count_a),
            float(self.vertex_count_b),
            self.overlap_ratio_a,
            self.overlap_ratio_b,
            float(self.source_count),
            self.extraction_quality,
        ]


def _compactness(geom: BaseGeometry) -> float:
    """Polsby-Popper compactness: 4 * pi * Area / Perimeter^2 (1.0 for a circle)."""
    if geom is None or geom.is_empty or geom.length == 0:
        return 0.0
    return float((4.0 * math.pi * geom.area) / (geom.length ** 2))


def _vertex_count(geom: BaseGeometry) -> int:
    """Counts exterior boundary vertices."""
    if geom is None or geom.is_empty:
        return 0
    if hasattr(geom, "exterior") and geom.exterior:
        return len(geom.exterior.coords)
    return 0


def extract_pairwise_features(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    source_count: int = 2,
    extraction_quality: float = 0.85,
) -> ParcelFeatureVector:
    """
    Extracts 12 structured features from two projected (metric) geometries.
    """
    if geom_a is None or geom_b is None or geom_a.is_empty or geom_b.is_empty:
        return ParcelFeatureVector(
            iou=0.0,
            centroid_drift_m=999.0,
            area_difference_pct=100.0,
            perimeter_difference_pct=100.0,
            shape_compactness_a=0.0,
            shape_compactness_b=0.0,
            vertex_count_a=0,
            vertex_count_b=0,
            overlap_ratio_a=0.0,
            overlap_ratio_b=0.0,
            source_count=source_count,
            extraction_quality=extraction_quality,
        )

    val_iou = iou(geom_a, geom_b)
    drift_m = centroid_distance(geom_a, geom_b)

    area_a = float(geom_a.area)
    area_b = float(geom_b.area)
    max_area = max(area_a, area_b)
    area_diff_pct = (abs(area_a - area_b) / max_area * 100.0) if max_area > 0 else 0.0

    len_a = float(geom_a.length)
    len_b = float(geom_b.length)
    max_len = max(len_a, len_b)
    len_diff_pct = (abs(len_a - len_b) / max_len * 100.0) if max_len > 0 else 0.0

    inter_geom = geom_a.intersection(geom_b) if geom_a.intersects(geom_b) else None
    inter_area = float(inter_geom.area) if inter_geom and not inter_geom.is_empty else 0.0

    overlap_a = (inter_area / area_a) if area_a > 0 else 0.0
    overlap_b = (inter_area / area_b) if area_b > 0 else 0.0

    return ParcelFeatureVector(
        iou=round(val_iou, 4),
        centroid_drift_m=round(drift_m, 3),
        area_difference_pct=round(area_diff_pct, 2),
        perimeter_difference_pct=round(len_diff_pct, 2),
        shape_compactness_a=round(_compactness(geom_a), 4),
        shape_compactness_b=round(_compactness(geom_b), 4),
        vertex_count_a=_vertex_count(geom_a),
        vertex_count_b=_vertex_count(geom_b),
        overlap_ratio_a=round(overlap_a, 4),
        overlap_ratio_b=round(overlap_b, 4),
        source_count=source_count,
        extraction_quality=round(extraction_quality, 4),
    )
