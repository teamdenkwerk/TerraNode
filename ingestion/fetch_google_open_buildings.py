"""
ingestion/fetch_google_open_buildings.py

Fetches Google Open Buildings polygons for the full district bbox.

Requires (one-time setup, before the demo):
    1. A Google Earth Engine account: https://earthengine.google.com
    2. `earthengine authenticate` run once
    3. EE_PROJECT set in config.py

Usage:
    python -m ingestion.fetch_google_open_buildings
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import ee
import geemap
import geopandas as gpd
import pandas as pd

from config import DISTRICT_BBOX, EE_PROJECT, CRS_LATLON, CRS_PROJECTED, SCRATCH_DIR

# ee.data.computeValue / getInfo() hard-caps any single collection query at
# 5000 elements server-side — this has nothing to do with bbox size in km^2,
# only feature *count*. Dense urban areas (like our Koramangala/HSR/
# Indiranagar test patch) can cross this well before the bbox looks "big".
# Fixed at district scale too: this is exactly why the architecture always
# planned to tile district imagery — we're just tiling this fetch step too,
# recursively, instead of guessing a fixed grid size upfront.
_MAX_ELEMENTS_ERROR_SNIPPET = "accumulating over 5000 elements"


def _fetch_tile_geojson(min_lon, min_lat, max_lon, max_lat, depth=0):
    """Fetch one bbox tile; recursively split into 4 quadrants on overflow."""
    region = ee.Geometry.BBox(min_lon, min_lat, max_lon, max_lat)
    buildings_fc = ee.FeatureCollection(
        "GOOGLE/Research/open-buildings/v3/polygons"
    ).filterBounds(region)

    tmp_path = str(SCRATCH_DIR / f"_gob_raw_tmp_{depth}_{min_lon}_{min_lat}.geojson")
    try:
        geemap.ee_to_geojson(buildings_fc, filename=tmp_path)
    except Exception as e:
        if _MAX_ELEMENTS_ERROR_SNIPPET in str(e):
            indent = "  " * (depth + 1)
            print(f"{indent}[GOB] Tile too dense at depth {depth}, splitting into 4...")
            mid_lon = (min_lon + max_lon) / 2
            mid_lat = (min_lat + max_lat) / 2
            gdfs = []
            for sub in [
                (min_lon, min_lat, mid_lon, mid_lat),
                (mid_lon, min_lat, max_lon, mid_lat),
                (min_lon, mid_lat, mid_lon, max_lat),
                (mid_lon, mid_lat, max_lon, max_lat),
            ]:
                gdfs.append(_fetch_tile_geojson(*sub, depth=depth + 1))
            return pd.concat(gdfs, ignore_index=True)
        raise

    gdf = gpd.read_file(tmp_path)
    return gdf


def fetch_google_open_buildings(
    bbox: tuple[float, float, float, float] = DISTRICT_BBOX,
    project: str = EE_PROJECT,
) -> gpd.GeoDataFrame:
    ee.Initialize(project=project)

    min_lon, min_lat, max_lon, max_lat = bbox
    print(f"[GOB] Querying Google Open Buildings for district bbox: {bbox}")

    gdf = _fetch_tile_geojson(min_lon, min_lat, max_lon, max_lat)

    if gdf.empty:
        raise RuntimeError(
            "No Google Open Buildings found for this district bbox — check "
            "coverage or EE authentication."
        )

    gdf = gdf.set_crs(CRS_LATLON) if gdf.crs is None else gdf.to_crs(CRS_LATLON)

    # Tiles can share buildings that sit on a shared boundary (filterBounds
    # matches anything touching the tile, so a border building can come back
    # from more than one tile) — dedupe on exact geometry before proceeding.
    before = len(gdf)
    gdf["_geom_wkt"] = gdf.geometry.apply(lambda g: g.wkt)
    gdf = gdf.drop_duplicates(subset="_geom_wkt").drop(columns="_geom_wkt")
    gdf = gdf.reset_index(drop=True)
    if before != len(gdf):
        print(f"[GOB] Deduplicated {before - len(gdf)} boundary-duplicate buildings")

    area_m2 = gdf.to_crs(CRS_PROJECTED).geometry.area

    gdf["source"] = "google_open_buildings"
    gdf["entity_uid"] = "gob:" + gdf.index.astype(str)
    gdf["feature_type"] = "building"
    gdf["building_type"] = "unknown"
    gdf["area_m2"] = area_m2
    # Google Open Buildings ships its own per-polygon confidence — this is
    # exactly the "AI extraction confidence" signal confidence_score.py
    # looks for, so keep the column name aligned with that expectation.
    if "confidence" in gdf.columns:
        gdf["extraction_confidence"] = gdf["confidence"]
    else:
        gdf["extraction_confidence"] = None

    keep = ["entity_uid", "source", "feature_type", "building_type",
            "area_m2", "extraction_confidence", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    print(f"[GOB] Fetched {len(gdf)} buildings")
    return gdf


if __name__ == "__main__":
    result = fetch_google_open_buildings()
    print(result.head())
    print(f"Total area: {result['area_m2'].sum():,.0f} m^2")