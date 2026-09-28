"""
ingestion/fetch_osm_buildings.py

Fetches OSM building footprints for the full district bbox (config.DISTRICT_BBOX).
No registration needed — run this first to confirm bbox/environment work.

Usage:
    python -m ingestion.fetch_osm_buildings
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import geopandas as gpd
import osmnx as ox


import socket

# Workaround: overpass-api.de resolves to two IPs, and one of them
# (162.55.144.139) is consistently unreachable from this network — Python's
# DNS/connection-pool logic sticks to whichever IP it picks first, unlike
# curl's happy-eyeballs behavior, so retries alone don't help. Force
# resolution straight to the known-good IP for this host only.
_original_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, *args, **kwargs):
    if host == "overpass-api.de":
        host = "65.109.112.52"
    return _original_getaddrinfo(host, *args, **kwargs)

socket.getaddrinfo = _patched_getaddrinfo

ox.settings.requests_headers = {"User-Agent": "geo-reconciliation-hackathon/1.0"}
ox.settings.requests_timeout = 20  # fail fast on a bad IP instead of waiting 180s

# Back to the default Overpass instance — confirmed working once the
# User-Agent header is set (the earlier 406 was the actual bug, not the
# server itself). One of its IPs is unreachable from this network, but
# the retry loop below handles that by giving DNS/connection pooling a
# few more chances to land on the reachable IP.
# ox.settings.overpass_url = "https://overpass.openstreetmap.ru/api"
# ox.settings.overpass_url = "https://overpass.kumi.systems/api"

from config import DISTRICT_BBOX, CRS_LATLON, CRS_PROJECTED


def fetch_osm_buildings(bbox: tuple[float, float, float, float] = DISTRICT_BBOX) -> gpd.GeoDataFrame:
    """bbox: (min_lon, min_lat, max_lon, max_lat). Returns a GeoDataFrame
    matching the raw_features schema (source, entity_uid, feature_type,
    building_type, area_m2, extraction_confidence, geometry) in EPSG:4326 —
    matching/normalize.py handles the reprojection into the matching SRID."""
    min_lon, min_lat, max_lon, max_lat = bbox
    print(f"[OSM] Querying buildings for district bbox: {bbox}")

    # Retry loop: one of Overpass's server IPs is unreachable from this
    # network and requests doesn't fail over to the working IP on its own
    # (unlike curl's "happy eyeballs" behavior) — retrying lets DNS/connection
    # pooling land on a reachable IP within a few attempts.
    gdf = None
    for attempt in range(5):
        try:
            gdf = ox.features_from_bbox(bbox=(min_lon, min_lat, max_lon, max_lat), tags={"building": True})
            break
        except Exception as e:
            print(f"[OSM] Attempt {attempt + 1}/5 failed: {e}")
            if attempt == 4:
                raise
            time.sleep(3)

    if gdf.empty:
        raise RuntimeError("No OSM buildings found — check DISTRICT_BBOX in config.py")

    gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy().reset_index()
    gdf = gdf.set_crs(CRS_LATLON) if gdf.crs is None else gdf.to_crs(CRS_LATLON)
    area_m2 = gdf.to_crs(CRS_PROJECTED).geometry.area

    gdf["source"] = "osm"
    gdf["entity_uid"] = "osm:" + gdf.get("osmid", gdf.index).astype(str)
    gdf["feature_type"] = "building"
    gdf["building_type"] = gdf.get("building", "unknown")
    gdf["area_m2"] = area_m2
    gdf["extraction_confidence"] = None  # OSM has no native per-feature confidence

    keep = ["entity_uid", "source", "feature_type", "building_type",
            "area_m2", "extraction_confidence", "geometry"]
    gdf = gdf[[c for c in keep if c in gdf.columns]]

    print(f"[OSM] Fetched {len(gdf)} buildings")
    return gdf


if __name__ == "__main__":
    result = fetch_osm_buildings()
    print(result.head())
    print(f"Total area: {result['area_m2'].sum():,.0f} m^2")