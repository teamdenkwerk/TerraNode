"""
similarity.py

Pairwise similarity/scoring functions used by the matching engine to decide
whether a building footprint from source A (e.g. OSM) and source B (e.g.
Google Open Buildings / AI-extracted layer) refer to the same real-world
entity.

All geometries are expected as shapely geometries in a *projected* CRS
(metres), NOT lat/lon. Reproject upstream (see matching/normalize.py) before
calling anything here — IoU and distance math is meaningless in degrees.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shapely.geometry.base import BaseGeometry


# ---------------------------------------------------------------------------
# Geometry similarity
# ---------------------------------------------------------------------------

def iou(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Intersection-over-Union of two polygon geometries. Returns 0.0 for
    non-overlapping or degenerate geometries instead of raising."""
    if geom_a is None or geom_b is None:
        return 0.0
    if geom_a.is_empty or geom_b.is_empty:
        return 0.0
    if not geom_a.intersects(geom_b):
        return 0.0

    try:
        inter_area = geom_a.intersection(geom_b).area
        union_area = geom_a.union(geom_b).area
    except Exception:
        # Disciplined repair via geometry validator rather than blind buffer(0)
        from backend.geometry.validator import validate_and_repair_geometry
        res_a = validate_and_repair_geometry(geom_a)
        res_b = validate_and_repair_geometry(geom_b)
        if not res_a.is_valid or not res_b.is_valid:
            return 0.0
        geom_a = res_a.repaired_geometry or geom_a
        geom_b = res_b.repaired_geometry or geom_b
        if geom_a.is_empty or geom_b.is_empty or not geom_a.intersects(geom_b):
            return 0.0
        inter_area = geom_a.intersection(geom_b).area
        union_area = geom_a.union(geom_b).area

    if union_area == 0:
        return 0.0
    return inter_area / union_area


def centroid_distance(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Euclidean distance (metres, given a projected CRS) between centroids."""
    if geom_a is None or geom_b is None:
        return float("inf")
    ca, cb = geom_a.centroid, geom_b.centroid
    return ca.distance(cb)


def normalized_centroid_distance(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    max_dist: float = 15.0,
) -> float:
    """Centroid distance normalized to [0, 1], clipped at max_dist metres.

    max_dist should be roughly "the largest centroid offset between two
    footprints we'd still consider plausibly the same building" — typical
    building-footprint disagreement between OSM and satellite-derived
    sources is a few metres, so 15m is a reasonably generous default.
    """
    d = centroid_distance(geom_a, geom_b)
    if d == float("inf"):
        return 1.0
    return min(d / max_dist, 1.0)


# ---------------------------------------------------------------------------
# Attribute similarity
# ---------------------------------------------------------------------------

def _area_similarity(area_a: Optional[float], area_b: Optional[float]) -> float:
    """1.0 for identical areas, decaying toward 0 as the ratio diverges."""
    if not area_a or not area_b or area_a <= 0 or area_b <= 0:
        return 0.5  # unknown -> neutral, doesn't penalize or reward
    ratio = min(area_a, area_b) / max(area_a, area_b)
    return ratio


def attribute_similarity(attrs_a: dict, attrs_b: dict) -> float:
    """Combines whatever attribute-level signals are available on each
    source's schema. Sources rarely share the same tags, so this stays
    deliberately loose: area ratio is the one signal both OSM and Google
    Open Buildings can always provide (derivable from geometry). Building
    type / class agreement adds a bonus when both sources have it (e.g. OSM
    `building=house|yes|...` vs an AI-extracted class label).

    attrs_a / attrs_b: dicts with optional keys:
        - "area_m2": float
        - "building_type": str (already normalized to a common vocabulary
          by matching/normalize.py — e.g. "residential", "unknown")
    """
    area_sim = _area_similarity(attrs_a.get("area_m2"), attrs_b.get("area_m2"))

    type_a = attrs_a.get("building_type")
    type_b = attrs_b.get("building_type")
    if type_a and type_b and type_a != "unknown" and type_b != "unknown":
        type_sim = 1.0 if type_a == type_b else 0.0
        # area carries more signal than a coarse type tag
        return 0.75 * area_sim + 0.25 * type_sim

    return area_sim


# ---------------------------------------------------------------------------
# Combined score
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreWeights:
    w_iou: float = 0.5
    w_centroid: float = 0.3
    w_attribute: float = 0.2

    def __post_init__(self):
        total = self.w_iou + self.w_centroid + self.w_attribute
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"ScoreWeights must sum to 1.0, got {total}")


DEFAULT_WEIGHTS = ScoreWeights()


@dataclass(frozen=True)
class MatchScore:
    total: float
    iou: float
    centroid_component: float  # already (1 - normalized_distance)
    attribute: float


def combined_score(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    attrs_a: Optional[dict] = None,
    attrs_b: Optional[dict] = None,
    weights: ScoreWeights = DEFAULT_WEIGHTS,
    max_centroid_dist: float = 15.0,
) -> MatchScore:
    """Score(A,B) = w1*IoU + w2*(1 - normalized_centroid_distance) + w3*attribute_similarity

    Matches the formula agreed in the design doc. attrs_a/attrs_b default to
    {} so this can be called with geometry only.
    """
    attrs_a = attrs_a or {}
    attrs_b = attrs_b or {}

    iou_score = iou(geom_a, geom_b)
    centroid_component = 1.0 - normalized_centroid_distance(
        geom_a, geom_b, max_dist=max_centroid_dist
    )
    attr_score = attribute_similarity(attrs_a, attrs_b)

    total = (
        weights.w_iou * iou_score
        + weights.w_centroid * centroid_component
        + weights.w_attribute * attr_score
    )

    return MatchScore(
        total=total,
        iou=iou_score,
        centroid_component=centroid_component,
        attribute=attr_score,
    )