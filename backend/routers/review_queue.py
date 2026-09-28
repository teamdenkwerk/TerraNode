"""
backend/routers/review_queue.py

GET /review-queue — entities with needs_review = true. bbox is optional
here (unlike /entities) since the review panel is likely a separate list
view, not necessarily tied to the current map viewport — pass bbox params
only if the frontend wants to scope it to what's currently on screen.
"""

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from fastapi import APIRouter, Query

from backend.db import get_connection
from backend.schema import EntitySummary
from config import MATCH_SRID

router = APIRouter(prefix="/review-queue", tags=["review-queue"])

DEFAULT_LIMIT = 500
MAX_LIMIT = 5000


@router.get("", response_model=list[EntitySummary])
def get_review_queue(
    dataset_id: str | None = Query(None, description="Optional dataset ID filter"),
    min_lon: float | None = Query(None, description="Optional bbox filter — min longitude, EPSG:4326"),
    min_lat: float | None = Query(None, description="Optional bbox filter — min latitude, EPSG:4326"),
    max_lon: float | None = Query(None, description="Optional bbox filter — max longitude, EPSG:4326"),
    max_lat: float | None = Query(None, description="Optional bbox filter — max latitude, EPSG:4326"),
    limit: int = Query(DEFAULT_LIMIT, le=MAX_LIMIT, ge=1),
):
    from backend.dataset_manager import get_entities_for_dataset, get_active_dataset_id
    target_dataset_id = dataset_id or get_active_dataset_id()

    # If non-bengaluru dataset active, pull from isolated dataset entities
    if target_dataset_id != "bengaluru-ward112":
        raw = get_entities_for_dataset(target_dataset_id, min_lon, min_lat, max_lon, max_lat, limit)
        review_entities = [e for e in raw if e.get("needs_review") or e.get("properties", {}).get("status") in ("review", "conflict")]
        return [
            EntitySummary(
                canonical_uid=e["canonical_uid"],
                geometry=e["geometry"],
                area_m2=e["area_m2"],
                source_count=e["source_count"],
                sources=e["sources"],
                confidence_score=e["confidence_score"],
                needs_review=True,
            )
            for e in review_entities
        ]

    bbox_given = all(v is not None for v in (min_lon, min_lat, max_lon, max_lat))

    query = f"""
        SELECT canonical_uid,
               ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geojson,
               area_m2, source_count, sources, confidence_score, needs_review
        FROM canonical_entities
        WHERE needs_review = true
    """
    params: dict = {"limit": limit}

    if bbox_given:
        query += f"""
            AND ST_Intersects(
                geom,
                ST_Transform(ST_MakeEnvelope(%(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326), {MATCH_SRID})
            )
        """
        params.update({"min_lon": min_lon, "min_lat": min_lat, "max_lon": max_lon, "max_lat": max_lat})

    query += " ORDER BY confidence_score ASC LIMIT %(limit)s"  # lowest-confidence first — most in need of a look

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        if rows:
            return [
                EntitySummary(
                    canonical_uid=r["canonical_uid"],
                    geometry=json.loads(r["geojson"]),
                    area_m2=r["area_m2"],
                    source_count=r["source_count"],
                    sources=r["sources"],
                    confidence_score=r["confidence_score"],
                    needs_review=r["needs_review"],
                )
                for r in rows
            ]
    except Exception:
        pass

    # Fallback to catalog review entities
    raw = get_entities_for_dataset(target_dataset_id, min_lon, min_lat, max_lon, max_lat, limit)
    review_entities = [e for e in raw if e.get("needs_review") or e.get("properties", {}).get("status") in ("review", "conflict")]
    return [
        EntitySummary(
            canonical_uid=e["canonical_uid"],
            geometry=e["geometry"],
            area_m2=e["area_m2"],
            source_count=e["source_count"],
            sources=e["sources"],
            confidence_score=e["confidence_score"],
            needs_review=True,
        )
        for e in review_entities
    ]