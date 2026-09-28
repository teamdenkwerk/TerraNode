"""
matching/normalize.py

Validates/cleans a source GeoDataFrame (as produced by ingestion/*.py, in
EPSG:4326) and inserts it into raw_features, reprojected into the matching
SRID (config.MATCH_SRID) — every downstream matching/reconciliation
calculation runs in that projected CRS, never in lat/lon degrees.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import geopandas as gpd

from config import CRS_LATLON, CRS_PROJECTED, MATCH_SRID
from db.connection import get_connection

REQUIRED_COLUMNS = ["entity_uid", "source", "feature_type", "building_type", "area_m2", "geometry"]


def normalize_layer(gdf: gpd.GeoDataFrame, source_name: str) -> gpd.GeoDataFrame:
    """Cleans geometry, ensures CRS, recomputes area/centroid in the
    projected CRS, and reprojects the geometry column itself into
    CRS_PROJECTED (so insert_raw_features can write it as-is)."""
    missing = [c for c in REQUIRED_COLUMNS if c not in gdf.columns]
    if missing:
        raise ValueError(f"[{source_name}] Missing required columns: {missing}")

    before = len(gdf)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()].copy()

    invalid_mask = ~gdf.geometry.is_valid
    if invalid_mask.any():
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].buffer(0)

    after = len(gdf)
    if before != after:
        print(f"[{source_name}] Dropped {before - after} invalid/empty geometries")

    gdf = gdf.set_crs(CRS_LATLON) if gdf.crs is None else gdf.to_crs(CRS_LATLON)

    gdf_proj = gdf.to_crs(CRS_PROJECTED)
    gdf["area_m2"] = gdf_proj.geometry.area
    centroid_proj = gdf_proj.geometry.centroid
    gdf["centroid_x"] = centroid_proj.x
    gdf["centroid_y"] = centroid_proj.y
    gdf["geometry"] = gdf_proj.geometry  # store the PROJECTED geometry — raw_features.geom is SRID 32643

    if "extraction_confidence" not in gdf.columns:
        gdf["extraction_confidence"] = None

    return gdf


def insert_raw_features(gdf: gpd.GeoDataFrame, tile_id: str | None = None) -> None:
    """Bulk-inserts a normalized (projected-CRS) GeoDataFrame into
    raw_features. ON CONFLICT (entity_uid) DO NOTHING makes re-runs safe."""
    if gdf.empty:
        print("[normalize] Nothing to insert — empty GeoDataFrame")
        return

    rows = [
        (
            row["entity_uid"],
            row["source"],
            row["feature_type"],
            row.get("building_type"),
            float(row["area_m2"]) if row["area_m2"] is not None else None,
            float(row["extraction_confidence"]) if row.get("extraction_confidence") not in (None, "") else None,
            float(row["centroid_x"]),
            float(row["centroid_y"]),
            row.geometry.wkt,
            tile_id,
        )
        for _, row in gdf.iterrows()
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO raw_features
                    (entity_uid, source, feature_type, building_type, area_m2,
                     extraction_confidence, centroid_x, centroid_y, geom, tile_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, {MATCH_SRID}), %s)
                ON CONFLICT (entity_uid) DO NOTHING
                """,
                rows,
            )
        conn.commit()

    source = gdf["source"].iloc[0] if len(gdf) else "n/a"
    print(f"[normalize] Inserted up to {len(rows)} rows into raw_features (source={source})")