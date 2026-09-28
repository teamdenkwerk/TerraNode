"""
ingestion/fetch_uploaded_file.py

Loads a user-uploaded GeoJSON or zipped-shapefile as a third raw_features
source, normalized to the same schema fetch_osm_buildings /
fetch_google_open_buildings produce.

Unlike those two, this doesn't query a bbox — it trusts whatever geometry
is in the file. If it falls outside DISTRICT_BBOX it still gets inserted
into raw_features, but will never spatially match anything already in the
district (ST_Intersects during matching just won't fire for it) — a silent
no-op, not a crash, so an out-of-area upload won't break the pipeline, it'll
just sit there as an unmatched single-source entity.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import geopandas as gpd

from config import CRS_LATLON, CRS_PROJECTED

SOURCE_NAME = "user_upload"


def fetch_uploaded_buildings(file_path: str) -> gpd.GeoDataFrame:
    path = Path(file_path)
    print(f"[UPLOAD] Loading uploaded file: {path}")

    gdf = gpd.read_file(f"zip://{path}") if path.suffix.lower() == ".zip" else gpd.read_file(path)

    if gdf.empty:
        raise RuntimeError(f"Uploaded file {path} contains no features")

    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy().reset_index(drop=True)
    if gdf.empty:
        raise RuntimeError(f"Uploaded file {path} has no Polygon/MultiPolygon geometries")

    gdf = gdf.set_crs(CRS_LATLON) if gdf.crs is None else gdf.to_crs(CRS_LATLON)
    area_m2 = gdf.to_crs(CRS_PROJECTED).geometry.area

    gdf["source"] = SOURCE_NAME
    gdf["entity_uid"] = f"{SOURCE_NAME}:{path.stem}:" + gdf.index.astype(str)
    gdf["feature_type"] = "building"
    gdf["building_type"] = gdf["building_type"] if "building_type" in gdf.columns else "unknown"
    gdf["area_m2"] = area_m2
    # Only populated if the uploaded file itself carries a confidence column —
    # arbitrary uploads have no guaranteed native confidence signal.
    gdf["extraction_confidence"] = gdf["confidence"] if "confidence" in gdf.columns else None

    keep = ["entity_uid", "source", "feature_type", "building_type",
            "area_m2", "extraction_confidence", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    print(f"[UPLOAD] Loaded {len(gdf)} features from upload")
    return gdf