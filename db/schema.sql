-- db/schema.sql
-- Run once against a fresh PostGIS-enabled database:
--   psql "$GEO_RECON_DB_DSN" -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------
-- raw_features: one row per polygon, per source, before any reconciliation.
-- geom is stored in the projected matching SRID (config.MATCH_SRID) so
-- every downstream IoU/distance calculation can run directly in SQL or
-- via geopandas without re-projecting on every query.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_features (
    id               SERIAL PRIMARY KEY,
    entity_uid       TEXT UNIQUE NOT NULL,      -- e.g. "osm:12345", "gob:998"
    source           TEXT NOT NULL,             -- "osm" | "google_open_buildings" | "ai_extracted" | ...
    feature_type     TEXT NOT NULL DEFAULT 'building',
    building_type    TEXT,
    area_m2          DOUBLE PRECISION,
    extraction_confidence DOUBLE PRECISION,     -- native/AI confidence, NULL if source has none
    centroid_x       DOUBLE PRECISION NOT NULL,
    centroid_y       DOUBLE PRECISION NOT NULL,
    geom             GEOMETRY(Geometry, 32643) NOT NULL,
    tile_id          TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_features_geom ON raw_features USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_raw_features_source ON raw_features (source);
CREATE INDEX IF NOT EXISTS idx_raw_features_tile ON raw_features (tile_id);

-- ---------------------------------------------------------------------
-- match_edges: every accepted pairwise match (score >= MATCH_SCORE_THRESHOLD)
-- between two raw_features from DIFFERENT sources. Kept as its own table
-- (not just folded into canonical_entities) so verification/evaluate_matching.py
-- can audit individual edges, and so a cluster's average match quality /
-- IoU-based agreement can be recomputed without re-running the matcher.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_edges (
    id                SERIAL PRIMARY KEY,
    feature_id_a      INTEGER NOT NULL REFERENCES raw_features(id),
    feature_id_b      INTEGER NOT NULL REFERENCES raw_features(id),
    score_total        DOUBLE PRECISION NOT NULL,
    score_iou          DOUBLE PRECISION NOT NULL,
    score_centroid      DOUBLE PRECISION NOT NULL,
    score_attribute      DOUBLE PRECISION NOT NULL,
    tile_id           TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (feature_id_a, feature_id_b)
);

-- ---------------------------------------------------------------------
-- canonical_entities: the reconciled output the API serves. One row per
-- real-world building (whether seen by 1, 2, or N sources).
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canonical_entities (
    id                    SERIAL PRIMARY KEY,
    canonical_uid         TEXT UNIQUE NOT NULL,
    geom                  GEOMETRY(Geometry, 32643) NOT NULL,
    area_m2               DOUBLE PRECISION,
    source_count           INTEGER NOT NULL,
    sources               TEXT[] NOT NULL,
    member_feature_ids     INTEGER[] NOT NULL,       -- raw_features.id list in this cluster
    avg_match_score        DOUBLE PRECISION,          -- NULL for single-source (unmatched) entities
    avg_iou_agreement      DOUBLE PRECISION,          -- NULL for single-source entities
    confidence_score       DOUBLE PRECISION NOT NULL,
    needs_review           BOOLEAN NOT NULL,
    tile_id               TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_canonical_entities_geom ON canonical_entities USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_canonical_entities_review ON canonical_entities (needs_review);

-- ---------------------------------------------------------------------
-- pipeline_runs: one row per offline batch run, for auditability/demo stats.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                     SERIAL PRIMARY KEY,
    bbox                   DOUBLE PRECISION[] NOT NULL,
    run_started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_completed_at        TIMESTAMPTZ,
    raw_feature_count       INTEGER,
    canonical_entity_count  INTEGER,
    review_queue_count      INTEGER
);

ALTER TABLE canonical_entities
  ADD COLUMN IF NOT EXISTS resolved_status TEXT,   -- 'approved' | 'rejected' | 'edited'
  ADD COLUMN IF NOT EXISTS reviewer_note   TEXT,
  ADD COLUMN IF NOT EXISTS reviewed_at     TIMESTAMPTZ;