"""
backend/infrastructure/service.py

High-level Infrastructure Intelligence service for parcel analysis.
Orchestrates spatial indexing, multi-category evaluation, and transparent metrics reporting.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from backend.infrastructure.models import (
    InfrastructureIntersectionResult,
    InfrastructureSummary,
    InfrastructureType,
    IntersectionTerminology,
    ParcelInfrastructureResponse,
)
from backend.infrastructure.intersection import evaluate_single_intersection
from backend.infrastructure.repository import get_infrastructure_repository
from backend.identity.identity_service import get_identity_service

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InfrastructureIntelligenceService:
    def __init__(self):
        self.repo = get_infrastructure_repository()

    def analyze_parcel(
        self,
        parcel_uuid: str,
        parcel_geometry: Optional[Dict[str, Any]] = None,
    ) -> ParcelInfrastructureResponse:
        """
        Executes complete spatial infrastructure intelligence analysis for a parcel.
        """
        start_time = time.perf_counter()

        # Resolve geometry from registry if not provided directly
        geom_dict = parcel_geometry
        if not geom_dict:
            id_svc = get_identity_service()
            parcel_record = id_svc.get_parcel(parcel_uuid)
            if parcel_record:
                geom_dict = parcel_record.geometry
            else:
                # Check if caller passed a canonical_uid like 'BLR-101'
                for p in id_svc._parcels.values():
                    if parcel_uuid in p.source_ids:
                        geom_dict = p.geometry
                        break

        if not geom_dict:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ParcelInfrastructureResponse(
                parcel_uuid=parcel_uuid,
                summary=InfrastructureSummary(detected=0, not_detected=0, unavailable=len(InfrastructureType)),
                results=[
                    InfrastructureIntersectionResult(
                        infrastructure_type=t.value,
                        intersection_exists=False,
                        intersection_status=IntersectionTerminology.DATA_UNAVAILABLE.value,
                        calculation_timestamp=_now_iso(),
                        details={"error": "Parcel geometry not found in identity registry"},
                    )
                    for t in InfrastructureType
                ],
                execution_time_ms=elapsed_ms,
            )

        p_geom = shape(geom_dict)
        if p_geom.is_empty:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return ParcelInfrastructureResponse(
                parcel_uuid=parcel_uuid,
                summary=InfrastructureSummary(detected=0, not_detected=0, unavailable=len(InfrastructureType)),
                results=[],
                execution_time_ms=elapsed_ms,
            )

        # Determine city context
        c_uid = str(parcel_uuid).upper()
        if "CHN" in c_uid or "MAA" in c_uid or "TNAGAR" in c_uid:
            city = "chennai"
        elif "MUM" in c_uid or "BOM" in c_uid or "ANDHERI" in c_uid:
            city = "mumbai"
        elif "DEL" in c_uid or "NCR" in c_uid or "SECRETARIAT" in c_uid:
            city = "delhi"
        elif "BLR" in c_uid or "DOM" in c_uid or "WARD112" in c_uid:
            city = "bengaluru"
        elif p_geom.centroid.x > 79.5:
            city = "chennai"
        elif 72.0 <= p_geom.centroid.x <= 73.5 and 18.5 <= p_geom.centroid.y <= 19.5:
            city = "mumbai"
        elif 76.5 <= p_geom.centroid.x <= 77.5 and 28.0 <= p_geom.centroid.y <= 29.0:
            city = "delhi"
        else:
            city = "bengaluru"

        # Buffer for spatial bounding box query (e.g. ~100 meters buffer in degrees)
        query_box = p_geom.envelope.buffer(0.001)

        results: List[InfrastructureIntersectionResult] = []
        detected_count = 0
        not_detected_count = 0
        unavailable_count = 0

        # Descriptions for categories without real datasets
        missing_descriptions = {
            InfrastructureType.WATER.value: "DATA NOT AVAILABLE — Requires municipal water pipeline network GIS dataset (CMWSSB / BWSSB).",
            InfrastructureType.PUBLIC_UTILITY.value: "NO AUTHORITATIVE EASEMENT DATA — Easement boundaries require municipal statutory planning or land-use maps. Upload a shapefile or GeoJSON to enable easement analysis.",
            InfrastructureType.ELECTRICITY.value: "DATA NOT AVAILABLE — Requires high-voltage power transmission line dataset.",
            InfrastructureType.RAILWAY.value: "DATA NOT AVAILABLE — Requires railway right-of-way and metro alignment GIS dataset.",
            InfrastructureType.ROAD.value: "DATA NOT AVAILABLE — Requires municipal road network dataset.",
            InfrastructureType.DRAINAGE.value: "DATA NOT AVAILABLE — Requires municipal stormwater drainage dataset.",
        }

        for itype in InfrastructureType:
            type_str = itype.value
            available_feats = self.repo.get_features_by_type(type_str, city=city)

            if not available_feats:
                # Honestly report unavailable state (Rule #3, #4 and #5)
                unavailable_count += 1
                reason = missing_descriptions.get(type_str, "Dataset not provided in current repository.")
                is_easement = (type_str == InfrastructureType.PUBLIC_UTILITY.value)
                results.append(
                    InfrastructureIntersectionResult(
                        infrastructure_type=type_str,
                        infrastructure_id=None,
                        intersection_exists=False,
                        intersection_status=IntersectionTerminology.DATA_UNAVAILABLE.value,
                        intersection_length_m=0.0,
                        intersection_area_m2=0.0,
                        intersection_percentage=0.0,
                        minimum_distance_m=0.0,
                        source_dataset=None,
                        source_feature_id=None,
                        source_name=None,
                        verification_status="NO_AUTHORITATIVE_DATA" if is_easement else "NOT_AVAILABLE",
                        calculation_timestamp=_now_iso(),
                        details={
                            "is_available": False,
                            "required_dataset": reason,
                            "requires_upload": True,
                            "upload_hint": "Upload GeoJSON / Shapefile to enable analysis",
                            "status_badge": "NO AUTHORITATIVE EASEMENT DATA" if is_easement else "DATA NOT AVAILABLE",
                        },
                    )
                )
                continue

            # Query STRtree candidates in bounding envelope
            candidates = self.repo.query_spatial_candidates(type_str, query_box, city=city)
            if not candidates:
                # Features exist in the city; compute distance to nearest feature in available_feats
                from backend.crs.transformer import determine_utm_crs, reproject_geometry
                utm_crs, _ = determine_utm_crs(p_geom.centroid.x, p_geom.centroid.y)
                p_utm = reproject_geometry(p_geom, from_crs="EPSG:4326", to_crs=utm_crs)
                best_feat = available_feats[0]
                min_dist_m = 999.0

                for f in available_feats:
                    try:
                        s_f_geom = shape(f.geometry)
                        f_utm = reproject_geometry(s_f_geom, from_crs="EPSG:4326", to_crs=utm_crs)
                        d = round(float(p_utm.distance(f_utm)), 2)
                        if d < min_dist_m:
                            min_dist_m = d
                            best_feat = f
                    except Exception:
                        continue

                not_detected_count += 1
                is_supporting = (
                    best_feat.verification_status.value == "REFERENCE_ONLY"
                    or type_str == InfrastructureType.ELECTRICITY.value
                    or "supporting" in best_feat.source_name.lower()
                    or "osm" in best_feat.source_name.lower()
                )
                v_stat = "SUPPORTING_DATA" if is_supporting else "AVAILABLE"
                feat_name = (
                    best_feat.metadata.get("name")
                    or best_feat.metadata.get("road_name")
                    or best_feat.metadata.get("drain_name")
                    or best_feat.source_name
                )

                results.append(
                    InfrastructureIntersectionResult(
                        infrastructure_type=type_str,
                        infrastructure_id=best_feat.infrastructure_id,
                        intersection_exists=False,
                        intersection_status=IntersectionTerminology.PROXIMITY_DETECTED.value if min_dist_m < 25.0 else IntersectionTerminology.NO_INTERSECTION.value,
                        intersection_length_m=0.0,
                        intersection_area_m2=0.0,
                        intersection_percentage=0.0,
                        minimum_distance_m=min_dist_m,
                        source_dataset=best_feat.source_dataset_id,
                        source_feature_id=best_feat.source_feature_id,
                        source_name=best_feat.source_name,
                        verification_status=v_stat,
                        calculation_timestamp=_now_iso(),
                        details={
                            "is_available": True,
                            "is_supporting": is_supporting,
                            "supporting_disclaimer": "SUPPORTING DATA — NOT AN OFFICIAL GOVERNMENT GIS LAYER" if is_supporting else None,
                            "nearest_feature_name": feat_name,
                            "nearest_feature_id": best_feat.infrastructure_id,
                            "geometry": best_feat.geometry,
                        },
                    )
                )
                continue

            # Evaluate against candidates
            best_res: Optional[InfrastructureIntersectionResult] = None
            any_intersect = False

            for feat, geom in candidates:
                eval_res = evaluate_single_intersection(p_geom, feat, geom)
                if eval_res.intersection_exists:
                    any_intersect = True
                    # If multiple intersections, pick the one with largest affected length or area
                    if not best_res or (eval_res.intersection_length_m > best_res.intersection_length_m or eval_res.intersection_area_m2 > best_res.intersection_area_m2):
                        best_res = eval_res
                elif not any_intersect:
                    # Keep track of the closest feature if no intersection
                    if not best_res or eval_res.minimum_distance_m < best_res.minimum_distance_m:
                        best_res = eval_res

            if any_intersect:
                detected_count += 1
            else:
                not_detected_count += 1

            if best_res:
                is_supporting = (
                    best_res.verification_status == "REFERENCE_ONLY"
                    or best_res.infrastructure_type == InfrastructureType.ELECTRICITY.value
                    or "supporting" in (best_res.source_name or "").lower()
                    or "osm" in (best_res.source_name or "").lower()
                )
                if is_supporting:
                    best_res.verification_status = "SUPPORTING_DATA"
                    best_res.details["is_supporting"] = True
                    best_res.details["supporting_disclaimer"] = "SUPPORTING DATA — NOT AN OFFICIAL GOVERNMENT GIS LAYER"
                results.append(best_res)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return ParcelInfrastructureResponse(
            parcel_uuid=parcel_uuid,
            summary=InfrastructureSummary(
                detected=detected_count,
                not_detected=not_detected_count,
                unavailable=unavailable_count,
            ),
            results=results,
            execution_time_ms=elapsed_ms,
        )


# Singleton
_service_instance: Optional[InfrastructureIntelligenceService] = None

def get_infrastructure_service() -> InfrastructureIntelligenceService:
    global _service_instance
    if _service_instance is None:
        _service_instance = InfrastructureIntelligenceService()
    return _service_instance
