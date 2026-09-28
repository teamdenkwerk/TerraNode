"""
tests/test_crs.py

UNIT TESTS: CRS & SPATIAL REFERENCE SAFETY

Validates:
- Automatic UTM zone detection (Lon 77.6, Lat 12.9 -> UTM 43N)
- Metric distance calculation in meters (never computes Euclidean drift on degrees!)
- Metric area calculation
- Safe reprojection between EPSG:4326 and UTM
"""

import pytest
from shapely.geometry import box, Point
from backend.crs.transformer import (
    determine_utm_crs,
    metric_distance_between,
    metric_area,
    reproject_geometry,
    EPSG_4326,
)


def test_determine_utm_crs_bengaluru():
    # Bengaluru coordinates: Lon 77.64, Lat 12.97
    crs, zone = determine_utm_crs(77.64, 12.97)
    assert zone == 43
    assert crs == "EPSG:32643"


def test_determine_utm_crs_chennai():
    # Chennai coordinates: Lon 80.27, Lat 13.08
    crs, zone = determine_utm_crs(80.27, 13.08)
    assert zone == 44
    assert crs == "EPSG:32644"


def test_metric_distance_between():
    # Two points in Bengaluru separated by ~0.0001 deg (~11 meters)
    pt_a = Point(77.6400, 12.9700)
    pt_b = Point(77.6401, 12.9700)

    # In degrees, euclidean distance is 0.0001 (meaningless in meters)
    deg_dist = pt_a.distance(pt_b)
    assert deg_dist < 0.001

    # Safe metric distance should be approx 10.8 to 11.2 meters
    metric_dist = metric_distance_between(pt_a, pt_b, source_crs=EPSG_4326)
    assert 10.0 <= metric_dist <= 12.0


def test_metric_area():
    # Small box in Bengaluru (~22m x 22m ~ 484 sqm)
    b = box(77.6400, 12.9700, 77.6402, 12.9702)
    area_m2 = metric_area(b, source_crs=EPSG_4326)
    assert 400.0 <= area_m2 <= 600.0


def test_reprojection_roundtrip():
    pt = Point(77.6408, 12.9784)
    utm_pt = reproject_geometry(pt, "EPSG:4326", "EPSG:32643")
    assert utm_pt.x > 100000  # Projected coordinates in hundreds of thousands of meters
    back_pt = reproject_geometry(utm_pt, "EPSG:32643", "EPSG:4326")
    assert abs(back_pt.x - 77.6408) < 1e-5
    assert abs(back_pt.y - 12.9784) < 1e-5
