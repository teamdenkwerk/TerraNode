"""
backend/infrastructure/validators.py

Comprehensive spatial validation and geometry normalization engine for infrastructure features.
Enforces GeoJSON WGS84 standards [lon, lat], detects coordinate inversions, repairs invalid geometries,
and verifies city-specific geographic boundaries.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

logger = logging.getLogger(__name__)

# Expected geographic bounding boxes for Indian metropolitan areas [min_lon, min_lat, max_lon, max_lat]
CITY_BOUNDS = {
    "chennai": [79.80, 12.70, 80.40, 13.40],
    "bengaluru": [77.20, 12.70, 77.90, 13.30],
    "mumbai": [72.70, 18.80, 73.10, 19.40],
    "delhi": [76.80, 28.30, 77.40, 28.90],
}


def _validate_and_normalize_coords(coords: Any) -> Any:
    """
    Recursively validates and normalizes coordinate pairs.
    Detects and corrects inverted [lat, lon] coordinates to standard GeoJSON [lon, lat].
    """
    if isinstance(coords, (list, tuple)):
        if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
            x, y = float(coords[0]), float(coords[1])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(f"Non-finite coordinate encountered: ({x}, {y})")

            # In India: Longitude is roughly 68° to 98°, Latitude is roughly 8° to 38°
            # If x is in latitude range (8-38) and y is in longitude range (68-98), coordinates were passed as [lat, lon]
            if 8.0 <= x <= 38.0 and 68.0 <= y <= 98.0:
                logger.warning("Detected inverted coordinates [%f, %f] (lat, lon). Normalizing to standard GeoJSON [lon, lat] [%f, %f].", x, y, y, x)
                x, y = y, x

            if not (-180.0 <= x <= 180.0):
                raise ValueError(f"Longitude {x} is out of valid WGS84 range [-180, 180]")
            if not (-90.0 <= y <= 90.0):
                raise ValueError(f"Latitude {y} is out of valid WGS84 range [-90, 90]")

            return [x, y]
        return [_validate_and_normalize_coords(c) for c in coords]
    return coords


def validate_and_normalize_geometry(
    geom_dict: Dict[str, Any],
    city: Optional[str] = None,
) -> Tuple[Dict[str, Any], BaseGeometry]:
    """
    Validates, repairs, and normalizes a GeoJSON geometry dictionary.
    Returns:
        (normalized_geojson_dict, shapely_geometry_object)
    """
    if not isinstance(geom_dict, dict) or "type" not in geom_dict or "coordinates" not in geom_dict:
        raise ValueError("Invalid GeoJSON geometry structure. Must be a dict with 'type' and 'coordinates'.")

    normalized_coords = _validate_and_normalize_coords(geom_dict["coordinates"])
    normalized_dict = {
        "type": geom_dict["type"],
        "coordinates": normalized_coords,
    }

    try:
        s_geom = shape(normalized_dict)
    except Exception as e:
        raise ValueError(f"Failed to construct Shapely geometry: {e}")

    if s_geom.is_empty:
        raise ValueError("Geometry cannot be empty.")

    if not s_geom.is_valid:
        logger.info("Shapely geometry was invalid; applying make_valid().")
        s_geom = make_valid(s_geom)
        normalized_dict = mapping(s_geom)

    # Optional geographic bounding box verification
    if city:
        c_low = city.lower()
        matched_bounds = None
        for ckey, bounds in CITY_BOUNDS.items():
            if ckey in c_low:
                matched_bounds = bounds
                break

        if matched_bounds:
            min_x, min_y, max_x, max_y = s_geom.bounds
            b_min_x, b_min_y, b_max_x, b_max_y = matched_bounds
            if (min_x < b_min_x or max_x > b_max_x or min_y < b_min_y or max_y > b_max_y):
                logger.warning(
                    "Feature geometry bounds [%.4f, %.4f, %.4f, %.4f] are outside standard %s boundary [%.4f, %.4f, %.4f, %.4f].",
                    min_x, min_y, max_x, max_y, city, b_min_x, b_min_y, b_max_x, b_max_y
                )

    return normalized_dict, s_geom


def validate_infrastructure_payload(payload: Dict[str, Any]) -> None:
    """Validates geometry and required fields for an infrastructure feature."""
    if "geometry" not in payload:
        raise ValueError("Infrastructure payload must contain a valid 'geometry' field.")
    validate_and_normalize_geometry(payload["geometry"])
