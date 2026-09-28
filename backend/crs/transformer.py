"""
backend/crs/transformer.py

PHASE 3: CRS AND SPATIAL REFERENCE SAFETY ENGINE

Ensures zero metric calculations are performed directly on angular degrees (EPSG:4326).
Automatically detects source CRS, derives appropriate projected UTM CRS based on AOI centroid,
and tracks:
    - original_crs
    - processing_crs (projected UTM / metric)
    - display_crs (EPSG:4326 for web maps)
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import pyproj
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform

logger = logging.getLogger(__name__)

# Standard Interchange & Display CRS
EPSG_4326 = "EPSG:4326"


@dataclass
class DatasetCRSTracker:
    original_crs: str
    processing_crs: str
    display_crs: str = EPSG_4326
    utm_zone: int = 43
    is_projected: bool = False
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def determine_utm_crs(lon: float, lat: float) -> Tuple[str, int]:
    """
    Computes standard UTM EPSG projection from geographic coordinates (WGS84 lon/lat).
    Returns (epsg_string, zone_number).
    e.g. Lon 77.6, Lat 12.9 -> ("EPSG:32643", 43)
    """
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))
    if lat >= 0:
        epsg = f"EPSG:{32600 + zone}"
    else:
        epsg = f"EPSG:{32700 + zone}"
    return epsg, zone


def detect_crs_from_payload(
    geojson_payload: Optional[Dict[str, Any]] = None,
    prj_wkt: Optional[str] = None,
    sample_coords: Optional[List[Tuple[float, float]]] = None,
) -> str:
    """
    Detects source CRS from GeoJSON metadata, ESRI .prj WKT, or coordinate magnitude analysis.
    """
    # 1. Inspect PRJ WKT if present
    if prj_wkt and prj_wkt.strip():
        try:
            crs_obj = pyproj.CRS.from_wkt(prj_wkt)
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            return crs_obj.to_string()
        except Exception as e:
            logger.warning("Failed to parse PRJ WKT: %s", e)

    # 2. Inspect GeoJSON CRS dictionary
    if geojson_payload and "crs" in geojson_payload:
        crs_meta = geojson_payload["crs"]
        if isinstance(crs_meta, dict):
            props = crs_meta.get("properties", {})
            name = props.get("name", "")
            match = re.search(r"EPSG:?:(\d+)", name, re.IGNORECASE)
            if match:
                return f"EPSG:{match.group(1)}"
            if "CRS84" in name or "4326" in name:
                return EPSG_4326

    # 3. Coordinate range inference
    if sample_coords and len(sample_coords) > 0:
        xs = [c[0] for c in sample_coords]
        ys = [c[1] for c in sample_coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Standard Geographic coordinates (lon in [-180, 180], lat in [-90, 90])
        if -180.0 <= min_x <= 180.0 and -180.0 <= max_x <= 180.0 and -90.0 <= min_y <= 90.0 and -90.0 <= max_y <= 90.0:
            return EPSG_4326

        # Check for UTM false easting/northing ranges (typically x in [100,000, 900,000] and y in [0, 10,000,000])
        if 100000 <= min_x <= 900000 and 0 <= min_y <= 10000000:
            return "EPSG:32643"  # Standard default projected UTM for India sector

    return EPSG_4326


def create_crs_tracker(
    source_crs: str,
    centroid_lon: float,
    centroid_lat: float,
) -> DatasetCRSTracker:
    """
    Builds a DatasetCRSTracker with source, processing (metric UTM), and display CRS.
    """
    utm_epsg, zone = determine_utm_crs(centroid_lon, centroid_lat)
    is_proj = (source_crs != EPSG_4326)

    return DatasetCRSTracker(
        original_crs=source_crs,
        processing_crs=utm_epsg,
        display_crs=EPSG_4326,
        utm_zone=zone,
        is_projected=is_proj,
        notes=f"Auto-selected UTM Zone {zone} ({utm_epsg}) for metric metrology.",
    )


def get_transformer(from_crs: str, to_crs: str) -> pyproj.Transformer:
    """Returns a PyProj Transformer configured with always_xy=True."""
    return pyproj.Transformer.from_crs(from_crs, to_crs, always_xy=True)


def reproject_geometry(
    geom: BaseGeometry,
    from_crs: str,
    to_crs: str,
) -> BaseGeometry:
    """
    Reprojects a Shapely geometry from one CRS to another.
    If from_crs equals to_crs, returns unchanged geom.
    """
    if from_crs == to_crs:
        return geom
    transformer = get_transformer(from_crs, to_crs)
    return shapely_transform(transformer.transform, geom)


def metric_distance_between(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    source_crs: str = EPSG_4326,
    processing_crs: Optional[str] = None,
) -> float:
    """
    Safely computes centroid distance in METERS.
    Never evaluates Euclidean distance directly on angular degrees.
    """
    if geom_a is None or geom_b is None or geom_a.is_empty or geom_b.is_empty:
        return float("inf")

    c_a = geom_a.centroid
    c_b = geom_b.centroid

    if processing_crs is None:
        if source_crs == EPSG_4326:
            processing_crs, _ = determine_utm_crs(c_a.x, c_a.y)
        else:
            processing_crs = source_crs

    # Project to metric CRS
    proj_a = reproject_geometry(c_a, source_crs, processing_crs)
    proj_b = reproject_geometry(c_b, source_crs, processing_crs)

    return float(proj_a.distance(proj_b))


def metric_area(
    geom: BaseGeometry,
    source_crs: str = EPSG_4326,
    processing_crs: Optional[str] = None,
) -> float:
    """
    Safely computes polygon area in SQUARE METERS.
    """
    if geom is None or geom.is_empty:
        return 0.0

    if processing_crs is None:
        if source_crs == EPSG_4326:
            c = geom.centroid
            processing_crs, _ = determine_utm_crs(c.x, c.y)
        else:
            processing_crs = source_crs

    proj_geom = reproject_geometry(geom, source_crs, processing_crs)
    return float(proj_geom.area)
