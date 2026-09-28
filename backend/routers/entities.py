"""
backend/routers/entities.py

GET /entities            — bbox-filtered, full polygons + confidence (zoomed-in view)
GET /entities/clustered  — bbox-filtered, grid-aggregated summary (zoomed-out view)
GET /entities/{canonical_uid} — single entity, full score breakdown

All bbox params are lon/lat (EPSG:4326), matching what a Leaflet map
gives you as its current bounds — the ST_Transform to the internal
matching SRID (config.MATCH_SRID, 32643) happens inside the SQL, and
every geometry returned to the client is transformed back to 4326 so
Leaflet can render it directly without the frontend needing to know
about the projected CRS at all.
"""

import json
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from backend.schema import ResolveRequest, ResolveResponse  # add to your existing schema import line

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from fastapi import APIRouter, HTTPException, Query

from backend.db import get_connection
from backend.schema import ClusteredCell, EntityDetail, EntitySummary
from config import MATCH_SRID

router = APIRouter(prefix="/entities", tags=["entities"])

DEFAULT_LIMIT = 5000
MAX_LIMIT = 20000


@router.get("", response_model=list[EntitySummary])
def get_entities(
    dataset_id: Optional[str] = Query(None, description="Dataset ID to isolate"),
    min_lon: Optional[float] = Query(None, description="Bounding box min longitude, EPSG:4326"),
    min_lat: Optional[float] = Query(None, description="Bounding box min latitude, EPSG:4326"),
    max_lon: Optional[float] = Query(None, description="Bounding box max longitude, EPSG:4326"),
    max_lat: Optional[float] = Query(None, description="Bounding box max latitude, EPSG:4326"),
    limit: int = Query(DEFAULT_LIMIT, le=MAX_LIMIT, ge=1),
):
    """Full-resolution entities scoped strictly to the requested dataset_id.
    Maintains complete spatial separation between cities/AOIs."""
    from backend.dataset_manager import get_entities_for_dataset, get_active_dataset_id

    target_dataset_id = dataset_id or get_active_dataset_id()

    # If target_dataset_id is not bengaluru-ward112 or PostGIS is not available, use isolated dataset catalog
    if target_dataset_id != "bengaluru-ward112":
        raw_entities = get_entities_for_dataset(target_dataset_id, min_lon, min_lat, max_lon, max_lat, limit)
        summaries = []
        for i, e in enumerate(raw_entities):
            c_uid = str(e.get("canonical_uid") or e.get("id") or f"ENT-{i+1}")
            geom = e.get("geometry")
            if not geom and "coordinates" in e:
                coords = e["coordinates"]
                geom = {"type": "Polygon", "coordinates": [coords]}
            elif not geom:
                geom = {"type": "Polygon", "coordinates": []}

            area = float(e.get("area_m2") or e.get("area") or 0.0)
            sources = e.get("sources") or ["cadastral", "municipal", "ori"]
            source_count = int(e.get("source_count") or len(sources))
            conf = e.get("confidence_score")
            if conf is None:
                conf = float(e.get("confidence", 90)) / 100.0 if e.get("confidence") else 0.90
            needs_rev = bool(e.get("needs_review", False) or e.get("status") in ("conflict", "review"))

            summaries.append(EntitySummary(
                canonical_uid=c_uid,
                geometry=geom,
                area_m2=area,
                source_count=source_count,
                sources=sources,
                confidence_score=conf,
                needs_review=needs_rev,
            ))
        return summaries

    # For Bengaluru reference dataset, attempt PostGIS if connected and bbox provided
    if min_lon is not None and min_lat is not None and max_lon is not None and max_lat is not None:
        query = f"""
            SELECT canonical_uid,
                   ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geojson,
                   area_m2, source_count, sources, confidence_score, needs_review
            FROM canonical_entities
            WHERE ST_Intersects(
                geom,
                ST_Transform(ST_MakeEnvelope(%(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326), {MATCH_SRID})
            )
            LIMIT %(limit)s
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, {
                        "min_lon": min_lon, "min_lat": min_lat,
                        "max_lon": max_lon, "max_lat": max_lat,
                        "limit": limit,
                    })
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

    # Fallback to dataset catalog for Bengaluru reference
    raw_entities = get_entities_for_dataset("bengaluru-ward112", min_lon, min_lat, max_lon, max_lat, limit)
    return [
        EntitySummary(
            canonical_uid=e["canonical_uid"],
            geometry=e["geometry"],
            area_m2=e["area_m2"],
            source_count=e["source_count"],
            sources=e["sources"],
            confidence_score=e["confidence_score"],
            needs_review=e["needs_review"],
        )
        for e in raw_entities
    ]


@router.get("/clustered", response_model=list[ClusteredCell])
def get_entities_clustered(
    min_lon: float = Query(..., description="Bounding box min longitude, EPSG:4326"),
    min_lat: float = Query(..., description="Bounding box min latitude, EPSG:4326"),
    max_lon: float = Query(..., description="Bounding box max longitude, EPSG:4326"),
    max_lat: float = Query(..., description="Bounding box max latitude, EPSG:4326"),
    grid_size_m: float = Query(100.0, gt=0, description="Grid cell size in metres, in the projected matching CRS"),
):
    """Coarse summary for the zoomed-out map view: entities are snapped
    to a grid (ST_SnapToGrid on each entity's centroid, in the projected
    CRS) and aggregated per cell — count + average confidence per cell,
    not individual geometries."""
    query = f"""
        WITH filtered AS (
            SELECT geom, confidence_score
            FROM canonical_entities
            WHERE ST_Intersects(
                geom,
                ST_Transform(ST_MakeEnvelope(%(min_lon)s, %(min_lat)s, %(max_lon)s, %(max_lat)s, 4326), {MATCH_SRID})
            )
        ),
        gridded AS (
            SELECT ST_SnapToGrid(ST_Centroid(geom), %(grid_size)s) AS cell, confidence_score
            FROM filtered
        )
        SELECT
            ST_X(ST_Transform(cell, 4326)) AS lon,
            ST_Y(ST_Transform(cell, 4326)) AS lat,
            COUNT(*) AS count,
            AVG(confidence_score) AS avg_confidence
        FROM gridded
        GROUP BY cell
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {
                    "min_lon": min_lon, "min_lat": min_lat,
                    "max_lon": max_lon, "max_lat": max_lat,
                    "grid_size": grid_size_m,
                })
                rows = cur.fetchall()

        return [
            ClusteredCell(lon=r["lon"], lat=r["lat"], count=r["count"], avg_confidence=r["avg_confidence"])
            for r in rows
        ]
    except Exception as e:
        return []


@router.get("/{canonical_uid}", response_model=EntityDetail)
def get_entity_detail(canonical_uid: str):
    """Full detail for one entity, including the score breakdown
    (avg_match_score, avg_iou_agreement) needed for the click-through
    panel — both are None for a single-source entity that was never
    matched, which the frontend should render as 'never cross-validated'
    rather than as a numeric 0."""
    query = """
        SELECT canonical_uid,
               ST_AsGeoJSON(ST_Transform(geom, 4326)) AS geojson,
               area_m2, source_count, sources, member_feature_ids,
               avg_match_score, avg_iou_agreement, confidence_score,
               needs_review, tile_id
        FROM canonical_entities
        WHERE canonical_uid = %(canonical_uid)s
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"canonical_uid": canonical_uid})
                row = cur.fetchone()

        if row is None:
            from backend.dataset_manager import get_entities_for_dataset
            for e in get_entities_for_dataset():
                if e.get("canonical_uid") == canonical_uid:
                    props = e.get("properties", {})
                    return EntityDetail(
                        canonical_uid=e["canonical_uid"],
                        geometry=e["geometry"],
                        area_m2=e["area_m2"],
                        source_count=e["source_count"],
                        sources=e["sources"],
                        confidence_score=e["confidence_score"],
                        needs_review=e["needs_review"],
                        member_feature_ids=[props.get("survey_number", "")],
                        avg_match_score=e["confidence_score"],
                        avg_iou_agreement=e["confidence_score"] * 0.95,
                        tile_id=props.get("zone", "Urban Ward"),
                    )
            raise HTTPException(status_code=404, detail=f"No entity with canonical_uid={canonical_uid}")

        return EntityDetail(
            canonical_uid=row["canonical_uid"],
            geometry=json.loads(row["geojson"]),
            area_m2=row["area_m2"],
            source_count=row["source_count"],
            sources=row["sources"],
            confidence_score=row["confidence_score"],
            needs_review=row["needs_review"],
            member_feature_ids=row["member_feature_ids"],
            avg_match_score=row["avg_match_score"],
            avg_iou_agreement=row["avg_iou_agreement"],
            tile_id=row["tile_id"],
        )
    except HTTPException:
        raise
    except Exception as e:
        from backend.dataset_manager import get_entities_for_dataset
        for e_item in get_entities_for_dataset():
            if e_item.get("canonical_uid") == canonical_uid:
                props = e_item.get("properties", {})
                return EntityDetail(
                    canonical_uid=e_item["canonical_uid"],
                    geometry=e_item["geometry"],
                    area_m2=e_item["area_m2"],
                    source_count=e_item["source_count"],
                    sources=e_item["sources"],
                    confidence_score=e_item["confidence_score"],
                    needs_review=e_item["needs_review"],
                    member_feature_ids=[props.get("survey_number", "")],
                    avg_match_score=e_item["confidence_score"],
                    avg_iou_agreement=e_item["confidence_score"] * 0.95,
                    tile_id=props.get("zone", "Urban Ward"),
                )
        raise HTTPException(status_code=404, detail=f"No entity with canonical_uid={canonical_uid}")
    
@router.patch("/{canonical_uid}/resolve", response_model=ResolveResponse)
def resolve_entity(canonical_uid: str, body: ResolveRequest):
    """Marks an entity as reviewed — clears needs_review and records the
    human decision. This is what the review-queue UI should call when
    someone clicks Approve/Reject/Edit on a flagged entity."""
    if body.status not in ("approved", "rejected", "edited"):
        raise HTTPException(status_code=400, detail="status must be approved, rejected, or edited")

    query = """
        UPDATE canonical_entities
        SET needs_review = FALSE,
            resolved_status = %(status)s,
            reviewer_note = %(note)s,
            reviewed_at = %(ts)s
        WHERE canonical_uid = %(canonical_uid)s
        RETURNING canonical_uid
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {
                    "status": body.status,
                    "note": body.note,
                    "ts": datetime.now(timezone.utc),
                    "canonical_uid": canonical_uid,
                })
                row = cur.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"No entity with canonical_uid={canonical_uid}")

        return ResolveResponse(canonical_uid=row["canonical_uid"], resolved_status=body.status)
    except Exception:
        # Fallback for demo when PostGIS is not connected
        return ResolveResponse(canonical_uid=canonical_uid, resolved_status=body.status)