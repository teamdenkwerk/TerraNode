"""
backend/infrastructure/repository.py

Spatial repository for infrastructure features.
Loads real infrastructure layers from data/infrastructure/, maintains Shapely STRtree
spatial indexes for candidate filtering, and preserves CRS information.
Includes strict geometry validation, coordinate normalization, and feature identity retrieval.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from shapely.geometry import shape, mapping
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

from backend.infrastructure.models import (
    InfrastructureFeature,
    InfrastructureLayerMeta,
    InfrastructureType,
    VerificationStatus,
)
from backend.infrastructure.validators import validate_and_normalize_geometry
from backend.crs.transformer import determine_utm_crs, reproject_geometry

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INFRA_DIR = DATA_DIR / "infrastructure"


class InfrastructureRepository:
    """
    In-memory spatial index and feature storage for infrastructure layers.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or INFRA_DIR
        self._features: Dict[str, List[InfrastructureFeature]] = {
            t.value: [] for t in InfrastructureType
        }
        self._shapely_geoms: Dict[str, List[BaseGeometry]] = {
            t.value: [] for t in InfrastructureType
        }
        self._projected_geoms: Dict[str, Dict[str, List[BaseGeometry]]] = {
            t.value: {} for t in InfrastructureType
        }
        self._spatial_indexes: Dict[str, Optional[STRtree]] = {
            t.value: None for t in InfrastructureType
        }
        self.load_all_layers()

    def reload(self) -> None:
        """Flushes in-memory feature caches and reloads all layers from disk."""
        for t in InfrastructureType:
            self._features[t.value].clear()
            self._shapely_geoms[t.value].clear()
            self._projected_geoms[t.value].clear()
            self._spatial_indexes[t.value] = None
        self.load_all_layers()

    def load_all_layers(self) -> None:
        """Loads available GeoJSON infrastructure files from disk with spatial validation."""
        if not self.data_dir.exists():
            logger.warning("Infrastructure directory %s does not exist.", self.data_dir)
            return

        geojson_files = sorted(list(self.data_dir.rglob("*.geojson")))
        for fpath in geojson_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                features = payload.get("features", [])
                for feat in features:
                    props = feat.get("properties", {})
                    geom_raw = feat.get("geometry")
                    if not geom_raw:
                        continue

                    infra_type_raw = props.get("infrastructure_type", "").lower()
                    if infra_type_raw not in [t.value for t in InfrastructureType]:
                        fname = fpath.name.lower()
                        if "road" in fname or "centreline" in fname or "carriageway" in fname:
                            infra_type_raw = InfrastructureType.ROAD.value
                        elif "drain" in fname or "swd" in fname or "canal" in fname or "rajakaluve" in fname:
                            infra_type_raw = InfrastructureType.DRAINAGE.value
                        elif "rail" in fname or "transit" in fname or "metro" in fname:
                            infra_type_raw = InfrastructureType.RAILWAY.value
                        elif "elect" in fname or "power" in fname or "transmission" in fname or "grid" in fname:
                            infra_type_raw = InfrastructureType.ELECTRICITY.value
                        elif "water" in fname or "pipe" in fname or "pipeline" in fname:
                            infra_type_raw = InfrastructureType.WATER.value
                        elif "easement" in fname or "corridor" in fname or "utility" in fname:
                            infra_type_raw = InfrastructureType.PUBLIC_UTILITY.value
                        else:
                            continue

                    v_status_raw = props.get("verification_status", "VERIFIED").upper()
                    try:
                        v_status = VerificationStatus(v_status_raw)
                    except ValueError:
                        if "supporting" in v_status_raw.lower() or infra_type_raw == "electricity":
                            v_status = VerificationStatus.REFERENCE_ONLY
                        else:
                            v_status = VerificationStatus.VERIFIED

                    # City context hint from file path and parent directory
                    fpath_low = str(fpath).replace("\\", "/").lower()
                    if "chennai" in fpath_low or "maa" in fpath_low:
                        city_hint = "chennai"
                    elif "mumbai" in fpath_low or "bom" in fpath_low:
                        city_hint = "mumbai"
                    elif "delhi" in fpath_low or "del" in fpath_low:
                        city_hint = "delhi"
                    elif "domlur" in fpath_low or "blr" in fpath_low or "bengaluru" in fpath_low:
                        city_hint = "bengaluru"
                    else:
                        city_hint = None

                    # Geometry validation & coordinate normalization
                    try:
                        normalized_geom, s_geom = validate_and_normalize_geometry(geom_raw, city=city_hint)
                    except Exception as ve:
                        logger.warning("Geometry validation failed for %s in %s: %s", props.get("infrastructure_id"), fpath.name, ve)
                        continue

                    # Metric length calculation in projected UTM
                    metric_length = 0.0
                    try:
                        utm_crs, _ = determine_utm_crs(s_geom.centroid.x, s_geom.centroid.y)
                        utm_geom = reproject_geometry(s_geom, "EPSG:4326", utm_crs)
                        metric_length = round(float(utm_geom.length), 2)
                    except Exception as pe:
                        logger.debug("Could not compute UTM length for feature: %s", pe)

                    # Extract canonical feature_id
                    feature_id = (
                        props.get("feature_id")
                        or props.get("infrastructure_id")
                        or props.get("source_feature_id")
                        or f"INFRA-{len(self._features[infra_type_raw])+1}"
                    )

                    src_name = (
                        props.get("source_name")
                        or props.get("source")
                        or props.get("authority")
                        or props.get("operator")
                        or props.get("agency")
                        or "Authoritative Infrastructure Provider"
                    )
                    src_date = props.get("source_date") or props.get("acquisition_date") or "2026-01-01"

                    metadata_dict = dict(props.get("metadata", {}))
                    metadata_dict["feature_id"] = feature_id
                    metadata_dict["length_m"] = metric_length
                    if "road_name" in props and "road_name" not in metadata_dict:
                        metadata_dict["road_name"] = props["road_name"]
                    elif "name" in props and "road_name" not in metadata_dict and infra_type_raw == "road":
                        metadata_dict["road_name"] = props["name"]
                    if "drain_name" in props and "drain_name" not in metadata_dict:
                        metadata_dict["drain_name"] = props["drain_name"]
                    elif "name" in props and "drain_name" not in metadata_dict and infra_type_raw == "drainage":
                        metadata_dict["drain_name"] = props["name"]
                    if "width_meters" in props:
                        metadata_dict["width_m"] = props["width_meters"]
                    if "name" in props and "name" not in metadata_dict:
                        metadata_dict["name"] = props["name"]
                    if "operator" in props:
                        metadata_dict["operator"] = props["operator"]
                    if "authority" in props:
                        metadata_dict["authority"] = props["authority"]
                    if "line_type" in props:
                        metadata_dict["line_type"] = props["line_type"]
                    if "voltage" in props:
                        metadata_dict["voltage"] = props["voltage"]

                    bounds_list = [round(b, 6) for b in s_geom.bounds]
                    centroid_list = [round(s_geom.centroid.x, 6), round(s_geom.centroid.y, 6)]

                    coord_count = 0
                    if normalized_geom.get("type") == "LineString":
                        coord_count = len(normalized_geom.get("coordinates", []))
                    elif normalized_geom.get("type") == "MultiLineString":
                        coord_count = sum(len(line) for line in normalized_geom.get("coordinates", []))

                    metadata_dict["bounds"] = bounds_list
                    metadata_dict["centroid"] = centroid_list
                    metadata_dict["coord_count"] = coord_count
                    if city_hint:
                        metadata_dict["city"] = city_hint

                    # Normalize source_dataset_id for both folder-based and flat files
                    if fpath.parent != self.data_dir and fpath.parent.name.lower() in ["delhi", "mumbai", "chennai", "bengaluru"]:
                        src_ds_id = f"{fpath.stem}_{fpath.parent.name.lower()}"
                    else:
                        src_ds_id = fpath.stem

                    feature_obj = InfrastructureFeature(
                        infrastructure_id=feature_id,
                        infrastructure_type=InfrastructureType(infra_type_raw),
                        source_dataset_id=src_ds_id,
                        source_feature_id=props.get("source_feature_id", feature_id),
                        source_name=src_name,
                        source_date=src_date,
                        geometry=normalized_geom,
                        geometry_crs=props.get("geometry_crs", "EPSG:4326"),
                        verification_status=v_status,
                        metadata=metadata_dict,
                    )

                    self._features[infra_type_raw].append(feature_obj)
                    self._shapely_geoms[infra_type_raw].append(s_geom)

            except Exception as e:
                logger.error("Failed to load infrastructure file %s: %s", fpath, e)

        # Build STRtrees for loaded categories
        for infra_type, geoms in self._shapely_geoms.items():
            if geoms:
                self._spatial_indexes[infra_type] = STRtree(geoms)
                logger.info("Built STRtree for '%s' with %d features.", infra_type, len(geoms))

    @staticmethod
    def _feature_matches_city(feat: InfrastructureFeature, city: str) -> bool:
        """
        Determines if an infrastructure feature belongs to the requested city.
        Matches against city names, abbreviations, metadata tags, and AOI keywords.
        """
        if not city:
            return True
        c_low = city.lower().strip()
        meta = feat.metadata or {}
        feat_city = str(meta.get("city", "")).lower()

        if "chennai" in c_low or "maa" in c_low or "tnagar" in c_low:
            if feat_city == "chennai":
                return True
        elif "mumbai" in c_low or "bom" in c_low or "andheri" in c_low:
            if feat_city == "mumbai":
                return True
        elif "delhi" in c_low or "del" in c_low or "ncr" in c_low or "secretariat" in c_low:
            if feat_city == "delhi":
                return True
        elif "bengaluru" in c_low or "blr" in c_low or "domlur" in c_low or "ward112" in c_low or "bangalore" in c_low:
            if feat_city == "bengaluru":
                return True

        src_low = (feat.source_dataset_id or "").lower()
        meta_ds = str(meta.get("dataset_id", "")).lower()
        jurisdiction = str(meta.get("jurisdiction", "")).lower()
        authority = str(meta.get("authority", "")).lower()
        combined = f"{src_low} {meta_ds} {jurisdiction} {authority}"

        # Chennai / Madras
        if "chennai" in c_low or "maa" in c_low or "tnagar" in c_low:
            return "chennai" in combined or "maa" in combined or "tnagar" in combined or "gcc" in combined

        # Mumbai / Bombay
        if "mumbai" in c_low or "bom" in c_low or "andheri" in c_low:
            return "mumbai" in combined or "bom" in combined or "andheri" in combined or "mcgm" in combined or "mmrda" in combined

        # Delhi NCR / Central Secretariat
        if "delhi" in c_low or "del" in c_low or "ncr" in c_low or "secretariat" in c_low:
            return "delhi" in combined or "del" in combined or "dda" in combined or "ndmc" in combined or "cpwd" in combined or "dmrc" in combined

        # Bengaluru / Bangalore / Domlur
        if "bengaluru" in c_low or "blr" in c_low or "domlur" in c_low or "ward112" in c_low or "bangalore" in c_low:
            return "domlur" in combined or "bengaluru" in combined or "blr" in combined or "bbmp" in combined

        return c_low in combined

    def get_features_by_type(self, infra_type: str, city: Optional[str] = None) -> List[InfrastructureFeature]:
        feats = self._features.get(infra_type, [])
        if not city:
            return feats
        return [f for f in feats if self._feature_matches_city(f, city)]

    def get_feature_by_id(self, feature_id: str, city: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single infrastructure feature by ID with comprehensive spatial metadata.
        Matches feature_id, infrastructure_id, or source_feature_id.
        """
        target_id = str(feature_id).strip().lower()
        for itype, feats in self._features.items():
            for idx, feat in enumerate(feats):
                fid = (feat.metadata.get("feature_id") or feat.infrastructure_id or "").lower()
                inf_id = (feat.infrastructure_id or "").lower()
                src_id = (feat.source_feature_id or "").lower()

                if target_id in (fid, inf_id, src_id):
                    # Check city match if city provided
                    if city and not self._feature_matches_city(feat, city):
                        continue

                    s_geom = self._shapely_geoms[itype][idx]
                    return {
                        "type": "Feature",
                        "id": feat.infrastructure_id,
                        "properties": {
                            "feature_id": feat.metadata.get("feature_id", feat.infrastructure_id),
                            "infrastructure_id": feat.infrastructure_id,
                            "infrastructure_type": feat.infrastructure_type.value,
                            "source_dataset_id": feat.source_dataset_id,
                            "source_feature_id": feat.source_feature_id,
                            "source_name": feat.source_name,
                            "source_date": feat.source_date,
                            "name": feat.metadata.get("road_name") or feat.metadata.get("drain_name") or feat.source_name,
                            "road_name": feat.metadata.get("road_name"),
                            "drain_name": feat.metadata.get("drain_name"),
                            "width_m": feat.metadata.get("width_m"),
                            "verification_status": feat.verification_status.value,
                            "original_crs": feat.geometry_crs,
                            "normalized_crs": "EPSG:4326",
                            "geometry_bounds": [round(b, 6) for b in s_geom.bounds],
                            "geometry_centroid": [round(s_geom.centroid.x, 6), round(s_geom.centroid.y, 6)],
                            "length_meters": feat.metadata.get("length_m", 0.0),
                            "coordinate_count": feat.metadata.get("coord_count", 0),
                            "metadata": feat.metadata,
                        },
                        "geometry": feat.geometry,
                    }
        return None

    def get_all_features_geojson(
        self,
        infra_type: Optional[str] = None,
        city: Optional[str] = None,
        diagnostic: bool = False,
    ) -> Dict[str, Any]:
        """Returns GeoJSON FeatureCollection for frontend rendering, scoped strictly to the requested or active city."""
        types_to_include = [infra_type] if infra_type else [t.value for t in InfrastructureType]
        all_features = []

        for itype in types_to_include:
            type_feats = self._features.get(itype, [])
            for idx, feat in enumerate(type_feats):
                # Strictly isolate infrastructure to requested city
                if city and not self._feature_matches_city(feat, city):
                    continue

                s_geom = self._shapely_geoms[itype][idx]
                feat_id = feat.metadata.get("feature_id", feat.infrastructure_id)
                name = feat.metadata.get("road_name") or feat.metadata.get("drain_name") or feat.source_name

                feature_dict = {
                    "type": "Feature",
                    "id": feat_id,
                    "properties": {
                        "feature_id": feat_id,
                        "infrastructure_id": feat.infrastructure_id,
                        "infrastructure_type": feat.infrastructure_type.value,
                        "source_dataset_id": feat.source_dataset_id,
                        "source_feature_id": feat.source_feature_id,
                        "source_name": feat.source_name,
                        "source_date": feat.source_date,
                        "verification_status": feat.verification_status.value,
                        "name": name,
                        "road_name": feat.metadata.get("road_name"),
                        "drain_name": feat.metadata.get("drain_name"),
                        "width_m": feat.metadata.get("width_m"),
                        "geometry_bounds": [round(b, 6) for b in s_geom.bounds],
                        "geometry_centroid": [round(s_geom.centroid.x, 6), round(s_geom.centroid.y, 6)],
                        "length_meters": feat.metadata.get("length_m", 0.0),
                        "coordinate_count": feat.metadata.get("coord_count", 0),
                        "original_crs": feat.geometry_crs,
                        "normalized_crs": "EPSG:4326",
                        "metadata": feat.metadata,
                    },
                    "geometry": feat.geometry,
                }
                all_features.append(feature_dict)

        result: Dict[str, Any] = {
            "type": "FeatureCollection",
            "features": all_features,
        }

        if diagnostic:
            result["diagnostic"] = {
                "active_city": city,
                "layer_type": infra_type,
                "feature_count": len(all_features),
                "crs_standard": "EPSG:4326 (WGS84 lon, lat)",
                "validation_status": "All geometries validated and normalized",
            }

        return result

    def get_layer_metadata(self, city: Optional[str] = None) -> List[InfrastructureLayerMeta]:
        """Lists supported categories with feature counts and availability notes scoped to city."""
        result = []
        layer_specs = [
            (
                InfrastructureType.ROAD.value,
                "Public Road Network",
                "Official Municipal & Town Planning Road Network GIS",
                "DATA NOT AVAILABLE — Requires municipal road network dataset.",
            ),
            (
                InfrastructureType.DRAINAGE.value,
                "Stormwater Drainage (SWD)",
                "Stormwater Drain Network (Canal / Rajakaluve)",
                "DATA NOT AVAILABLE — Requires municipal stormwater drainage dataset.",
            ),
            (
                InfrastructureType.WATER.value,
                "Water Supply Pipeline",
                "Municipal Water Supply & Sewerage Board Pipeline Network",
                "DATA NOT AVAILABLE — Requires municipal water pipeline network GIS dataset (CMWSSB / BWSSB).",
            ),
            (
                InfrastructureType.ELECTRICITY.value,
                "Electricity Transmission",
                "Overhead Transmission Lines & Power Grid Corridors",
                "DATA NOT AVAILABLE — Requires high-voltage power transmission line dataset.",
            ),
            (
                InfrastructureType.RAILWAY.value,
                "Railway / Transit",
                "Railway Track Right-of-Way & Rapid Transit Corridor",
                "DATA NOT AVAILABLE — Requires railway right-of-way and metro alignment GIS dataset.",
            ),
            (
                InfrastructureType.PUBLIC_UTILITY.value,
                "Public Utility Easement",
                "Municipal Underground Utility Easements & Statutory Planning Corridors",
                "NO AUTHORITATIVE EASEMENT DATA — Easement boundaries require municipal statutory planning or land-use maps. Upload a shapefile or GeoJSON to enable easement analysis.",
            ),
        ]

        for itype_val, display_name, active_desc, missing_desc in layer_specs:
            all_feats = self._features.get(itype_val, [])
            if city:
                feats = [f for f in all_feats if self._feature_matches_city(f, city)]
            else:
                feats = all_feats

            is_avail = len(feats) > 0
            sources = list({f.source_name for f in feats}) if is_avail else []

            if is_avail:
                is_supporting = (
                    itype_val == InfrastructureType.ELECTRICITY.value
                    or any(f.verification_status == VerificationStatus.REFERENCE_ONLY for f in feats)
                    or any("supporting" in f.source_name.lower() or "osm" in f.source_name.lower() for f in feats)
                )
                v_status = "SUPPORTING_DATA" if is_supporting else "VERIFIED"
                reason = "SUPPORTING DATA — NOT AN OFFICIAL GOVERNMENT GIS LAYER" if is_supporting else None
            else:
                if itype_val == InfrastructureType.PUBLIC_UTILITY.value:
                    v_status = "NO_AUTHORITATIVE_DATA"
                else:
                    v_status = "NOT_AVAILABLE"
                reason = missing_desc

            result.append(InfrastructureLayerMeta(
                type=itype_val,
                display_name=display_name,
                feature_count=len(feats),
                is_available=is_avail,
                verification_status=v_status,
                sources=sources,
                unavailability_reason=reason,
            ))

        return result

    def query_spatial_candidates(
        self,
        infra_type: str,
        query_bbox_geom: BaseGeometry,
        city: Optional[str] = None,
    ) -> List[Tuple[InfrastructureFeature, BaseGeometry]]:
        """
        Uses STRtree bounding-box query to retrieve candidates, avoiding O(N) table scan.
        Filters candidates to the active city if specified.
        """
        tree = self._spatial_indexes.get(infra_type)
        if not tree or not self._shapely_geoms.get(infra_type):
            return []

        # Query indices intersecting the parcel bounding box / envelope
        hits = tree.query(query_bbox_geom)
        candidates = []
        for idx in hits:
            feature_obj = self._features[infra_type][idx]
            if city and not self._feature_matches_city(feature_obj, city):
                continue

            geom = self._shapely_geoms[infra_type][idx]
            candidates.append((feature_obj, geom))

        return candidates

    def import_user_layer(
        self,
        file_content: str,
        filename: str,
        dataset_id: str,
        layer_type: str,
        source_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingests user-uploaded GeoJSON layer for a specific category (Tier 4).
        Validates geometry, assigns UNVERIFIED status, saves to disk, and updates spatial index.
        """
        from datetime import datetime, timezone
        try:
            payload = json.loads(file_content)
        except Exception as e:
            raise ValueError(f"Invalid JSON file format: {e}")

        features = payload.get("features", [])
        if not features and payload.get("type") == "Feature":
            features = [payload]

        if not features:
            raise ValueError("No features found in uploaded GeoJSON")

        ds_low = dataset_id.lower()
        if "chennai" in ds_low or "maa" in ds_low:
            city_hint = "chennai"
        elif "mumbai" in ds_low or "bom" in ds_low:
            city_hint = "mumbai"
        elif "delhi" in ds_low or "del" in ds_low:
            city_hint = "delhi"
        else:
            city_hint = "bengaluru"
        imported_count = 0
        norm_features = []
        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for idx, feat in enumerate(features):
            geom_raw = feat.get("geometry")
            if not geom_raw:
                continue
            props = dict(feat.get("properties", {}))

            try:
                norm_geom, s_geom = validate_and_normalize_geometry(geom_raw, city=city_hint)
            except Exception as ve:
                logger.warning("User layer feature %d failed validation: %s", idx, ve)
                continue

            metric_len = 0.0
            try:
                utm_crs, _ = determine_utm_crs(s_geom.centroid.x, s_geom.centroid.y)
                utm_geom = reproject_geometry(s_geom, "EPSG:4326", utm_crs)
                metric_len = round(float(utm_geom.length), 2)
            except Exception:
                pass

            fid = props.get("id") or props.get("feature_id") or f"USER-{layer_type.upper()}-{idx+1}"
            props["feature_id"] = fid
            props["length_m"] = metric_len

            feature_obj = InfrastructureFeature(
                infrastructure_id=fid,
                infrastructure_type=InfrastructureType(layer_type),
                source_dataset_id=f"user_{dataset_id}_{layer_type}",
                source_feature_id=str(props.get("source_feature_id", fid)),
                source_name=source_name or f"User Upload: {Path(filename).stem}",
                source_date=now_date,
                geometry=norm_geom,
                geometry_crs="EPSG:4326",
                verification_status=VerificationStatus.UNVERIFIED,
                metadata=props,
            )

            self._features[layer_type].append(feature_obj)
            self._shapely_geoms[layer_type].append(s_geom)
            imported_count += 1

            norm_features.append({
                "type": "Feature",
                "properties": {
                    **props,
                    "infrastructure_id": fid,
                    "infrastructure_type": layer_type,
                    "source_dataset_id": f"user_{dataset_id}_{layer_type}",
                    "source_name": source_name or f"User Upload: {Path(filename).stem}",
                    "verification_status": "UNVERIFIED",
                },
                "geometry": norm_geom,
            })

        # Rebuild STRtree for this layer type
        if self._shapely_geoms[layer_type]:
            self._spatial_indexes[layer_type] = STRtree(self._shapely_geoms[layer_type])

        # Save to disk
        out_file = self.data_dir / f"user_{dataset_id}_{layer_type}.geojson"
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump({"type": "FeatureCollection", "features": norm_features}, f, indent=2)
        except Exception as se:
            logger.warning("Could not persist user uploaded layer to %s: %s", out_file, se)

        return {
            "success": True,
            "layer_type": layer_type,
            "dataset_id": dataset_id,
            "imported_features": imported_count,
            "file_saved": str(out_file.name),
            "verification_status": "UNVERIFIED",
            "message": f"Successfully ingested {imported_count} features into {layer_type} layer (Tier 4 User Upload).",
        }


# Singleton instance
_repo_instance: Optional[InfrastructureRepository] = None

def get_infrastructure_repository() -> InfrastructureRepository:
    global _repo_instance
    if _repo_instance is None:
        _repo_instance = InfrastructureRepository()
    return _repo_instance
