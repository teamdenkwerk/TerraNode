"""
backend/geospatial/crs_intelligence.py

TERRANODE FEATURE 02 — LEGACY CRS INTELLIGENCE ENGINE

Extends TerraNode's PyProj-based spatial reference subsystem with advanced
diagnostic intelligence for historical, legacy, and mixed Indian cadastral records.

Capabilities:
1. Declared CRS Parsing & Strict PyProj Validation
2. High-Precision Coordinate Range & Magnitude Analysis
3. AOI Geographic Context & Administrative Correlation
4. Multi-Anomaly Inconsistency Detection:
   - Coordinate-range mismatch (e.g. declared projected metric, but coordinates are in degrees)
   - Coordinate-range overflow (e.g. declared geographic WGS84, but coordinates are in meters)
   - Invalid or unrecognized EPSG declarations
   - Missing CRS headers in legacy vectors
   - Local Cartesian survey grid / scan pixel coordinates
5. Deterministic, Non-Fabricated Confidence Scoring
6. Guardrail: Never silently assigns a CRS when confidence is low (< 0.75)
7. Full Audit Metadata Tracking:
   - original_crs, detected_crs, processing_crs, display_crs
   - crs_detection_method, crs_confidence, crs_warning
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pyproj
from pydantic import BaseModel, Field
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry

from backend.crs.transformer import (
    EPSG_4326,
    determine_utm_crs,
    reproject_geometry,
    get_transformer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# VERIFIED CRS DEFINITIONS (Survey of India & Standard EPSG Registry)
# Strictly zero invented historical mappings.
# ---------------------------------------------------------------------------

VERIFIED_CRS_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "EPSG:4326": {
        "name": "WGS 84 (Geographic 2D)",
        "type": "geographic",
        "units": "degrees",
        "bounds_lon": (-180.0, 180.0),
        "bounds_lat": (-90.0, 90.0),
        "india_bounds_lon": (68.0, 98.0),
        "india_bounds_lat": (6.0, 38.0),
        "description": "Standard Global Geographic Reference System (WGS 84)",
    },
    "EPSG:32642": {
        "name": "WGS 84 / UTM zone 42N",
        "type": "projected",
        "units": "meters",
        "utm_zone": 42,
        "central_meridian": 69.0,
        "description": "Western India / Gujarat / Rajasthan Sector UTM Zone 42N",
    },
    "EPSG:32643": {
        "name": "WGS 84 / UTM zone 43N",
        "type": "projected",
        "units": "meters",
        "utm_zone": 43,
        "central_meridian": 75.0,
        "description": "Western & Southern India UTM Zone 43N (Mumbai, Bengaluru, Goa, Kerala)",
    },
    "EPSG:32644": {
        "name": "WGS 84 / UTM zone 44N",
        "type": "projected",
        "units": "meters",
        "utm_zone": 44,
        "central_meridian": 81.0,
        "description": "Central & Southern India UTM Zone 44N (Chennai, Hyderabad, Delhi NCR)",
    },
    "EPSG:32645": {
        "name": "WGS 84 / UTM zone 45N",
        "type": "projected",
        "units": "meters",
        "utm_zone": 45,
        "central_meridian": 87.0,
        "description": "Eastern India UTM Zone 45N (Kolkata, Odisha, Bihar, West Bengal)",
    },
    "EPSG:32646": {
        "name": "WGS 84 / UTM zone 46N",
        "type": "projected",
        "units": "meters",
        "utm_zone": 46,
        "central_meridian": 93.0,
        "description": "Northeastern India UTM Zone 46N (Assam, Meghalaya, Tripura, Mizoram)",
    },
    "EPSG:7760": {
        "name": "WGS 84 / Delhi LCC (State Survey Grid)",
        "type": "projected",
        "units": "meters",
        "description": "Survey of India / State Official Lambert Conformal Conic Grid",
    },
    "EPSG:24379": {
        "name": "Kalianpur 1975 / India zone IIa",
        "type": "projected",
        "units": "meters",
        "description": "Survey of India Historical Cadastral Topographic Grid (Zone IIa)",
    },
    "EPSG:24380": {
        "name": "Kalianpur 1975 / India zone IIb",
        "type": "projected",
        "units": "meters",
        "description": "Survey of India Historical Cadastral Topographic Grid (Zone IIb)",
    },
    "EPSG:3857": {
        "name": "WGS 84 / Pseudo-Mercator",
        "type": "projected",
        "units": "meters",
        "description": "Web Mercator Auxiliary Sphere (Spherical Metric Grid)",
    },
}

# Verified regional centroid & AOI mapping
VERIFIED_AOI_MAPPING: Dict[str, str] = {
    "bengaluru": "EPSG:32643",
    "blr": "EPSG:32643",
    "domlur": "EPSG:32643",
    "mumbai": "EPSG:32643",
    "bom": "EPSG:32643",
    "andheri": "EPSG:32643",
    "chennai": "EPSG:32644",
    "maa": "EPSG:32644",
    "tnagar": "EPSG:32644",
    "hyderabad": "EPSG:32644",
    "hyd": "EPSG:32644",
    "delhi": "EPSG:32644",
    "del": "EPSG:32644",
    "kolkata": "EPSG:32645",
    "ccu": "EPSG:32645",
}


# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

class CRSDetectionMethod(str, Enum):
    DECLARED_AUTHORITATIVE = "DECLARED_AUTHORITATIVE"
    COORDINATE_EXTENT_ANALYSIS = "COORDINATE_EXTENT_ANALYSIS"
    AOI_CORRELATION = "AOI_CORRELATION"
    INCONSISTENCY_RESOLVED = "INCONSISTENCY_RESOLVED"
    HISTORICAL_MAPPING = "HISTORICAL_MAPPING"
    UNRESOLVED = "UNRESOLVED"


class TransformationStatus(str, Enum):
    READY = "READY"
    TRANSFORMED = "TRANSFORMED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    UNRESOLVED = "UNRESOLVED"


class CoordinateRange(BaseModel):
    min_x: float = Field(..., description="Minimum X (Longitude or Easting)")
    max_x: float = Field(..., description="Maximum X (Longitude or Easting)")
    min_y: float = Field(..., description="Minimum Y (Latitude or Northing)")
    max_y: float = Field(..., description="Maximum Y (Latitude or Northing)")
    units: str = Field(..., description="'degrees' | 'meters' | 'local_grid'")
    is_geographic: bool = Field(..., description="True if coordinates are in degree range")
    is_projected: bool = Field(..., description="True if coordinates are metric projection scale")
    sample_count: int = Field(..., description="Number of inspected vertices")


class CRSIntelligenceReport(BaseModel):
    dataset_id: str
    declared_crs: Optional[str] = None
    original_crs: Optional[str] = None
    detected_crs: str
    processing_crs: str
    display_crs: str = EPSG_4326
    coordinate_range: CoordinateRange
    crs_detection_method: CRSDetectionMethod
    crs_confidence: float = Field(..., ge=0.0, le=1.0)
    crs_warning: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    inconsistencies: List[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    transformation_status: TransformationStatus
    suggested_crs_options: List[Dict[str, Any]] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


# ---------------------------------------------------------------------------
# LEGACY CRS INTELLIGENCE SERVICE
# ---------------------------------------------------------------------------

class LegacyCRSIntelligence:
    """
    Production-grade CRS diagnostics and intelligence engine.
    Diagnoses legacy inconsistencies, missing metadata, and projected mismatches.
    """

    @staticmethod
    def validate_declared_crs(declared_crs: Optional[str]) -> Tuple[bool, Optional[str], Optional[pyproj.CRS]]:
        """
        Validates declared CRS using PyProj without inventing definitions.
        Returns: (is_valid, normalized_epsg_or_name, pyproj_crs_obj)
        """
        if not declared_crs or not str(declared_crs).strip():
            return False, None, None

        cleaned = str(declared_crs).strip()

        # Handle OGC URI prefixes: e.g. urn:ogc:def:crs:OGC:1.3:CRS84 -> EPSG:4326
        if "CRS84" in cleaned or "CRS:84" in cleaned or "4326" in cleaned:
            cleaned = EPSG_4326
        elif re.search(r"EPSG:?:?(\d+)", cleaned, re.IGNORECASE):
            m = re.search(r"EPSG:?:?(\d+)", cleaned, re.IGNORECASE)
            cleaned = f"EPSG:{m.group(1)}"

        try:
            crs_obj = pyproj.CRS.from_user_input(cleaned)
            epsg_code = crs_obj.to_epsg()
            norm = f"EPSG:{epsg_code}" if epsg_code else crs_obj.to_string()
            return True, norm, crs_obj
        except Exception:
            return False, cleaned, None

    @staticmethod
    def extract_coordinate_samples(features: List[Dict[str, Any]], max_vertices: int = 500) -> List[Tuple[float, float]]:
        """Extracts (x, y) coordinates from GeoJSON features."""
        samples: List[Tuple[float, float]] = []

        def _walk(coords: Any):
            if not coords or len(samples) >= max_vertices:
                return
            if isinstance(coords, (list, tuple)):
                if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                    samples.append((float(coords[0]), float(coords[1])))
                else:
                    for sub in coords:
                        _walk(sub)

        for feat in features:
            geom = feat.get("geometry")
            if geom and "coordinates" in geom:
                _walk(geom["coordinates"])
            if len(samples) >= max_vertices:
                break

        return samples

    @staticmethod
    def inspect_coordinate_range(coords: List[Tuple[float, float]]) -> CoordinateRange:
        """
        Calculates bounding values and identifies coordinate unit system.
        """
        if not coords:
            return CoordinateRange(
                min_x=0.0, max_x=0.0, min_y=0.0, max_y=0.0,
                units="unknown", is_geographic=False, is_projected=False, sample_count=0
            )

        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Geographic test: longitude within [-180, 180], latitude within [-90, 90]
        is_geo = (-180.0 <= min_x <= 180.0 and -180.0 <= max_x <= 180.0 and
                  -90.0 <= min_y <= 90.0 and -90.0 <= max_y <= 90.0)

        # Projected test: meters in hundreds of thousands or millions
        # Standard India UTM ranges: Easting 100,000 to 900,000; Northing 0 to 4,000,000
        # Web Mercator ranges: x, y in millions
        is_proj = (min_x > 1000.0 and min_y > 1000.0) or (abs(min_x) > 180.0 or abs(max_x) > 180.0 or abs(min_y) > 90.0 or abs(max_y) > 90.0)

        # Local grid test: e.g. 0 to 1000 without georeferencing
        if not is_geo and not is_proj:
            units = "local_grid"
        elif is_geo:
            units = "degrees"
        else:
            units = "meters"

        return CoordinateRange(
            min_x=round(min_x, 6),
            max_x=round(max_x, 6),
            min_y=round(min_y, 6),
            max_y=round(max_y, 6),
            units=units,
            is_geographic=is_geo,
            is_projected=is_proj,
            sample_count=len(coords),
        )

    def diagnose_and_report(
        self,
        dataset_id: str,
        declared_crs: Optional[str] = None,
        features: Optional[List[Dict[str, Any]]] = None,
        sample_coords: Optional[List[Tuple[float, float]]] = None,
        aoi_metadata: Optional[Dict[str, Any]] = None,
    ) -> CRSIntelligenceReport:
        """
        Executes complete CRS Intelligence workflow on a dataset.
        Identifies inconsistencies, computes confidence, and returns an authoritative report.
        """
        warnings: List[str] = []
        inconsistencies: List[str] = []
        suggested_options: List[Dict[str, Any]] = []

        # Step 1: Read declared CRS
        orig_crs = declared_crs
        if declared_crs and ("→" in str(declared_crs) or "->" in str(declared_crs)):
            orig_crs = str(declared_crs).split("→")[0].split("->")[0].strip()

        # Step 2: Validate declared CRS
        is_valid_declared, norm_declared, pyproj_crs = self.validate_declared_crs(declared_crs)

        # Step 3: Inspect coordinate ranges
        if not sample_coords and features:
            sample_coords = self.extract_coordinate_samples(features)

        coord_range = self.inspect_coordinate_range(sample_coords or [])

        # Step 4: Inspect AOI metadata
        aoi_name = ""
        aoi_crs = None
        if aoi_metadata:
            aoi_str = f"{aoi_metadata.get('city', '')} {aoi_metadata.get('aoi', '')} {aoi_metadata.get('name', '')}".lower()
            for key, crs_code in VERIFIED_AOI_MAPPING.items():
                if key in aoi_str:
                    aoi_name = key
                    aoi_crs = crs_code
                    break

        # Step 5: Detect Inconsistencies & Mismatches
        is_declared_geographic = False
        is_declared_projected = False

        if is_valid_declared and pyproj_crs:
            is_declared_geographic = pyproj_crs.is_geographic
            is_declared_projected = pyproj_crs.is_projected

        # Check for Coordinate-Range Mismatch (CRITICAL ANOMALY)
        # Case A: Declared projected metric (e.g. UTM / 3857), but coordinates are degree angles (e.g. 77.6, 12.9)
        if is_declared_projected and coord_range.is_geographic and coord_range.sample_count > 0:
            inconsistencies.append(
                f"Coordinate-range mismatch: Declared CRS '{norm_declared}' is projected (units: meters), "
                f"but coordinates are in geographic angular degrees [{coord_range.min_x}, {coord_range.max_x}]."
            )
            warnings.append(
                f"Declared projected CRS '{norm_declared}' is mismatched with degree coordinate values. "
                f"Coordinates indicate unprojected geographic data."
            )

        # Case B: Declared geographic degree (e.g. EPSG:4326), but coordinates exceed 180 (projected meters)
        if is_declared_geographic and coord_range.is_projected and coord_range.sample_count > 0:
            inconsistencies.append(
                f"Coordinate-range mismatch: Declared CRS '{norm_declared}' is geographic (units: degrees), "
                f"but coordinate values [{coord_range.min_x}, {coord_range.min_y}] exceed valid degree bounds."
            )
            warnings.append(
                f"Declared geographic CRS '{norm_declared}' contradicts large metric coordinate values."
            )

        # Case C: Declared CRS is completely missing
        if not declared_crs:
            warnings.append("Missing CRS metadata: Input dataset has no explicit CRS definition.")

        # Case D: Declared CRS is invalid / unparseable
        if declared_crs and not is_valid_declared:
            inconsistencies.append(f"Invalid CRS declaration: '{declared_crs}' is not a recognized EPSG or WKT definition.")
            warnings.append(f"Unrecognized CRS '{declared_crs}'. Automatic coordinate range fallback engaged.")

        # Step 6: Suggest likely CRS & calculate mathematically defensible confidence
        detected_crs = EPSG_4326
        detection_method = CRSDetectionMethod.UNRESOLVED
        confidence = 0.50
        requires_confirm = False

        # Scenario 1: Valid declared geographic CRS matching geographic degree coordinates
        if is_valid_declared and is_declared_geographic and coord_range.is_geographic:
            detected_crs = norm_declared or EPSG_4326
            detection_method = CRSDetectionMethod.DECLARED_AUTHORITATIVE
            confidence = 1.0
            transformation_status = TransformationStatus.READY

        # Scenario 2: Valid declared projected CRS matching projected metric coordinates
        elif is_valid_declared and is_declared_projected and coord_range.is_projected:
            detected_crs = norm_declared or "EPSG:32643"
            detection_method = CRSDetectionMethod.DECLARED_AUTHORITATIVE
            confidence = 1.0
            transformation_status = TransformationStatus.READY

        # Scenario 3: Declared projected but coordinates are degrees -> Resolve to EPSG:4326
        elif is_declared_projected and coord_range.is_geographic and coord_range.sample_count > 0:
            detected_crs = EPSG_4326
            detection_method = CRSDetectionMethod.INCONSISTENCY_RESOLVED
            confidence = 0.85
            requires_confirm = True  # Must prompt user because declared header was overridden
            transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
            suggested_options.append({"crs": EPSG_4326, "label": "WGS 84 (Geographic Degrees)", "confidence": 0.85})
            if norm_declared:
                suggested_options.append({"crs": norm_declared, "label": f"Declared ({norm_declared}) [Not Recommended]", "confidence": 0.20})

        # Scenario 4: Missing CRS, but coordinates are geographic degrees
        elif not declared_crs and coord_range.is_geographic and coord_range.sample_count > 0:
            # Check if coordinates fall within India extent (lon 68-98, lat 6-38)
            in_india = (68.0 <= coord_range.min_x <= 98.0 and 6.0 <= coord_range.min_y <= 38.0)
            if in_india:
                detected_crs = EPSG_4326
                detection_method = CRSDetectionMethod.COORDINATE_EXTENT_ANALYSIS
                confidence = 0.95
                transformation_status = TransformationStatus.READY
            else:
                detected_crs = EPSG_4326
                detection_method = CRSDetectionMethod.COORDINATE_EXTENT_ANALYSIS
                confidence = 0.85
                transformation_status = TransformationStatus.READY

        # Scenario 5: Missing or invalid CRS, but coordinates are projected UTM meters
        elif coord_range.is_projected and coord_range.sample_count > 0:
            if aoi_crs:
                detected_crs = aoi_crs
                detection_method = CRSDetectionMethod.AOI_CORRELATION
                confidence = 0.90
                transformation_status = TransformationStatus.READY
                suggested_options.append({"crs": aoi_crs, "label": f"Verified AOI Projection ({aoi_crs})", "confidence": 0.90})
            else:
                # Multiple UTM zones are possible across India (Zone 42N - 46N)
                # Never silently guess when uncertain!
                detected_crs = "EPSG:32643"  # Primary default but low confidence
                detection_method = CRSDetectionMethod.COORDINATE_EXTENT_ANALYSIS
                confidence = 0.65  # Below safe threshold of 0.75
                requires_confirm = True
                transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
                warnings.append("Projected coordinates detected without AOI context. Multiple UTM zones possible (Zone 42N to 46N). Confirmation required.")
                suggested_options.append({"crs": "EPSG:32643", "label": "UTM Zone 43N (West/South India - Mumbai, Bengaluru)", "confidence": 0.65})
                suggested_options.append({"crs": "EPSG:32644", "label": "UTM Zone 44N (Central/South - Chennai, Hyderabad, Delhi)", "confidence": 0.65})
                suggested_options.append({"crs": "EPSG:32645", "label": "UTM Zone 45N (East - Kolkata, Odisha)", "confidence": 0.60})

        # Scenario 6: Invalid declared CRS
        elif declared_crs and not is_valid_declared:
            if coord_range.is_geographic:
                detected_crs = EPSG_4326
                detection_method = CRSDetectionMethod.INCONSISTENCY_RESOLVED
                confidence = 0.80
                requires_confirm = True
                transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
            elif aoi_crs:
                detected_crs = aoi_crs
                detection_method = CRSDetectionMethod.AOI_CORRELATION
                confidence = 0.80
                requires_confirm = True
                transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
            else:
                detected_crs = EPSG_4326
                detection_method = CRSDetectionMethod.UNRESOLVED
                confidence = 0.30
                requires_confirm = True
                transformation_status = TransformationStatus.UNRESOLVED

        # Scenario 7: Local arbitrary / scanned grid
        else:
            detected_crs = "LOCAL_GRID"
            detection_method = CRSDetectionMethod.UNRESOLVED
            confidence = 0.20
            requires_confirm = True
            transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
            warnings.append("Coordinates appear to be local cadastre sheet grid or scanned raster pixels. Tie-point georeferencing required.")

        # Step 7 & 8: Determine processing CRS (metric UTM)
        if coord_range.is_geographic and coord_range.sample_count > 0:
            center_lon = (coord_range.min_x + coord_range.max_x) / 2.0
            center_lat = (coord_range.min_y + coord_range.max_y) / 2.0
            processing_crs, _ = determine_utm_crs(center_lon, center_lat)
        elif aoi_crs:
            processing_crs = aoi_crs
        elif is_declared_projected and is_valid_declared and norm_declared:
            processing_crs = norm_declared
        else:
            processing_crs = "EPSG:32643"

        # Final safety checks
        if confidence < 0.75:
            requires_confirm = True
            if transformation_status == TransformationStatus.READY:
                transformation_status = TransformationStatus.REQUIRES_CONFIRMATION

        main_warning = warnings[0] if warnings else None

        return CRSIntelligenceReport(
            dataset_id=dataset_id,
            declared_crs=declared_crs,
            original_crs=orig_crs,
            detected_crs=detected_crs,
            processing_crs=processing_crs,
            display_crs=EPSG_4326,
            coordinate_range=coord_range,
            crs_detection_method=detection_method,
            crs_confidence=round(confidence, 3),
            crs_warning=main_warning,
            warnings=warnings,
            inconsistencies=inconsistencies,
            requires_confirmation=requires_confirm,
            transformation_status=transformation_status,
            suggested_crs_options=suggested_options,
        )

    def transform_geometry_safely(
        self,
        geom: BaseGeometry,
        source_crs: str,
        target_crs: str,
    ) -> BaseGeometry:
        """
        Executes disciplined geometric reprojection using PyProj transformer.
        Preserves topological validity without altering vertex precision.
        """
        if geom is None or geom.is_empty:
            return geom
        if source_crs == target_crs:
            return geom

        return reproject_geometry(geom, from_crs=source_crs, to_crs=target_crs)
