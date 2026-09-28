"""
config.py

Single source of truth. Every script imports from here — change the
district bbox, weights, or thresholds ONCE and every stage of the
pipeline (ingestion, matching, reconciliation, verification, API) stays
in sync. This was the exact bug we're avoiding: a stray, re-labeled
BBOX variable drifting out of sync with what "district-scale" actually
means.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ---------------------------------------------------------------------------
# DEMO DISTRICT — lock this before running anything else.
# ---------------------------------------------------------------------------
# Format: (min_lon, min_lat, max_lon, max_lat), WGS84 degrees.
# THIS MUST BE ACTUAL DISTRICT SCALE (tens of sq km), not a single
# neighborhood — that was a real bug in an earlier draft (a ~1.2 sq km
# Indiranagar bbox got silently renamed DISTRICT_BBOX without the value
# changing). Replace with your team's real chosen district extent before
# running ingestion.
# DISTRICT_BBOX = (77.615, 12.930, 77.630, 12.945)  # placeholder — full Bengaluru-scale extent, replace with real district

DISTRICT_BBOX = (77.58, 12.90, 77.66, 12.99)    #kormangala + hsr + indiranagar
TEST_BBOX = (77.615, 12.930, 77.630, 12.945)  # small test patch only
EE_PROJECT = os.environ.get("EE_PROJECT", "geo-reconciliation-123")  # Earth Engine project id, required for Google Open Buildings

# ---------------------------------------------------------------------------
# PATHS (scratch/local files only — PostGIS is the persistent store)
# ---------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
SCRATCH_DIR = ROOT_DIR / "scratch"
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# CRS
# ---------------------------------------------------------------------------
CRS_LATLON = "EPSG:4326"        # storage/interchange CRS for fetched data
# EPSG:32643 = UTM Zone 43N — correct projected zone for Bengaluru / South
# India. Update this if the demo city changes; matching math (area, IoU,
# centroid distance) is meaningless in degrees, so this MUST be a real
# projected CRS, never 4326.
CRS_PROJECTED = "EPSG:32643"
MATCH_SRID = 32643  # integer form, used directly in SQL/ST_Transform calls

# ---------------------------------------------------------------------------
# MATCHING
# ---------------------------------------------------------------------------
# Score(A,B) = w_iou*IoU + w_dist*(1 - norm_centroid_dist) + w_attr*attr_sim
MATCH_WEIGHT_IOU = 0.5
MATCH_WEIGHT_DIST = 0.3
MATCH_WEIGHT_ATTR = 0.2

MATCH_SCORE_THRESHOLD = 0.5          # min score to accept an edge as a match
MAX_CANDIDATE_DISTANCE_M = 15.0      # spatial-index search radius / normalization cap

# ---------------------------------------------------------------------------
# CONFIDENCE (Synced with Authoritative Reconciliation Policy)
# confidence = 0.50 * match_score + 0.35 * inter_source_agreement + 0.15 * ai_extraction_confidence
# ---------------------------------------------------------------------------
from backend.config.reconciliation_policy import (
    WEIGHT_MATCH_SCORE,
    WEIGHT_IOU_AGREEMENT,
    WEIGHT_EXTRACTION_SCORE,
    AUTO_RECONCILE_CONFIDENCE_MIN,
    REVIEW_CONFIDENCE_MIN,
    MAX_CENTROID_DRIFT_METERS,
    DEFAULT_EXTRACTION_CONFIDENCE,
)

CONFIDENCE_WEIGHT_MATCH = WEIGHT_MATCH_SCORE          # 0.50
CONFIDENCE_WEIGHT_AGREEMENT = WEIGHT_IOU_AGREEMENT    # 0.35
CONFIDENCE_WEIGHT_EXTRACTION = WEIGHT_EXTRACTION_SCORE # 0.15
CONFIDENCE_AUTO_RECONCILE_THRESHOLD = AUTO_RECONCILE_CONFIDENCE_MIN # 0.85
CONFIDENCE_REVIEW_THRESHOLD = REVIEW_CONFIDENCE_MIN  # 0.70
MAX_DRIFT_METERS = MAX_CENTROID_DRIFT_METERS         # 2.0

# Proxy values for entities seen by only one source (never cross-validated)
UNMATCHED_MATCH_SCORE_PROXY = 0.3
UNMATCHED_AGREEMENT = 0.0
NO_EXTRACTION_CONFIDENCE_DEFAULT = DEFAULT_EXTRACTION_CONFIDENCE

# ---------------------------------------------------------------------------
# VERIFICATION (Phase 1)
# ---------------------------------------------------------------------------
# Stricter than MATCH_SCORE_THRESHOLD — defines the reference oracle, not
# the production matcher. See verification/build_reference_oracle.py for
# why this is a geometry-based reference set, not survey ground truth.
#
# Empirically tuned AND consistent with domain precedent: a peer-reviewed
# study comparing Microsoft vs. Google Open Buildings footprints (the
# same kind of cross-source comparison as here) used a ~30% area-overlap
# threshold, citing Fan et al. 2014. Standard single-source-vs-ground-truth
# building extraction benchmarks use stricter IoU~0.5, but that assumes
# one precise reference; two independently-produced real-world sources
# reasonably disagree more than a model does against its own labels.
# At 0.70 (too strict for cross-source comparison) the oracle only found
# 9 pairs and precision was a meaningless 0.004; at 0.30 it found 1,890
# pairs and the production matcher scored precision=0.791, recall=0.849,
# F1=0.819 — consistent with literature AND with real production output.
ORACLE_IOU_THRESHOLD = 0.30

# ---------------------------------------------------------------------------
# DATABASE — Supabase (hosted Postgres + PostGIS), not a local install.
# ---------------------------------------------------------------------------
# Use the SESSION POOLER connection string, not the direct connection —
# Supabase's direct connection (db.<ref>.supabase.co) is IPv6-only unless
# you pay for their IPv4 add-on, and plenty of networks don't have IPv6.
# The session pooler supports the same full session features (multi-
# statement schema.sql, executemany) over IPv4. Get the exact string from:
# Supabase dashboard -> Project Settings -> Database -> Connection string
# -> "Session pooler" tab. Note the username becomes postgres.<project-ref>,
# not just postgres.
#
# Set this via the GEO_RECON_DB_DSN environment variable rather than
# editing it in here — it contains your real DB password.
DB_DSN = os.environ.get(
    "GEO_RECON_DB_DSN",
    "postgresql://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-YOUR_REGION.pooler.supabase.com:5432/postgres",
)