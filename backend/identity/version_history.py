"""
backend/identity/version_history.py

TERRANODE FEATURE 04 — PARCEL VERSION HISTORY & AUDIT LEDGER

Implements an immutable, append-only version history system for TerraNode land entities.
Guarantees:
1. Historical geospatial decisions and geometries are never overwritten.
2. Every meaningful change produces a new, monotonically incremented version.
3. Database constraint: Compound unique key (parcel_uuid, version_number) prevents accidental duplicates.
4. Comprehensive geometric comparison between versions:
   - area_change (absolute m², percent change)
   - boundary_change (metric IoU, symmetric difference area, perimeter change)
   - centroid_shift (metric distance in meters, directional bearing)
5. Full attribution: Who approved it, why it changed, decision classification, and review status.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field
from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry

from backend.crs.transformer import determine_utm_crs, reproject_geometry
from backend.geometry.validator import validate_and_repair_geometry

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PARCELS_DIR = DATA_DIR / "parcels"
HISTORY_STORAGE_FILE = PARCELS_DIR / "version_history.json"


def _now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CUSTOM EXCEPTIONS
# ---------------------------------------------------------------------------

class DuplicateVersionError(Exception):
    """Raised when an attempt is made to insert an existing (parcel_uuid, version_number)."""
    pass


class VersionNotFoundError(Exception):
    """Raised when a requested version does not exist."""
    pass


# ---------------------------------------------------------------------------
# DATA MODELS
# ---------------------------------------------------------------------------

class AreaChangeComparison(BaseModel):
    area_a_m2: float = Field(..., description="Area of earlier version A in square meters")
    area_b_m2: float = Field(..., description="Area of later version B in square meters")
    diff_m2: float = Field(..., description="Absolute area change (B - A) in square meters")
    percent_change: float = Field(..., description="Percentage change in area")


class BoundaryChangeComparison(BaseModel):
    metric_iou: float = Field(..., description="Intersection over Union agreement (0.0 to 1.0)")
    symmetric_difference_m2: float = Field(..., description="Area of non-overlapping discrepancy in square meters")
    has_boundary_change: bool = Field(..., description="True if geometries are not identical")
    perimeter_a_m: float = Field(..., description="Perimeter of version A in meters")
    perimeter_b_m: float = Field(..., description="Perimeter of version B in meters")


class CentroidShiftComparison(BaseModel):
    centroid_a: List[float] = Field(..., description="[lat, lon] of version A")
    centroid_b: List[float] = Field(..., description="[lat, lon] of version B")
    distance_m: float = Field(..., description="Shift distance in meters")
    bearing_deg: Optional[float] = Field(None, description="Compass bearing of shift (0-360 degrees)")


class GeometryComparisonResult(BaseModel):
    version_a: int
    version_b: int
    area_change: AreaChangeComparison
    boundary_change: BoundaryChangeComparison
    centroid_shift: CentroidShiftComparison
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class ParcelVersionRecord(BaseModel):
    """
    Immutable version snapshot for a land parcel entity.
    """
    parcel_uuid: str = Field(..., description="Permanent internal parcel UUID")
    version_number: int = Field(..., ge=1, description="Monotonically increasing version counter")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry definition")
    source_datasets: List[str] = Field(default_factory=list, description="Contributing datasets")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    IoU: Optional[float] = Field(None, ge=0.0, le=1.0, description="IoU relative to previous version or reference")
    centroid_drift: Optional[float] = Field(None, ge=0.0, description="Centroid drift in meters")
    decision: str = Field(..., description="e.g. ORIGINAL_INGESTION, DRONE_RECONCILIATION, SURVEYOR_APPROVED_CORRECTION")
    review_status: str = Field(..., description="e.g. APPROVED, AUTO_VALIDATED, PENDING_REVIEW")
    reviewer: str = Field(..., description="Officer name or automated subsystem")
    created_at: str = Field(..., description="ISO 8601 UTC creation timestamp")
    change_reason: str = Field(..., description="Explicit rationale for this version update")

    # Spatial metadata
    area_m2: float = Field(default=0.0, description="Metric area in square meters")
    centroid: List[float] = Field(default_factory=list, description="[latitude, longitude]")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom properties or survey numbers")

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


class NewVersionRequest(BaseModel):
    """Request payload to record a new immutable version of a parcel."""
    geometry: Dict[str, Any]
    source_datasets: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    decision: str = Field(default="SURVEYOR_APPROVED_CORRECTION")
    review_status: str = Field(default="APPROVED")
    reviewer: str = Field(default="Senior Land Records Officer")
    change_reason: str = Field(..., min_length=3, description="Why this version was created")
    version_number: Optional[int] = Field(None, description="Optional explicit version number (must be max + 1)")
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ParcelHistoryResponse(BaseModel):
    parcel_uuid: str
    total_versions: int
    current_version: int
    timeline: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump() if hasattr(self, "model_dump") else self.dict()


# ---------------------------------------------------------------------------
# PARCEL VERSION HISTORY SERVICE
# ---------------------------------------------------------------------------

class ParcelVersionHistoryService:
    """
    Manages the immutable append-only version ledger for parcels.
    Enforces strict relational-style uniqueness constraints and provides
    mathematically rigorous geometry comparison between any two versions.
    """

    def __init__(self, storage_path: Optional[Path] = None, auto_seed: bool = True):
        self.storage_path = storage_path or HISTORY_STORAGE_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory indices:
        # _history: parcel_uuid -> sorted List[ParcelVersionRecord]
        self._history: Dict[str, List[ParcelVersionRecord]] = {}
        # _version_keys: Set of (parcel_uuid, version_number) for O(1) constraint verification
        self._version_keys: Set[Tuple[str, int]] = set()

        self._load_from_disk()

        if not self._history and auto_seed:
            self._seed_initial_versions()
            self._save_to_disk()

    # -----------------------------------------------------------------------
    # PERSISTENCE & INITIALIZATION
    # -----------------------------------------------------------------------

    def _load_from_disk(self) -> None:
        """Loads version records from disk storage and builds constraint index."""
        if not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                record = ParcelVersionRecord(**item)
                key = (record.parcel_uuid, record.version_number)
                if key in self._version_keys:
                    logger.warning("Corrupt storage: duplicate key %s found in file!", key)
                    continue
                self._version_keys.add(key)
                if record.parcel_uuid not in self._history:
                    self._history[record.parcel_uuid] = []
                self._history[record.parcel_uuid].append(record)

            # Sort all timelines by version_number ascending
            for u in self._history:
                self._history[u].sort(key=lambda x: x.version_number)

            logger.info("Loaded %d parcel versions from %s", len(self._version_keys), self.storage_path)
        except Exception as e:
            logger.warning("Could not load version history from %s: %s", self.storage_path, e)

    def _save_to_disk(self) -> None:
        """Flushes version history to disk storage atomically."""
        try:
            records = []
            for timeline in self._history.values():
                for rec in timeline:
                    records.append(rec.to_dict())
            temp_path = self.storage_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            temp_path.replace(self.storage_path)
        except Exception as e:
            logger.error("Failed to persist version history: %s", e)

    def _seed_initial_versions(self) -> None:
        """Seeds multi-version timelines for sample demo parcels to illustrate the 3-version workflow."""
        from backend.identity.identity_service import get_identity_service
        try:
            id_service = get_identity_service()
            for p in list(id_service._parcels.values())[:10]:
                u = p.parcel_uuid
                geom = p.geometry
                survey_no = p.survey_numbers[0] if p.survey_numbers else "101/A"
                c = p.centroid
                area = p.area_m2

                # Version 1: Original cadastral geometry
                v1 = ParcelVersionRecord(
                    parcel_uuid=u,
                    version_number=1,
                    geometry=geom,
                    source_datasets=["Survey of India Cadastral Map (1998)"],
                    confidence=0.88,
                    IoU=1.0,
                    centroid_drift=0.0,
                    decision="ORIGINAL_INGESTION",
                    review_status="APPROVED",
                    reviewer="State Cadastral Revenue Authority",
                    created_at="2024-03-12T09:00:00Z",
                    change_reason="Original cadastral paper map digitization and vectorization",
                    area_m2=area,
                    centroid=c,
                    properties={"survey_number": survey_no, "source": "cadastral"},
                )
                self._insert_record(v1)

                # Version 2: Drone reconciliation
                # Slightly refined geometry (e.g. IoU ~ 0.94, drift ~ 0.6m)
                g_shape = shape(geom)
                clon, clat = g_shape.centroid.x, g_shape.centroid.y
                # Shift slightly for version 2
                poly_coords = []
                for pt in geom.get("coordinates", [[]])[0]:
                    poly_coords.append([round(pt[0] + 0.000005, 6), round(pt[1] + 0.000004, 6)])
                v2_geom = {"type": "Polygon", "coordinates": [poly_coords]}
                v2 = ParcelVersionRecord(
                    parcel_uuid=u,
                    version_number=2,
                    geometry=v2_geom,
                    source_datasets=["Survey of India Cadastral Map", "High-Resolution Drone Orthophoto (2025)"],
                    confidence=0.92,
                    IoU=0.942,
                    centroid_drift=0.58,
                    decision="DRONE_RECONCILIATION",
                    review_status="AUTO_VALIDATED",
                    reviewer="TerraNode Automated Spatial Consensus Engine",
                    created_at="2025-08-18T14:30:00Z",
                    change_reason="High-resolution drone orthophoto boundary reconciliation",
                    area_m2=round(area * 1.015, 2),
                    centroid=[round(c[0] + 0.000004, 6), round(c[1] + 0.000005, 6)],
                    properties={"survey_number": survey_no, "source": "drone_reconciled"},
                )
                self._insert_record(v2)

                # Version 3: Surveyor-approved correction
                poly_coords_v3 = []
                for pt in geom.get("coordinates", [[]])[0]:
                    poly_coords_v3.append([round(pt[0] + 0.000002, 6), round(pt[1] + 0.000002, 6)])
                v3_geom = {"type": "Polygon", "coordinates": [poly_coords_v3]}
                v3 = ParcelVersionRecord(
                    parcel_uuid=u,
                    version_number=3,
                    geometry=v3_geom,
                    source_datasets=["Survey of India Cadastral Map", "Drone Orthophoto", "CORS RTK Field Rover Checkpoint"],
                    confidence=0.98,
                    IoU=0.981,
                    centroid_drift=0.22,
                    decision="SURVEYOR_APPROVED_CORRECTION",
                    review_status="APPROVED",
                    reviewer="Senior Surveyor Ramesh K. (Badge #401)",
                    created_at="2026-09-26T11:15:00Z",
                    change_reason="Surveyor-approved correction following joint physical boundary verification",
                    area_m2=round(area * 1.005, 2),
                    centroid=[round(c[0] + 0.000002, 6), round(c[1] + 0.000002, 6)],
                    properties={"survey_number": survey_no, "source": "rtk_verified"},
                )
                self._insert_record(v3)

            logger.info("Seeded 3-version historical timelines for %d demo parcels.", min(10, len(id_service._parcels)))
        except Exception as e:
            logger.warning("Could not auto-seed version histories: %s", e)

    # -----------------------------------------------------------------------
    # CONSTRAINT ENFORCEMENT & INSERTION
    # -----------------------------------------------------------------------

    def _insert_record(self, record: ParcelVersionRecord) -> None:
        """
        Enforces database-level constraint:
        PRIMARY KEY (parcel_uuid, version_number) MUST BE UNIQUE.
        """
        key = (record.parcel_uuid, record.version_number)
        if key in self._version_keys:
            raise DuplicateVersionError(
                f"DATABASE CONSTRAINT VIOLATION: Duplicate version {record.version_number} "
                f"already exists for parcel_uuid '{record.parcel_uuid}'."
            )

        # Monotonicity check if previous versions exist
        timeline = self._history.get(record.parcel_uuid, [])
        if timeline:
            max_v = timeline[-1].version_number
            if record.version_number <= max_v:
                raise DuplicateVersionError(
                    f"MONOTONICITY VIOLATION: Version number {record.version_number} must be strictly "
                    f"greater than current maximum version {max_v}."
                )

        self._version_keys.add(key)
        if record.parcel_uuid not in self._history:
            self._history[record.parcel_uuid] = []
        self._history[record.parcel_uuid].append(record)
        self._history[record.parcel_uuid].sort(key=lambda x: x.version_number)

    # -----------------------------------------------------------------------
    # VERSION CREATION ENGINE
    # -----------------------------------------------------------------------

    def create_new_version(
        self,
        parcel_uuid: str,
        request: NewVersionRequest,
    ) -> Tuple[ParcelVersionRecord, Optional[GeometryComparisonResult]]:
        """
        Appends a new version to the immutable ledger for parcel_uuid.
        Validates geometry, enforces constraints, computes metric differences
        against previous version, and preserves complete attribution.
        """
        # 1. Parse and validate input geometry
        try:
            geom_shape = shape(request.geometry)
        except Exception as e:
            raise ValueError(f"Invalid geometry in new-version request: {str(e)}")

        val_res = validate_and_repair_geometry(geom_shape)
        valid_geom = val_res.repaired_geometry if val_res.was_repaired else geom_shape
        if valid_geom is None or valid_geom.is_empty:
            raise ValueError("Supplied geometry is null or empty.")

        # Compute metric area & centroid
        c_lon = float(valid_geom.centroid.x)
        c_lat = float(valid_geom.centroid.y)
        utm_crs, _ = determine_utm_crs(c_lon, c_lat)
        geom_utm = reproject_geometry(valid_geom, from_crs="EPSG:4326", to_crs=utm_crs)
        area_m2 = round(geom_utm.area, 2)
        centroid = [round(c_lat, 6), round(c_lon, 6)]

        # 2. Determine target version_number
        timeline = self._history.get(parcel_uuid, [])
        previous_version: Optional[ParcelVersionRecord] = timeline[-1] if timeline else None
        current_max = previous_version.version_number if previous_version else 0

        if request.version_number is not None:
            target_v = request.version_number
        else:
            target_v = current_max + 1

        # 3. Compute metrics against previous version if available
        comparison: Optional[GeometryComparisonResult] = None
        iou_val: Optional[float] = None
        drift_val: Optional[float] = None

        if previous_version is not None:
            comparison = self.compare_geometries(
                shape(previous_version.geometry),
                valid_geom,
                version_a_num=previous_version.version_number,
                version_b_num=target_v,
                c_lon=c_lon,
                c_lat=c_lat,
            )
            iou_val = comparison.boundary_change.metric_iou
            drift_val = comparison.centroid_shift.distance_m

        # 4. Construct record and insert with constraint verification
        new_record = ParcelVersionRecord(
            parcel_uuid=parcel_uuid,
            version_number=target_v,
            geometry=mapping(valid_geom),
            source_datasets=request.source_datasets or ["Surveyor Verification"],
            confidence=request.confidence,
            IoU=iou_val,
            centroid_drift=drift_val,
            decision=request.decision,
            review_status=request.review_status,
            reviewer=request.reviewer,
            created_at=_now_iso(),
            change_reason=request.change_reason,
            area_m2=area_m2,
            centroid=centroid,
            properties=request.properties or {},
        )

        self._insert_record(new_record)
        self._save_to_disk()

        # Update parent parcel entity geometry version if registered
        try:
            from backend.identity.identity_service import get_identity_service
            id_svc = get_identity_service()
            p = id_svc.get_parcel(parcel_uuid)
            if p:
                p.current_geometry_version = f"v{target_v}.0"
                p.geometry = mapping(valid_geom)
                p.area_m2 = area_m2
                p.centroid = centroid
                p.updated_at = _now_iso()
                id_svc._save_registry()
        except Exception:
            pass

        return new_record, comparison

    # -----------------------------------------------------------------------
    # GEOMETRY COMPARISON ENGINE
    # -----------------------------------------------------------------------

    @staticmethod
    def compare_geometries(
        geom_a_4326: BaseGeometry,
        geom_b_4326: BaseGeometry,
        version_a_num: int,
        version_b_num: int,
        c_lon: float,
        c_lat: float,
    ) -> GeometryComparisonResult:
        """
        Calculates exact metric geometry comparison between two versions:
        - area_change: area_a_m2, area_b_m2, diff_m2, percent_change
        - boundary_change: metric_iou, symmetric_difference_m2, has_boundary_change
        - centroid_shift: distance_m, bearing_deg
        """
        utm_crs, _ = determine_utm_crs(c_lon, c_lat)
        poly_a = reproject_geometry(geom_a_4326, from_crs="EPSG:4326", to_crs=utm_crs)
        poly_b = reproject_geometry(geom_b_4326, from_crs="EPSG:4326", to_crs=utm_crs)

        if not poly_a.is_valid:
            poly_a = poly_a.buffer(0)
        if not poly_b.is_valid:
            poly_b = poly_b.buffer(0)

        # 1. Area Change
        area_a = float(poly_a.area)
        area_b = float(poly_b.area)
        diff_m2 = area_b - area_a
        pct_change = (diff_m2 / area_a * 100.0) if area_a > 0 else 0.0

        area_comp = AreaChangeComparison(
            area_a_m2=round(area_a, 2),
            area_b_m2=round(area_b, 2),
            diff_m2=round(diff_m2, 2),
            percent_change=round(pct_change, 2),
        )

        # 2. Boundary Change
        inter_area = poly_a.intersection(poly_b).area
        union_area = poly_a.union(poly_b).area
        metric_iou = float(inter_area / union_area) if union_area > 0 else 0.0
        sym_diff_m2 = float(poly_a.symmetric_difference(poly_b).area)
        perim_a = float(poly_a.length)
        perim_b = float(poly_b.length)

        bound_comp = BoundaryChangeComparison(
            metric_iou=round(metric_iou, 4),
            symmetric_difference_m2=round(sym_diff_m2, 2),
            has_boundary_change=(sym_diff_m2 > 0.01 or abs(diff_m2) > 0.01),
            perimeter_a_m=round(perim_a, 2),
            perimeter_b_m=round(perim_b, 2),
        )

        # 3. Centroid Shift
        ca = poly_a.centroid
        cb = poly_b.centroid
        shift_dist = float(ca.distance(cb))

        dx = cb.x - ca.x
        dy = cb.y - ca.y
        bearing = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0 if shift_dist > 0.001 else None

        centroid_comp = CentroidShiftComparison(
            centroid_a=[round(geom_a_4326.centroid.y, 6), round(geom_a_4326.centroid.x, 6)],
            centroid_b=[round(geom_b_4326.centroid.y, 6), round(geom_b_4326.centroid.x, 6)],
            distance_m=round(shift_dist, 3),
            bearing_deg=round(bearing, 1) if bearing is not None else None,
        )

        summary = (
            f"Version {version_a_num} → {version_b_num}: Area Δ={diff_m2:+.2f} m² ({pct_change:+.2f}%), "
            f"Boundary IoU={metric_iou*100:.1f}%, Centroid Shift={shift_dist:.2f}m."
        )

        return GeometryComparisonResult(
            version_a=version_a_num,
            version_b=version_b_num,
            area_change=area_comp,
            boundary_change=bound_comp,
            centroid_shift=centroid_comp,
            summary=summary,
        )

    # -----------------------------------------------------------------------
    # RETRIEVAL API
    # -----------------------------------------------------------------------

    def get_history(self, parcel_uuid: str) -> ParcelHistoryResponse:
        """Returns the full chronological version history timeline for a parcel."""
        canonical_uuid = parcel_uuid
        timeline = self._history.get(parcel_uuid, [])
        if not timeline:
            # Check if parent parcel exists in identity service
            from backend.identity.identity_service import get_identity_service
            p = get_identity_service().get_parcel(parcel_uuid)
            if not p:
                raise VersionNotFoundError(f"Parcel with UUID '{parcel_uuid}' not found.")
            canonical_uuid = p.parcel_uuid
            timeline = self._history.get(canonical_uuid, [])
            if not timeline:
                # Synthesize Version 1 for baseline parcel if not yet recorded in history ledger
                v1 = ParcelVersionRecord(
                    parcel_uuid=canonical_uuid,
                    version_number=1,
                    geometry=p.geometry,
                    source_datasets=p.source_ids or ["Cadastral Survey"],
                    confidence=p.confidence_score,
                    IoU=1.0,
                    centroid_drift=0.0,
                    decision="ORIGINAL_INGESTION",
                    review_status="APPROVED",
                    reviewer="System (Ingestion Engine)",
                    created_at=p.created_at,
                    change_reason="Original parcel cadastral boundary",
                    area_m2=p.area_m2,
                    centroid=p.centroid,
                    properties=p.source_records[0].properties if p.source_records else {},
                )
                self._insert_record(v1)
                self._save_to_disk()
                timeline = [v1]

        summary_timeline = []
        for v in timeline:
            summary_timeline.append({
                "version_number": v.version_number,
                "decision": v.decision,
                "review_status": v.review_status,
                "reviewer": v.reviewer,
                "created_at": v.created_at,
                "change_reason": v.change_reason,
                "area_m2": v.area_m2,
                "confidence": v.confidence,
                "IoU": v.IoU,
                "centroid_drift": v.centroid_drift,
                "source_datasets": v.source_datasets,
            })

        return ParcelHistoryResponse(
            parcel_uuid=canonical_uuid,
            total_versions=len(timeline),
            current_version=timeline[-1].version_number,
            timeline=summary_timeline,
        )

    def get_version_detail(
        self,
        parcel_uuid: str,
        version_number: int,
        compare_with: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves full detail of a specific version, including comparison
        with the requested or immediately preceding version.
        """
        canonical_uuid = parcel_uuid
        timeline = self._history.get(parcel_uuid, [])
        if not timeline:
            hist = self.get_history(parcel_uuid)  # Auto-seed baseline or resolve canonical
            canonical_uuid = hist.parcel_uuid
            timeline = self._history.get(canonical_uuid, [])

        target_rec: Optional[ParcelVersionRecord] = None
        for v in timeline:
            if v.version_number == version_number:
                target_rec = v
                break

        if target_rec is None:
            raise VersionNotFoundError(f"Version {version_number} not found for parcel '{parcel_uuid}'.")

        res_dict = target_rec.to_dict()

        # Geometry comparison
        compare_v_num = compare_with if compare_with is not None else (version_number - 1 if version_number > 1 else None)

        if compare_v_num is not None:
            prev_rec: Optional[ParcelVersionRecord] = None
            for v in timeline:
                if v.version_number == compare_v_num:
                    prev_rec = v
                    break

            if prev_rec is not None:
                c_lon = float(shape(target_rec.geometry).centroid.x)
                c_lat = float(shape(target_rec.geometry).centroid.y)
                comp = self.compare_geometries(
                    shape(prev_rec.geometry),
                    shape(target_rec.geometry),
                    version_a_num=prev_rec.version_number,
                    version_b_num=target_rec.version_number,
                    c_lon=c_lon,
                    c_lat=c_lat,
                )
                res_dict["comparison_with_previous"] = comp.to_dict()
                res_dict["previous_geometry"] = prev_rec.geometry

        return res_dict


# Global Singleton
_VERSION_HISTORY_SERVICE: Optional[ParcelVersionHistoryService] = None


def get_version_history_service() -> ParcelVersionHistoryService:
    """Returns or lazily creates the global ParcelVersionHistoryService singleton."""
    global _VERSION_HISTORY_SERVICE
    if _VERSION_HISTORY_SERVICE is None:
        _VERSION_HISTORY_SERVICE = ParcelVersionHistoryService()
    return _VERSION_HISTORY_SERVICE
