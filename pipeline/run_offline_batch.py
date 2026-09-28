"""
pipeline/run_offline_batch.py

THE OFFLINE BATCH JOB — runs once, before the demo, not live:
  ingest OSM + Google Open Buildings (+ optional uploaded file) -> normalize
  -> insert raw_features -> match (N-source clustering) -> reconcile
  -> confidence score -> insert canonical_entities

AI-extracted features are OPTIONAL. The pipeline runs correctly with just
OSM + Google Open Buildings (fallback-first principle) — to add a third
source later, normalize + insert_raw_features it the same way, before
matching runs; the matching engine already generalizes to N sources.

Usage:
    python -m pipeline.run_offline_batch
    python -m pipeline.run_offline_batch --uploaded-file data/uploads/some.geojson
    python -m pipeline.run_offline_batch --run-id 12   # used when the API triggers this
"""

import sys
import time
import argparse
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import DISTRICT_BBOX
from db.connection import get_connection
from ingestion.fetch_osm_buildings import fetch_osm_buildings
from ingestion.fetch_google_open_buildings import fetch_google_open_buildings
from ingestion.fetch_uploaded_file import fetch_uploaded_buildings
from matching.normalize import normalize_layer, insert_raw_features
from matching.match_entities import run_matching
from reconciliation.resolve_conflicts import reconcile_clusters
from reconciliation.confidence_score import score_entities, write_scored_entities


def _log_run_start(bbox=None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pipeline_runs (bbox) VALUES (%s) RETURNING id",
                (bbox or list(DISTRICT_BBOX),),
            )
            run_id = cur.fetchone()["id"]
        conn.commit()
    return run_id


def _log_run_complete(run_id: int, raw_count: int, canonical_count: int, review_count: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs
                SET run_completed_at = now(), raw_feature_count = %s,
                    canonical_entity_count = %s, review_queue_count = %s
                WHERE id = %s
                """,
                (raw_count, canonical_count, review_count, run_id),
            )
        conn.commit()


def run_pipeline(tile_id: str | None = None, uploaded_file_path: str | None = None,
                  run_id: int | None = None) -> None:
    start = time.time()
    if run_id is None:
        run_id = _log_run_start()          # standalone run — log it ourselves
    print(f"=== Pipeline run {run_id} started ===")

    # Step 1: Ingestion
    osm_gdf = fetch_osm_buildings()
    gob_gdf = fetch_google_open_buildings()

    # Step 2: Normalize + insert raw_features
    insert_raw_features(normalize_layer(osm_gdf, "osm"), tile_id=tile_id)
    insert_raw_features(normalize_layer(gob_gdf, "google_open_buildings"), tile_id=tile_id)

    if uploaded_file_path:
        upload_gdf = fetch_uploaded_buildings(uploaded_file_path)
        insert_raw_features(normalize_layer(upload_gdf, "user_upload"), tile_id=tile_id)

    # Plug an AI-extracted layer here later:
    #   ai_gdf = fetch_ai_extracted_buildings()
    #   insert_raw_features(normalize_layer(ai_gdf, "ai_extracted"), tile_id=tile_id)

    # Step 3: Matching (N-source clustering, spatial-index candidate generation)
    features, clusters = run_matching(tile_id=tile_id)
    features_by_id = {f["id"]: f for f in features}

    # Step 4: Reconciliation + confidence scoring
    reconciled = reconcile_clusters(clusters, features_by_id)
    scored = score_entities(reconciled)
    write_scored_entities(scored, tile_id=tile_id)

    review_count = sum(1 for s in scored if s.needs_review)
    _log_run_complete(run_id, len(features), len(scored), review_count)

    elapsed = time.time() - start
    print(f"\n=== Pipeline run {run_id} complete in {elapsed:.1f}s ===")
    print(f"Raw features: {len(features)} | Canonical entities: {len(scored)} | Needs review: {review_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uploaded-file", default=None,
                        help="Path to an uploaded GeoJSON/zip to include as a third source")
    parser.add_argument("--run-id", type=int, default=None,
                        help="Reuse an existing pipeline_runs row instead of creating a new one "
                             "(used when the API triggers this, so it isn't logged twice)")
    args = parser.parse_args()
    run_pipeline(uploaded_file_path=args.uploaded_file, run_id=args.run_id)