# LandLens — AI Geospatial Reconciliation Engine

**Smart India Hackathon 2026 · NAKSHA Programme (Dept. of Land Resources, Ministry of Rural Development)**

🔗 **Live demo:** [frontend-eight-gray-93.vercel.app](https://frontend-eight-gray-93.vercel.app/)
📦 **Repository:** [github.com/ShubhAgarwal-03/Geo-Reconciliation](https://github.com/ShubhAgarwal-03/Geo-Reconciliation)

---

## The Problem

India's **NAKSHA Programme** is building a digital twin of urban land records across 157 Urban Local Bodies in 27 states. But the underlying geospatial data — drone imagery, orthorectified images (ORI), DSM/DTM, cadastral maps, revenue records, municipal GIS layers, utility networks, ground-truth surveys, GNSS/CORS data, and building footprints — comes from disconnected departments that don't agree with each other. Today, reconciling these datasets is a manual GIS job.

NAKSHA's own SOP (inherited from the sister scheme SVAMITVA) describes a **manual feature-extraction-plus-ground-validation loop**: extract features from imagery, then have a human validate them against other sources. That loop is the actual bottleneck.

## What This Project Does

LandLens automates that loop. It takes independent building-footprint sources for a real urban area, spatially matches the same real-world building across sources, reconciles conflicting geometries into one canonical entity, and assigns each entity a **confidence score** — routing only the genuinely ambiguous cases to a human review queue instead of asking a person to check everything.

**Demo city:** Bengaluru (a NAKSHA digital twin is already in progress here), covering the **Koramangala–Indiranagar–HSR Layout** corridor — chosen for building density and commercial/residential mix.

This is a deliberately narrow, working proof-of-mechanism rather than an attempt to cover all 10 dataset types and 7 capabilities named in the problem statement. Everything built here is built end-to-end and validated on real data; everything not built is scoped out explicitly rather than faked.

---

## Architecture

Because the demo runs at **district scale** (tens of thousands of buildings, not a single neighborhood), matching and reconciliation are **not** computed live. They run once, offline, as a batch pipeline, and are written to a spatial database. The live demo only queries precomputed results.

```
OFFLINE (run once, before the demo)
────────────────────────────────────
 OpenStreetMap buildings ──┐
                           ├──► Normalize (CRS + schema) ──► raw_features (PostGIS)
 Google Open Buildings v3 ─┘
                                        │
                                        ▼
                      Spatial matching (STRtree candidate search
                      + IoU / centroid-distance / attribute scoring)
                                        │
                                        ▼
                      Conflict resolution (merge matched geometries,
                      carry unmatched entities through)
                                        │
                                        ▼
                      Confidence scoring (match score + inter-source
                      agreement + extraction confidence)
                                        │
                                        ▼
                      canonical_entities (PostGIS, GIST-indexed)


LIVE (during the demo)
────────────────────────────────────
 Leaflet-based map (LandLens UI) ──bbox + zoom──► FastAPI ──► PostGIS query
   zoomed out  → clustered summary view
   zoomed in   → real building polygons, confidence color-coded
   click       → per-entity score breakdown
   review tab  → entities flagged needs_review
```

### Matching score

Two candidate footprints from different sources are scored as:

```
Score(A, B) = w1 · IoU(geometry) + w2 · (1 − normalized_centroid_distance) + w3 · attribute_similarity
```

Candidate pairs are generated with an **STRtree** spatial index rather than all-pairs comparison — necessary once a single tile can contain thousands of buildings per source. Matches are assigned greedily (highest score first, unclaimed pairs only), which is far easier to reason about under hackathon time pressure than a full optimal assignment solve, and is a reasonable approximation given that buildings are close to a one-to-one match between sources within a tile.

### Confidence scoring

Each canonical entity's confidence combines:
- the matching score itself,
- how many independent sources agree on it, and
- the source extraction's own confidence (for AI-extracted features).

Entities below a configurable threshold are routed to a **review queue** instead of being auto-accepted.

---

## Data Sources

| Source | Access | Used for |
|---|---|---|
| OpenStreetMap building footprints | Open (Overpass API via `osmnx`) | Primary footprint source |
| Google Open Buildings v3 | Open, CC-BY-4.0 (Google Earth Engine) | Independent footprint source |
| Sentinel-2 / district imagery | Open (Copernicus, via Earth Engine) | Basis for future AI-extracted footprint layer |

Both primary sources are fully open and — usefully — **genuinely disagree** with each other in places, so the conflict data the reconciliation engine works on is real, not synthetic.

Sources considered but explicitly **not** integrated in this build (registration-gated, lookup-only, or entirely closed to the public): Bhuvan/ISRO imagery, SVAMITVA stats (AIKosh), state cadastral portals, municipal GIS/utility networks, GNSS/CORS survey data, and real NAKSHA raw survey data. These are named as future extensions in the pitch, not simulated here.

---

## Verification

Rather than only showing output, the matching engine is checked against a held-out reference: one source is treated as a pseudo-ground-truth subset, and **precision, recall, F1, and average IoU** are computed against it (`verification/evaluate_matching.py`). This is what lets the project state a real accuracy number instead of an unverified demo.

A representative offline run over a test patch of the district: **5,633** OpenStreetMap buildings and **8,846** deduplicated Google Open Buildings footprints were ingested, producing **12,451** canonical reconciled entities from **14,479** raw input features in under three minutes.

---

## Tech Stack

**Pipeline / matching engine**
- Python, GeoPandas, Shapely, `osmnx` (OSM/Overpass), Google Earth Engine (`earthengine-api`) for Google Open Buildings
- `STRtree` (Shapely) for spatial candidate generation at district scale

**Database**
- PostgreSQL + PostGIS (spatial types, GIST indexing), hosted on Supabase

**Backend**
- FastAPI, serving bounding-box-filtered endpoints:
  - `GET /entities` — full polygons within a bbox
  - `GET /entities/clustered` — summarized/clustered view for zoomed-out queries
  - `GET /entities/{id}` — single entity detail, including its score breakdown
  - `GET /review-queue` — entities flagged for human review
  - `GET /health`

**Frontend — "LandLens"**
- React + Vite, Leaflet for the map
- Zoom-dependent rendering (clustered summary vs. full polygon detail), confidence-based color coding, per-entity detail panel, review-queue panel, and a numeric results table
- Deployed on Vercel: **[frontend-eight-gray-93.vercel.app](https://frontend-eight-gray-93.vercel.app/)**

---

## Repository Structure

```
Geo-Reconciliation/
├── config.py                 # district bbox, SRID, table names, thresholds
├── docker-compose.yml        # local PostGIS (optional — project also runs against Supabase)
├── requirements.txt
├── db/                       # schema definition + Supabase/Postgres connection handling
├── ingestion/                # OSM + Google Open Buildings fetchers
├── matching/                 # normalization, similarity scoring, entity matching
├── reconciliation/           # conflict resolution + confidence scoring
├── pipeline/                 # offline batch driver (run_offline_batch.py)
├── verification/             # precision/recall/F1 evaluation against held-out reference
└── backend/                  # FastAPI app + bbox-aware routers
```

The frontend (LandLens UI) is deployed separately on Vercel; see the live demo link above.

---

## Running It Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Point at a PostGIS-enabled Postgres instance (Supabase or local Docker)
export GEO_RECON_DB_DSN="postgresql://<user>:<password>@<host>:5432/postgres"

# 3. Apply the schema
python -m db.apply_schema

# 4. Authenticate Earth Engine (one-time)
earthengine authenticate

# 5. Set your target area in config.py (DISTRICT_BBOX, EE_PROJECT), then run the pipeline
python -m pipeline.run_offline_batch

# 6. Evaluate matching quality
python -m verification.evaluate_matching

# 7. Serve the API
uvicorn backend.main:app --reload
```

The frontend consumes the FastAPI endpoints above — point its API base URL config at your running backend (or the deployed one) to view results on the map.

---

## Scope & Honesty Notes

- **What's fully built:** OSM + Google Open Buildings ingestion, CRS/schema normalization, spatial matching with a real scoring formula, conflict resolution, confidence scoring, a PostGIS-backed API, and a Leaflet-based review UI — validated end-to-end on a real multi-neighborhood slice of Bengaluru.
- **What's partial:** topology correction (basic self-intersection repair) and attribute mapping (deterministic schema mapping).
- **What's future work, not built:** AI-based footprint extraction from raw imagery (currently two independent open footprint sources are reconciled; a third AI-extracted layer is architecturally supported but not yet trained/integrated), roads as a second feature type, DSM−DTM building-height enrichment, change detection, and integration of the dataset types that have no public access path today (utility networks, GNSS/CORS, municipal GIS, real NAKSHA raw survey data).

This project intentionally reports what actually works, including a known tuning finding from testing: on early runs, a large share of entities were flagged `needs_review` because genuine cross-source disagreement in real footprint data is common — which is itself the actual problem NAKSHA's manual validation loop exists to solve.

---

## Team

Built for Smart India Hackathon 2026, organized around four tracks: data ingestion, AI/matching engine, backend/API, and frontend — each aligned to a shared schema and API contract so the pipeline and the UI could be developed in parallel.
