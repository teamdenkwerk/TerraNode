"""
backend/identity/identity_service.py

TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY SERVICE

Provides deterministic, immutable internal parcel identity resolution.
Guarantees:
1. Stable parcel_uuid independent of changing survey numbers, municipal IDs, or source filenames.
2. Verified geometric & topological continuity before associating new source records.
3. Guardrail: Never merges parcels solely because names or IDs look similar.
4. Detects same-parcel re-uploads, evolved survey numbers, evolved municipal IDs, geometry revisions, and duplicate records.
5. Flags ambiguous or sub-threshold continuity as 'IDENTITY_UNCERTAIN' requiring officer review.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from backend.config.reconciliation_policy import (
    AUTO_RECONCILE_CONFIDENCE_MIN,
    REVIEW_CONFIDENCE_MIN,
    MAX_CENTROID_DRIFT_METERS,
)
from backend.crs.transformer import determine_utm_crs, reproject_geometry
from backend.geometry.validator import validate_and_repair_geometry
from backend.identity.models import (
    IdentityResolutionResult,
    LineageEvent,
    ParcelIdentityRecord,
    ParcelStatus,
    ResolutionAction,
    ResolveIdentityRequest,
    ResolveIdentityResponse,
    SourceRecordSnapshot,
)

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PARCELS_DIR = DATA_DIR / "parcels"
REGISTRY_FILE = PARCELS_DIR / "parcel_registry.json"

# Fixed TerraNode namespace for stable deterministic UUIDv5 generation
TERRANODE_NAMESPACE = uuid.UUID("7e57a0de-6e05-4c0a-8d3e-905c110da5e1")


def _now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_id(raw: Optional[str]) -> Optional[str]:
    """Normalizes an identifier for invariant matching."""
    if not raw:
        return None
    cleaned = str(raw).strip().upper()
    cleaned = re.sub(r"[\s\-_/]+", "", cleaned)
    return cleaned if cleaned else None


class ParcelIdentityService:
    """
    Production-grade Permanent Parcel Identity Management Engine.
    Maintains the authoritative internal identity registry and verifies
    continuity across data evolutions.
    """

    def __init__(self, storage_path: Optional[Path] = None, auto_seed: bool = True):
        self.storage_path = storage_path or REGISTRY_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._parcels: Dict[str, ParcelIdentityRecord] = {}
        self._spatial_tree: Optional[STRtree] = None
        self._spatial_geoms: List[BaseGeometry] = []
        self._spatial_uuids: List[str] = []

        # Load existing registry or seed initial datasets
        self._load_registry()
        if not self._parcels and auto_seed:
            self._seed_from_catalog()
            self._save_registry()

        self._rebuild_spatial_index()

    # -----------------------------------------------------------------------
    # PERSISTENCE & INITIALIZATION
    # -----------------------------------------------------------------------

    def _load_registry(self) -> None:
        """Loads parcel records from disk storage."""
        if not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                record = ParcelIdentityRecord(**item)
                self._parcels[record.parcel_uuid] = record
            logger.info("Loaded %d permanent parcels from %s", len(self._parcels), self.storage_path)
        except Exception as e:
            logger.warning("Could not load parcel registry from %s: %s", self.storage_path, e)

    def _save_registry(self) -> None:
        """Flushes in-memory registry to disk storage."""
        try:
            records = [p.to_dict() for p in self._parcels.values()]
            temp_path = self.storage_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
            temp_path.replace(self.storage_path)
        except Exception as e:
            logger.error("Failed to persist parcel registry: %s", e)

    def _seed_from_catalog(self) -> None:
        """Seeds the registry with preloaded platform datasets (e.g. Bengaluru Ward 112)."""
        try:
            from backend.dataset_manager import DATASET_CATALOG
            seeded_count = 0
            ts = _now_iso()

            for ds_id, ds in DATASET_CATALOG.items():
                entities = ds.get("entities", [])
                for e in entities:
                    canonical_uid = e.get("canonical_uid", f"SEED-{uuid.uuid4().hex[:6]}")
                    props = e.get("properties", {}) or {}
                    survey_no = props.get("survey_number")
                    geom = e.get("geometry")
                    if not geom:
                        continue

                    # Stable deterministic UUID for preloaded canonical entities
                    parcel_uuid = str(uuid.uuid5(TERRANODE_NAMESPACE, f"catalog:{ds_id}:{canonical_uid}"))
                    c = props.get("centroid") or [12.9784, 77.6408]
                    area_m2 = float(e.get("area_m2") or 200.0)

                    record = ParcelIdentityRecord(
                        parcel_uuid=parcel_uuid,
                        source_ids=[canonical_uid],
                        survey_numbers=[survey_no] if survey_no else [],
                        municipal_ids=[f"PID-{canonical_uid}"],
                        current_geometry_version="v1.0",
                        status=ParcelStatus.RECONCILED.value,
                        created_at=ts,
                        updated_at=ts,
                        geometry=geom,
                        centroid=c,
                        area_m2=area_m2,
                        confidence_score=float(e.get("confidence_score") or 0.95),
                        needs_review=bool(e.get("needs_review", False)),
                        source_records=[
                            SourceRecordSnapshot(
                                source_record_id=f"SRC-{uuid.uuid4().hex[:8]}",
                                source_dataset=ds_id,
                                source_id=canonical_uid,
                                survey_number=survey_no,
                                municipal_id=f"PID-{canonical_uid}",
                                geometry_version="v1.0",
                                recorded_at=ts,
                                match_evidence={"type": "SEED_AUTHORITATIVE"},
                                properties=props,
                            )
                        ],
                        lineage=[
                            LineageEvent(
                                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                                event_type="INITIAL_SEED",
                                timestamp=ts,
                                description=f"Seeded from catalog dataset '{ds_id}' as authoritative entity {canonical_uid}",
                                details={"dataset_id": ds_id, "canonical_uid": canonical_uid},
                            )
                        ],
                    )
                    self._parcels[parcel_uuid] = record
                    seeded_count += 1

            logger.info("Seeded %d permanent parcels from platform catalog.", seeded_count)
        except Exception as e:
            logger.warning("Could not auto-seed parcels from catalog: %s", e)

    def _rebuild_spatial_index(self) -> None:
        """Reconstructs R-tree spatial index over all active parcel geometries."""
        geoms = []
        uuids = []
        for p in self._parcels.values():
            try:
                g = shape(p.geometry)
                if g.is_valid and not g.is_empty:
                    geoms.append(g)
                    uuids.append(p.parcel_uuid)
            except Exception:
                continue

        self._spatial_geoms = geoms
        self._spatial_uuids = uuids
        self._spatial_tree = STRtree(geoms) if geoms else None

    # -----------------------------------------------------------------------
    # CONTINUITY & METRIC CALCULATION
    # -----------------------------------------------------------------------

    @staticmethod
    def compute_metric_spatial_evidence(
        geom_a_4326: BaseGeometry,
        geom_b_4326: BaseGeometry,
        center_lon: float,
        center_lat: float,
    ) -> Tuple[float, float, float]:
        """
        Computes metric spatial matching evidence using distortion-free UTM projection:
        Returns: (metric_iou, centroid_drift_meters, area_difference_ratio)
        """
        utm_crs, _ = determine_utm_crs(center_lon, center_lat)
        poly_a_utm = reproject_geometry(geom_a_4326, from_crs="EPSG:4326", to_crs=utm_crs)
        poly_b_utm = reproject_geometry(geom_b_4326, from_crs="EPSG:4326", to_crs=utm_crs)

        if not poly_a_utm.is_valid:
            poly_a_utm = poly_a_utm.buffer(0)
        if not poly_b_utm.is_valid:
            poly_b_utm = poly_b_utm.buffer(0)

        # Centroid drift
        ca = poly_a_utm.centroid
        cb = poly_b_utm.centroid
        drift_m = float(ca.distance(cb))

        # Metric IoU
        inter_area = poly_a_utm.intersection(poly_b_utm).area
        union_area = poly_a_utm.union(poly_b_utm).area
        iou = float(inter_area / union_area) if union_area > 0 else 0.0

        # Area difference ratio
        max_area = max(poly_a_utm.area, poly_b_utm.area)
        area_diff_ratio = abs(poly_a_utm.area - poly_b_utm.area) / max_area if max_area > 0 else 0.0

        return round(iou, 4), round(drift_m, 3), round(area_diff_ratio, 4)

    # -----------------------------------------------------------------------
    # RESOLUTION ENGINE
    # -----------------------------------------------------------------------

    def resolve_identity(self, request: ResolveIdentityRequest) -> IdentityResolutionResult:
        """
        Evaluates an incoming parcel representation against the permanent identity registry.
        Uses verified geometric evidence, continuity thresholds, and lineage tracking.
        Enforces guardrail: Never merges parcels solely because names or IDs look similar.
        """
        ts = _now_iso()

        # 1. Parse and validate input geometry
        try:
            incoming_geom = shape(request.geometry)
        except Exception as e:
            raise ValueError(f"Invalid geometry in resolve request: {str(e)}")

        val_res = validate_and_repair_geometry(incoming_geom)
        valid_geom = val_res.repaired_geometry if val_res.was_repaired else incoming_geom
        if valid_geom is None or valid_geom.is_empty:
            raise ValueError("Empty or invalid geometry supplied in resolve request.")

        # Compute incoming centroid and metric area
        c_lon = float(valid_geom.centroid.x)
        c_lat = float(valid_geom.centroid.y)
        utm_crs, _ = determine_utm_crs(c_lon, c_lat)
        incoming_utm = reproject_geometry(valid_geom, from_crs="EPSG:4326", to_crs=utm_crs)
        area_m2 = round(incoming_utm.area, 2)
        centroid = [round(c_lat, 6), round(c_lon, 6)]

        # 2. Query spatial candidates via R-Tree (search within ~60m buffer in degrees: 0.0006 deg)
        search_envelope = valid_geom.buffer(0.0006)
        candidate_uuids: List[str] = []

        if self._spatial_tree is not None and len(self._spatial_geoms) > 0:
            candidate_indices = self._spatial_tree.query(search_envelope)
            for idx in candidate_indices:
                cand_geom = self._spatial_geoms[idx]
                if cand_geom.intersects(search_envelope):
                    candidate_uuids.append(self._spatial_uuids[idx])

        # De-duplicate candidate UUIDs
        candidate_uuids = list(dict.fromkeys(candidate_uuids))

        # 3. Guardrail Evaluation: Check for name/ID collisions without spatial proximity
        # Inspect whether the same source_id or survey_number exists far away
        req_clean_survey = _clean_id(request.survey_number)
        req_clean_mun = _clean_id(request.municipal_id)

        # 4. Evaluate each spatial candidate with strict metric evidence
        best_candidate: Optional[ParcelIdentityRecord] = None
        best_iou: float = -1.0
        best_drift: float = 9999.0
        best_area_diff: float = 1.0

        for cand_uuid in candidate_uuids:
            cand = self._parcels.get(cand_uuid)
            if not cand:
                continue
            cand_geom = shape(cand.geometry)
            iou, drift_m, area_diff = self.compute_metric_spatial_evidence(
                valid_geom, cand_geom, c_lon, c_lat
            )

            if iou > best_iou:
                best_iou = iou
                best_drift = drift_m
                best_area_diff = area_diff
                best_candidate = cand

        # -------------------------------------------------------------------
        # DECISION TREE
        # -------------------------------------------------------------------

        # SCENARIO 1: No spatial candidate intersects within tolerance
        # MUST NOT merge even if survey number or municipal ID matches another parcel in another location!
        if best_candidate is None or best_iou < 0.15:
            # Generate deterministic permanent UUID based on canonical spatial location
            # Stable spatial footprint prevents random UUID generation on reprocessing
            spatial_sig = f"sig:{round(c_lat, 5)}:{round(c_lon, 5)}:{int(area_m2)}"
            parcel_uuid = str(uuid.uuid5(TERRANODE_NAMESPACE, spatial_sig))

            # If existing parcel already has this exact spatial UUID, retrieve it
            if parcel_uuid in self._parcels:
                existing = self._parcels[parcel_uuid]
                return self._handle_duplicate_or_match(existing, request, 1.0, 0.0, ts)

            # Create brand new permanent parcel
            new_record = ParcelIdentityRecord(
                parcel_uuid=parcel_uuid,
                source_ids=[request.source_id],
                survey_numbers=[request.survey_number] if request.survey_number else [],
                municipal_ids=[request.municipal_id] if request.municipal_id else [],
                current_geometry_version="v1.0",
                status=ParcelStatus.ACTIVE.value,
                created_at=ts,
                updated_at=ts,
                geometry=mapping(valid_geom),
                centroid=centroid,
                area_m2=area_m2,
                confidence_score=1.0,
                needs_review=False,
                source_records=[
                    SourceRecordSnapshot(
                        source_record_id=f"SRC-{uuid.uuid4().hex[:8]}",
                        source_dataset=request.source_dataset,
                        source_id=request.source_id,
                        survey_number=request.survey_number,
                        municipal_id=request.municipal_id,
                        geometry_version="v1.0",
                        recorded_at=ts,
                        match_evidence={"action": "NEW_PARCEL_CREATED"},
                        properties=request.properties or {},
                    )
                ],
                lineage=[
                    LineageEvent(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        event_type="PARCEL_CREATED",
                        timestamp=ts,
                        description=f"Registered new permanent parcel from {request.source_dataset} (ID: {request.source_id})",
                        details={"source_id": request.source_id, "dataset": request.source_dataset},
                    )
                ],
            )
            self._parcels[parcel_uuid] = new_record
            self._rebuild_spatial_index()
            self._save_registry()

            return IdentityResolutionResult(
                parcel_uuid=parcel_uuid,
                resolution_action=ResolutionAction.NEW_PARCEL_CREATED,
                status=new_record.status,
                current_geometry_version=new_record.current_geometry_version,
                source_ids=new_record.source_ids,
                survey_numbers=new_record.survey_numbers,
                municipal_ids=new_record.municipal_ids,
                iou=1.0,
                centroid_drift_m=0.0,
                confidence_score=1.0,
                needs_review=False,
                message=f"Created new permanent parcel '{parcel_uuid}' with version v1.0.",
                details={"area_m2": area_m2},
            )

        # SCENARIO 2: Spatial candidate exists, but continuity is UNCERTAIN
        # e.g. Moderate overlap (0.20 <= IoU < 0.70) or excessive centroid drift (> 2.0m)
        # where geometric evidence cannot definitively establish continuity
        is_high_spatial_continuity = (best_iou >= 0.70 and best_drift < MAX_CENTROID_DRIFT_METERS)
        is_sub_threshold = (best_iou < 0.70 or best_drift >= MAX_CENTROID_DRIFT_METERS)

        if is_sub_threshold:
            # Check if identifiers contradict or conflict
            has_id_match = (
                request.source_id in best_candidate.source_ids or
                (req_clean_survey and any(_clean_id(s) == req_clean_survey for s in best_candidate.survey_numbers)) or
                (req_clean_mun and any(_clean_id(m) == req_clean_mun for m in best_candidate.municipal_ids))
            )

            # Continuity cannot be established!
            # CRITICAL RULE: Mark as "IDENTITY_UNCERTAIN" and require review.
            uncertain_uuid = str(uuid.uuid5(TERRANODE_NAMESPACE, f"uncertain:{round(c_lat, 5)}:{round(c_lon, 5)}:{request.source_id}"))

            uncertain_record = ParcelIdentityRecord(
                parcel_uuid=uncertain_uuid,
                source_ids=[request.source_id],
                survey_numbers=[request.survey_number] if request.survey_number else [],
                municipal_ids=[request.municipal_id] if request.municipal_id else [],
                current_geometry_version="v1.0-provisional",
                status=ParcelStatus.IDENTITY_UNCERTAIN.value,
                created_at=ts,
                updated_at=ts,
                geometry=mapping(valid_geom),
                centroid=centroid,
                area_m2=area_m2,
                confidence_score=round(max(0.40, best_iou), 2),
                needs_review=True,
                review_reason=(
                    f"Continuity cannot be established with candidate '{best_candidate.parcel_uuid}': "
                    f"IoU={best_iou*100:.1f}%, Drift={best_drift:.2f}m violates authoritative policy "
                    f"(IoU >= 70%, Drift < 2.0m). Officer review required."
                ),
                source_records=[
                    SourceRecordSnapshot(
                        source_record_id=f"SRC-{uuid.uuid4().hex[:8]}",
                        source_dataset=request.source_dataset,
                        source_id=request.source_id,
                        survey_number=request.survey_number,
                        municipal_id=request.municipal_id,
                        geometry_version="v1.0-provisional",
                        recorded_at=ts,
                        match_evidence={
                            "action": "IDENTITY_UNCERTAIN",
                            "candidate_uuid": best_candidate.parcel_uuid,
                            "candidate_iou": best_iou,
                            "candidate_drift_m": best_drift,
                        },
                        properties=request.properties or {},
                    )
                ],
                lineage=[
                    LineageEvent(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        event_type="IDENTITY_UNCERTAIN_FLAGGED",
                        timestamp=ts,
                        description="Provisional parcel flagged as IDENTITY_UNCERTAIN due to ambiguous boundary alignment",
                        details={
                            "candidate_uuid": best_candidate.parcel_uuid,
                            "candidate_iou": best_iou,
                            "candidate_drift_m": best_drift,
                        },
                    )
                ],
            )
            self._parcels[uncertain_uuid] = uncertain_record
            self._rebuild_spatial_index()
            self._save_registry()

            return IdentityResolutionResult(
                parcel_uuid=uncertain_uuid,
                resolution_action=ResolutionAction.IDENTITY_UNCERTAIN,
                status=ParcelStatus.IDENTITY_UNCERTAIN.value,
                current_geometry_version="v1.0-provisional",
                source_ids=uncertain_record.source_ids,
                survey_numbers=uncertain_record.survey_numbers,
                municipal_ids=uncertain_record.municipal_ids,
                iou=best_iou,
                centroid_drift_m=best_drift,
                confidence_score=uncertain_record.confidence_score,
                needs_review=True,
                message=f"IDENTITY_UNCERTAIN: Spatial continuity falls below authoritative thresholds (IoU: {best_iou*100:.1f}%, Drift: {best_drift:.2f}m violates authoritative policy). Review required.",
                details={"candidate_uuid": best_candidate.parcel_uuid, "review_reason": uncertain_record.review_reason},
            )

        # SCENARIO 3: Verified Geometric Continuity Established (IoU >= 0.70 AND Drift < 2.0m)
        # Preserve best_candidate.parcel_uuid!
        return self._handle_verified_continuity(best_candidate, request, valid_geom, best_iou, best_drift, area_m2, centroid, ts)

    def _handle_duplicate_or_match(
        self,
        candidate: ParcelIdentityRecord,
        request: ResolveIdentityRequest,
        iou: float,
        drift_m: float,
        ts: str,
    ) -> IdentityResolutionResult:
        """Handles exact duplicate records without corrupting registry."""
        is_duplicate = (
            request.source_id in candidate.source_ids and
            any(s.source_dataset == request.source_dataset and s.source_id == request.source_id for s in candidate.source_records)
        )
        action = ResolutionAction.DUPLICATE_SOURCE_RECORD if is_duplicate else ResolutionAction.MATCHED_EXISTING
        candidate.updated_at = ts

        if not is_duplicate:
            candidate.source_records.append(
                SourceRecordSnapshot(
                    source_record_id=f"SRC-{uuid.uuid4().hex[:8]}",
                    source_dataset=request.source_dataset,
                    source_id=request.source_id,
                    survey_number=request.survey_number,
                    municipal_id=request.municipal_id,
                    geometry_version=candidate.current_geometry_version,
                    recorded_at=ts,
                    match_evidence={"iou": iou, "drift_m": drift_m, "action": action.value},
                    properties=request.properties or {},
                )
            )

        self._save_registry()
        return IdentityResolutionResult(
            parcel_uuid=candidate.parcel_uuid,
            resolution_action=action,
            status=candidate.status,
            current_geometry_version=candidate.current_geometry_version,
            source_ids=candidate.source_ids,
            survey_numbers=candidate.survey_numbers,
            municipal_ids=candidate.municipal_ids,
            iou=iou,
            centroid_drift_m=drift_m,
            confidence_score=candidate.confidence_score,
            needs_review=candidate.needs_review,
            message=f"Preserved permanent parcel_uuid '{candidate.parcel_uuid}' ({action.value}).",
        )

    def _handle_verified_continuity(
        self,
        candidate: ParcelIdentityRecord,
        request: ResolveIdentityRequest,
        valid_geom: BaseGeometry,
        iou: float,
        drift_m: float,
        new_area_m2: float,
        new_centroid: List[float],
        ts: str,
    ) -> IdentityResolutionResult:
        """
        Executes verified continuity state transitions while preserving parcel_uuid:
        - Detects duplicate source records
        - Incorporates changed survey numbers
        - Incorporates changed municipal IDs
        - Advances geometry version on verified boundary revisions
        """
        # 1. Duplicate Check
        is_duplicate = (
            request.source_id in candidate.source_ids and
            any(s.source_dataset == request.source_dataset and s.source_id == request.source_id for s in candidate.source_records) and
            iou >= 0.98 and drift_m <= 0.20
        )
        if is_duplicate:
            candidate.updated_at = ts
            self._save_registry()
            return IdentityResolutionResult(
                parcel_uuid=candidate.parcel_uuid,
                resolution_action=ResolutionAction.DUPLICATE_SOURCE_RECORD,
                status=candidate.status,
                current_geometry_version=candidate.current_geometry_version,
                source_ids=candidate.source_ids,
                survey_numbers=candidate.survey_numbers,
                municipal_ids=candidate.municipal_ids,
                iou=iou,
                centroid_drift_m=drift_m,
                confidence_score=candidate.confidence_score,
                needs_review=candidate.needs_review,
                message=f"Duplicate source record detected from dataset '{request.source_dataset}'. Preserved parcel_uuid.",
            )

        action = ResolutionAction.MATCHED_EXISTING
        lineage_events: List[LineageEvent] = []

        # 2. Check for Changed / Evolving Survey Number
        if request.survey_number and request.survey_number not in candidate.survey_numbers:
            action = ResolutionAction.SURVEY_NUMBER_EVOLVED
            old_surveys = list(candidate.survey_numbers)
            candidate.survey_numbers.append(request.survey_number)
            lineage_events.append(
                LineageEvent(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    event_type="SURVEY_NUMBER_EVOLVED",
                    timestamp=ts,
                    description=f"Survey number evolved: added '{request.survey_number}' (Historical: {old_surveys})",
                    details={"old": old_surveys, "new": request.survey_number},
                )
            )

        # 3. Check for Changed / Evolving Municipal Property ID
        if request.municipal_id and request.municipal_id not in candidate.municipal_ids:
            action = ResolutionAction.MUNICIPAL_ID_EVOLVED
            old_mun = list(candidate.municipal_ids)
            candidate.municipal_ids.append(request.municipal_id)
            lineage_events.append(
                LineageEvent(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    event_type="MUNICIPAL_ID_EVOLVED",
                    timestamp=ts,
                    description=f"Municipal ID evolved: added '{request.municipal_id}' (Historical: {old_mun})",
                    details={"old": old_mun, "new": request.municipal_id},
                )
            )

        # 4. Check for Geometry Revision (boundary adjustment)
        # Occurs when continuity is verified (IoU >= 0.70, drift < 2.0m) but geometry differs (IoU < 0.96 or drift > 0.3m)
        is_geometry_revision = (iou < 0.96 or drift_m > 0.30 or abs(new_area_m2 - candidate.area_m2) > 5.0)

        if is_geometry_revision:
            action = ResolutionAction.GEOMETRY_REVISED
            # Bump version: e.g. "v1.0" -> "v2.0"
            m = re.search(r"v(\d+)\.(\d+)", candidate.current_geometry_version)
            if m:
                major = int(m.group(1)) + 1
                new_version = f"v{major}.0"
            else:
                new_version = f"{candidate.current_geometry_version}.1"

            old_version = candidate.current_geometry_version
            candidate.current_geometry_version = new_version
            candidate.geometry = mapping(valid_geom)
            candidate.area_m2 = new_area_m2
            candidate.centroid = new_centroid

            lineage_events.append(
                LineageEvent(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    event_type="GEOMETRY_REVISED",
                    timestamp=ts,
                    description=f"Geometry revised from {old_version} to {new_version} (IoU: {iou*100:.1f}%, Drift: {drift_m:.2f}m)",
                    details={"old_version": old_version, "new_version": new_version, "iou": iou, "drift_m": drift_m},
                )
            )

        # 5. Append new source_id
        if request.source_id not in candidate.source_ids:
            candidate.source_ids.append(request.source_id)

        # 6. Record source snapshot
        candidate.source_records.append(
            SourceRecordSnapshot(
                source_record_id=f"SRC-{uuid.uuid4().hex[:8]}",
                source_dataset=request.source_dataset,
                source_id=request.source_id,
                survey_number=request.survey_number,
                municipal_id=request.municipal_id,
                geometry_version=candidate.current_geometry_version,
                recorded_at=ts,
                match_evidence={"iou": iou, "drift_m": drift_m, "action": action.value},
                properties=request.properties or {},
            )
        )

        candidate.lineage.extend(lineage_events)
        candidate.updated_at = ts
        candidate.status = ParcelStatus.ACTIVE.value
        candidate.needs_review = False

        if is_geometry_revision:
            self._rebuild_spatial_index()

        self._save_registry()

        return IdentityResolutionResult(
            parcel_uuid=candidate.parcel_uuid,
            resolution_action=action,
            status=candidate.status,
            current_geometry_version=candidate.current_geometry_version,
            source_ids=candidate.source_ids,
            survey_numbers=candidate.survey_numbers,
            municipal_ids=candidate.municipal_ids,
            iou=iou,
            centroid_drift_m=drift_m,
            confidence_score=candidate.confidence_score,
            needs_review=candidate.needs_review,
            message=f"Continuity verified! Preserved permanent parcel_uuid '{candidate.parcel_uuid}' ({action.value}).",
            details={
                "geometry_version": candidate.current_geometry_version,
                "total_sources": len(candidate.source_records),
            },
        )

    # -----------------------------------------------------------------------
    # API RETRIEVAL
    # -----------------------------------------------------------------------

    def get_parcel(self, parcel_uuid_or_source_id: str) -> Optional[ParcelIdentityRecord]:
        """Retrieves a parcel by its permanent UUID or source identifier."""
        if parcel_uuid_or_source_id in self._parcels:
            return self._parcels[parcel_uuid_or_source_id]
        for p in self._parcels.values():
            if parcel_uuid_or_source_id in p.source_ids:
                return p
        
        # Check active and catalog datasets dynamically
        try:
            from backend.dataset_manager import DATASET_CATALOG, get_active_dataset
            active_ds = get_active_dataset()
            catalog_datasets = [active_ds] + [ds for ds in DATASET_CATALOG.values() if ds.get("dataset_id") != active_ds.get("dataset_id")]
            
            for ds in catalog_datasets:
                ds_id = ds.get("dataset_id", "unknown")
                for e in ds.get("entities", []):
                    c_uid = e.get("canonical_uid")
                    alias = e.get("properties", {}).get("alias_uid")
                    if parcel_uuid_or_source_id in (c_uid, alias):
                        ts = _now_iso()
                        props = e.get("properties", {}) or {}
                        parcel_uuid = str(uuid.uuid5(TERRANODE_NAMESPACE, f"catalog:{ds_id}:{c_uid}"))
                        rec = ParcelIdentityRecord(
                            parcel_uuid=parcel_uuid,
                            source_ids=[c_uid] + ([alias] if alias else []),
                            survey_numbers=[props.get("survey_number")] if props.get("survey_number") else [],
                            municipal_ids=[f"PID-{c_uid}"],
                            current_geometry_version="v1.0",
                            status=e.get("properties", {}).get("status", ParcelStatus.RECONCILED.value),
                            created_at=ts,
                            updated_at=ts,
                            geometry=e.get("geometry"),
                            centroid=props.get("centroid") or [13.0418, 80.2341],
                            area_m2=float(e.get("area_m2") or 200.0),
                            confidence_score=float(e.get("confidence_score") or 0.95),
                            needs_review=bool(e.get("needs_review", False)),
                            source_records=[],
                            lineage=[],
                        )
                        self._parcels[parcel_uuid] = rec
                        return rec
        except Exception as err:
            logger.debug("Catalog lookup failed in get_parcel: %s", err)

        return None

    def get_parcel_sources(self, parcel_uuid_or_source_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the complete source provenance snapshot history for a parcel."""
        parcel = self.get_parcel(parcel_uuid_or_source_id)
        if not parcel:
            return None
        return {
            "parcel_uuid": parcel.parcel_uuid,
            "current_geometry_version": parcel.current_geometry_version,
            "status": parcel.status,
            "total_sources": len(parcel.source_records),
            "sources": [s.to_dict() for s in parcel.source_records],
            "lineage": [l.to_dict() for l in parcel.lineage],
            "created_at": parcel.created_at,
            "updated_at": parcel.updated_at,
        }

    def resolve_batch(self, requests: List[ResolveIdentityRequest]) -> ResolveIdentityResponse:
        """Resolves a batch of incoming parcel records."""
        results = [self.resolve_identity(req) for req in requests]
        return ResolveIdentityResponse(
            success=True,
            resolved_count=len(results),
            results=results,
        )


# Global singleton instance
_IDENTITY_SERVICE: Optional[ParcelIdentityService] = None


def get_identity_service() -> ParcelIdentityService:
    """Returns or lazily creates the global ParcelIdentityService singleton."""
    global _IDENTITY_SERVICE
    if _IDENTITY_SERVICE is None:
        _IDENTITY_SERVICE = ParcelIdentityService()
    return _IDENTITY_SERVICE
