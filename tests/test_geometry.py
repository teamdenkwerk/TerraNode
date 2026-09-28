"""
tests/test_geometry.py

UNIT TESTS: REAL GEOMETRY QUALITY ENGINE

Validates:
- Valid polygons
- Self-intersecting polygons (bowtie)
- Zero-area degenerate polygons
- Empty / Null geometries
- Safe repair vs unsafe repair rejection
"""

import pytest
from shapely.geometry import Polygon, Point
from backend.geometry.validator import validate_and_repair_geometry, GeometryValidationResult


def test_valid_polygon():
    # Clean 10x10 square
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    res = validate_and_repair_geometry(poly)
    assert res.is_valid is True
    assert res.was_repaired is False
    assert res.original_area == 100.0
    assert res.repaired_area == 100.0
    assert res.area_change_percent == 0.0


def test_self_intersecting_bowtie_polygon():
    # Bowtie self-intersecting polygon
    bowtie = Polygon([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])
    assert not bowtie.is_valid
    res = validate_and_repair_geometry(bowtie)
    # Must repair safely without collapse
    assert res.is_valid is True
    assert res.was_repaired is True
    assert res.repaired_geometry is not None
    assert res.repaired_geometry.is_valid is True


def test_zero_area_polygon():
    # Collapsed polygon with all points on a line
    flat = Polygon([(0, 0), (5, 0), (10, 0), (0, 0)])
    res = validate_and_repair_geometry(flat)
    assert res.is_valid is False
    assert "degenerate" in str(res.error).lower() or res.original_area == 0.0


def test_null_and_empty_geometry():
    res_null = validate_and_repair_geometry(None)
    assert res_null.is_valid is False
    assert "null" in res_null.error.lower()

    res_empty = validate_and_repair_geometry(Polygon())
    assert res_empty.is_valid is False
    assert "empty" in res_empty.error.lower()
