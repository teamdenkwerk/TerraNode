# TERRANODE Data Pipeline Specification

## 1. End-to-End Pipeline Architecture

```
EXISTING SOURCES                         NEW AI SOURCE
───────────────                         ─────────────

Cadastral ───────────────┐
                         │
Municipal ───────────────┼──────► Stage 03
                         │       Schema Normalization
                         │              │
Drone ORI ──► 02B ──► 02C ┘              │
              │         │                 ▼
         Mask R-CNN   Polygon       Existing Pipeline
         inference    + CRS         unchanged
                           │
                           ▼
                    Stage 03+
                    ─────────────
                    Schema
                    Validation
                    CRS
                    Topology
                    Index
                    Matching
                    IoU
                    Reconciliation
                    Confidence
                    Review
                    Versioning
                    Evidence
                    GIS
                    Reports
```

---

## 2. Ingestion & Preprocessing Streams

### A. Existing Sources
1. **Cadastral Stream**:
   - Ingests revenue cadastral land maps (Khasra, FMB, CTS, Town Survey).
   - Authoritative legal parcel boundaries in native projection (e.g. KSRSAC EPSG:7760, State Grids, or WGS 84).
2. **Municipal Stream**:
   - Ingests municipal property tax GIS polygons and assessment databases.
   - Built-up footprints and physical setback boundaries.

### B. New AI Source Stream
1. **Input: Drone ORI (Orthorectified Imagery)**:
   - High-resolution drone orthomosaics (5cm Ground Sampling Distance - GSD).
   - Tiled with 6-parameter affine georeferencing metadata.
2. **Stage 02B: Mask R-CNN Inference**:
   - Deep learning instance segmentation engine (`backend/ml/stage_02_drone_ai.py`).
   - Backbone: `ResNet-50-FPN` / `ResNet-101-FPN`.
   - Instance detection confidence threshold: $S_{\text{det}} \ge 0.70$.
   - Generates pixel-accurate building footprint masks and bounding boxes.
3. **Stage 02C: Polygon Extraction + CRS Georeferencing**:
   - Contour polygonization tracing building perimeter contours.
   - 6-parameter Affine Geotransform:
     $$X_{\text{geo}} = c + a \cdot x + b \cdot y$$
     $$Y_{\text{geo}} = f + d \cdot x + e \cdot y$$
   - Douglas-Peucker simplification (tolerance $\approx 0.20\text{m}$) eliminating raster staircasing while preserving geometric corners.
   - Target CRS assignment: Metric UTM (`EPSG:32643` / `EPSG:32644`) and WGS 84 display (`EPSG:4326`).
   - Closed-ring topological validation.

---

## 3. Convergence Hub: Stage 03 Schema Normalization

All 3 streams converge into **Stage 03**:
- **Cadastral**
- **Municipal**
- **AI Source (02B Mask R-CNN ➔ 02C Polygon + CRS)**

Normalized to the canonical 10-field schema:
1. `canonical_uid`: Universal entity identifier.
2. `survey_number`: Cadastral / CTS / AI identifier.
3. `source_type`: `"cadastral"` | `"municipal"` | `"ai"`.
4. `source_name`: Descriptive provenance origin.
5. `geometry`: Closed GeoJSON Polygon.
6. `area_m2`: Area in square meters.
7. `confidence_score`: Source / detection reliability metric (0.00 – 1.00).
8. `crs`: Coordinate reference system string.
9. `centroid`: Lat/Lon and projected metric centroid.
10. `provenance_hash`: SHA-256 cryptographic fingerprint.

---

## 4. Downstream Pipeline: Stage 03+ (Existing Pipeline Unchanged)

Following Stage 03 convergence, the downstream pipeline executes without alteration:

| Step | Stage Name | Implementation Module | Description |
|:---|:---|:---|:---|
| **04** | **Schema Validation** | `backend/validation/dataset_validator.py` | 20 topological invariant checks (closure, bounds, validity). |
| **05** | **CRS Transformation** | `backend/crs/transformer.py` | Projection to local metric UTM grid for Euclidean metrology. |
| **06** | **Topology Repair** | `backend/geometry/validator.py` | Non-destructive repair using `shapely.make_valid` (< 5% area shift). |
| **07** | **Spatial Indexing** | `backend/matching/matcher.py` | STRtree R-tree spatial index for $O(N \log N)$ candidate intersection. |
| **08** | **Pairwise Matching** | `backend/matching/matcher.py` | Cross-source candidate pairing & Union-Find identity clustering. |
| **09** | **IoU & Centroid Drift** | `backend/reconciliation/policy.py` | Intersection over Union ($\ge 85\%$) & Euclidean drift ($< 2\text{m}$). |
| **10** | **Reconciliation Consensus** | `backend/reconciliation/resolver.py` | Autonomous multi-source consensus boundary synthesis. |
| **11** | **Confidence Scoring** | `backend/reconciliation/policy.py` | Bayesian multi-source probability score ($0.50 \cdot M + 0.35 \cdot \text{IoU} + 0.15 \cdot \text{AI}$). |
| **12** | **Authority Review Queue** | `backend/routers/review_queue.py` | Human-in-the-loop dispute triage for borderline parcels. |
| **13** | **Immutable Versioning** | `backend/history/service.py` | Cryptographic state machine ($v1.0 \to v1.1$) with SHA-256 ledger. |
| **14** | **Evidence Dossier** | `backend/evidence/service.py` | 6-layer spatial provenance evidence bundle. |
| **15** | **Interactive GIS Explorer** | `frontend/src/components/InteractiveMap.tsx` | Multi-layer cartographic visualization with authentic OSM parcels. |
| **16** | **Reports & Certificates** | `backend/reports/summary_service.py` | Official reconciliation audit certificates & signed PDF export. |
