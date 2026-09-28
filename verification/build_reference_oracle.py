"""
verification/build_reference_oracle.py

Phase 1 — builds a reference ("oracle") set of true matches between two
independent sources, using a STRICT geometric overlap threshold
(config.ORACLE_IOU_THRESHOLD) — independent of the production matcher's
weighted score.

Important honesty note for the pitch: this is NOT survey-verified ground
truth. It's a stricter, purely geometric definition of "same building,"
used to sanity-check whether the production matcher (which also uses
centroid distance + attributes, not just IoU) agrees with the obvious
cases. Describe it in the demo as "a geometry-based reference set," not
"ground truth."

Usage:
    python -m verification.build_reference_oracle
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from shapely import wkt as shapely_wkt
from shapely.strtree import STRtree

from config import ORACLE_IOU_THRESHOLD
from db.connection import get_connection
from matching.similarity import iou


def load_features_by_source(source: str) -> list[dict]:
    """Loads raw_features for one source, geometry already in the
    projected matching CRS (no reprojection needed — see matching/normalize.py)."""
    query = """
        SELECT id, entity_uid, source, area_m2, ST_AsText(geom) AS geom_wkt
        FROM raw_features
        WHERE source = %s
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (source,))
            rows = cur.fetchall()
    for r in rows:
        r["geometry"] = shapely_wkt.loads(r.pop("geom_wkt"))
    return rows


def build_oracle_matches(
    source_a: str = "osm",
    source_b: str = "google_open_buildings",
    iou_threshold: float = ORACLE_IOU_THRESHOLD,
) -> set[tuple[int, int]]:
    """Returns a set of (id_a, id_b) pairs passing the strict IoU oracle
    threshold. STRtree-backed candidate generation (bbox/envelope filter
    via the spatial index) before the expensive IoU calc — same pattern
    as matching/match_entities.py, needed at district scale where a plain
    nested loop over both feature lists is an O(n*m) non-starter."""
    features_a = load_features_by_source(source_a)
    features_b = load_features_by_source(source_b)
    print(f"Building oracle from {len(features_a)} {source_a} vs {len(features_b)} {source_b} features...")

    if not features_a or not features_b:
        print("One or both sources empty — returning empty oracle.")
        return set()

    geoms_b = [f["geometry"] for f in features_b]
    tree = STRtree(geoms_b)

    oracle_pairs: set[tuple[int, int]] = set()
    for fa in features_a:
        if fa["geometry"] is None or fa["geometry"].is_empty:
            continue
        # Envelope-intersection candidate lookup — cheap prefilter,
        # same role the bbox check played in the old nested-loop version.
        candidate_positions = tree.query(fa["geometry"])
        for j in candidate_positions:
            fb = features_b[j]
            if fb["geometry"] is None or fb["geometry"].is_empty:
                continue
            if iou(fa["geometry"], fb["geometry"]) >= iou_threshold:
                oracle_pairs.add((fa["id"], fb["id"]))

    print(f"Oracle contains {len(oracle_pairs)} high-confidence true-match pairs (IoU >= {iou_threshold})")
    return oracle_pairs


if __name__ == "__main__":
    pairs = build_oracle_matches()
    print(f"Sample oracle pairs: {list(pairs)[:5]}")