# TERRANODE FEATURE 04 — PARCEL VERSION HISTORY SPECIFICATION

## 1. Executive Summary & Problem Formulation

In municipal cadastre, revenue mapping, and land administration, geospatial decisions have lasting legal and financial consequences:
- **Resurveys & Drone Rectifications** refine boundaries but must never erase the original registered title boundaries.
- **Surveyor-Approved Corrections** resolve disputes, adjust offsets, and record formal field inspections.
- **Judicial & Audit Scrutiny** requires an unbroken, tamper-evident timeline of every spatial boundary version, explaining *what changed*, *why it changed*, and *who approved it*.

**TERRANODE Parcel Version History** (`backend/identity/version_history.py`) implements an immutable, append-only versioning system for parcel geometries and reconciliation states. Every meaningful spatial change generates a new sequential version, protected by strict database constraints against duplicate versions or overwrites.

---

## 2. Core Architectural Principles

```
  ┌────────────────────────────────────────────────────────┐
  │                   Version 1 (Initial)                  │
  │  Source: Historical Cadastral Survey Dataset           │
  │  Decision: INITIAL_INGESTION                           │
  │  Reviewer: System Automated Ingest                     │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼  (Version comparison: Area Δ, IoU, Centroid shift)
  ┌────────────────────────────────────────────────────────┐
  │                   Version 2 (Updated)                  │
  │  Source: Drone Orthophoto Photogrammetry Ingestion     │
  │  Decision: AUTO_RECONCILED                             │
  │  IoU: 88.5% | Centroid Drift: 0.94m | Confidence: 89%  │
  │  Reviewer: Automated Reconciliation Engine             │
  └───────────────────────────┬────────────────────────────┘
                              │
                              ▼  (Version comparison: Area Δ, IoU, Centroid shift)
  ┌────────────────────────────────────────────────────────┐
  │                   Version 3 (Current)                  │
  │  Source: Field DGPS Survey Verification                │
  │  Decision: OFFICER_APPROVED                            │
  │  IoU: 95.8% | Centroid Drift: 0.22m | Confidence: 97%  │
  │  Reviewer: Senior Surveyor General (#402)              │
  │  Change Reason: Field inspection confirmed boundary    │
  └────────────────────────────────────────────────────────┘
```

### Strict Invariants & Safety Constraints
1. **Never Overwrite or Delete Historical Records**: Historical versions are permanent and immutable.
2. **Compound Unique Key Constraint**: `(parcel_uuid, version_number)` must be strictly unique. Attempting to insert an existing version triggers `DuplicateVersionError` and an HTTP `409 Conflict`.
3. **Monotonic Version Sequencing**: New versions must strictly exceed the highest existing version number (`v_new > v_current`).
4. **Projected Metric Geometry Comparison**: All spatial comparisons (area change in $\text{m}^2$, boundary $\text{IoU}$, centroid shift distance in meters, and bearing angle) are computed in localized metric UTM projections, never degree-space approximations.

---

## 3. Data Schema & Model Specification

### ParcelVersionRecord (`backend/identity/version_history.py`)
Each version entry in the append-only ledger records:
```json
{
  "parcel_uuid": "2dec5c4d-cc5b-525f-b9f4-d90d447a455e",
  "version_number": 3,
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[77.6401, 12.9781], [77.6405, 12.9781], [77.6405, 12.9785], [77.6401, 12.9785], [77.6401, 12.9781]]]
  },
  "source_datasets": ["cadastre_2024.geojson", "drone_survey_oct2025.geojson", "field_dgps_2026.geojson"],
  "confidence": 0.97,
  "IoU": 0.958,
  "centroid_drift": 0.22,
  "decision": "OFFICER_APPROVED",
  "review_status": "APPROVED",
  "reviewer": "Officer K. Sharma (Senior Land Records Surveyor #402)",
  "created_at": "2026-09-27T05:35:10Z",
  "change_reason": "Field inspection and DGPS survey confirmed northeast boundary peg alignment.",
  "area_m2": 2435.8,
  "perimeter_m": 198.4,
  "centroid": [12.9783, 77.6403]
}
```

### Geometry Comparison Schema
When comparing two versions (e.g. Previous $V_{i-1}$ vs Current $V_i$):
- **Area Change**:
  - `previous_area_m2`: Area of previous geometry ($\text{m}^2$)
  - `current_area_m2`: Area of current geometry ($\text{m}^2$)
  - `delta_area_m2`: Absolute change ($A_i - A_{i-1}$)
  - `percentage_change`: Relative percent change ($\frac{A_i - A_{i-1}}{A_{i-1}} \times 100\%$)
- **Boundary Change**:
  - `iou`: Intersection-over-Union agreement ($\frac{A_{i-1} \cap A_i}{A_{i-1} \cup A_i}$)
  - `symmetric_difference_m2`: Non-overlapping discrepancy area ($\text{m}^2$)
  - `previous_perimeter_m` & `current_perimeter_m`
- **Centroid Shift**:
  - `shift_distance_meters`: Euclidean distance between centroids in meters ($L_2$ norm in UTM)
  - `bearing_degrees`: Compass bearing from previous centroid to current centroid ($0^\circ$ North to $360^\circ$)

---

## 4. REST API Specification

### `GET /api/parcels/{uuid}/history`
Retrieves the full timeline of versions for the given parcel UUID (or mapped source ID).
- **Response** (`200 OK`):
  ```json
  {
    "parcel_uuid": "2dec5c4d-cc5b-525f-b9f4-d90d447a455e",
    "total_versions": 3,
    "current_version": 3,
    "created_at": "2026-09-27T05:25:00Z",
    "updated_at": "2026-09-27T05:35:10Z",
    "versions": [ ... array of ParcelVersionRecord objects ... ]
  }
  ```

### `GET /api/parcels/{uuid}/versions/{version}`
Retrieves a specific historical version, along with an automated geometric comparison against the immediately preceding version.
- **Response** (`200 OK`):
  ```json
  {
    "parcel_uuid": "58039d15-328e-5d1d-a453-a06e4f3cbfa3",
    "version_number": 3,
    "geometry": { "type": "Polygon", "coordinates": [...] },
    "decision": "SURVEYOR_APPROVED_CORRECTION",
    "review_status": "APPROVED",
    "reviewer": "Senior Surveyor Ramesh K. (Badge #401)",
    "created_at": "2026-09-26T11:15:00Z",
    "change_reason": "Surveyor-approved correction following joint physical boundary verification",
    "comparison_with_previous": {
      "version_a": 2,
      "version_b": 3,
      "area_change": {
        "area_a_m2": 359.09,
        "area_b_m2": 359.09,
        "diff_m2": 0.0,
        "percent_change": 0.0
      },
      "boundary_change": {
        "metric_iou": 0.9437,
        "symmetric_difference_m2": 20.81,
        "has_boundary_change": true,
        "perimeter_a_m": 75.89,
        "perimeter_b_m": 75.89
      },
      "centroid_shift": {
        "centroid_a": [12.976129, 77.63818],
        "centroid_b": [12.976127, 77.638177],
        "distance_m": 0.394,
        "bearing_deg": 235.2
      },
      "summary": "Version 2 → 3: Area Δ=+0.00 m² (+0.00%), Boundary IoU=94.4%, Centroid Shift=0.39m."
    }
  }
  ```

### `POST /api/parcels/{uuid}/new-version`
Appends a new version to the immutable ledger.
- **Request Body**:
  ```json
  {
    "geometry": { "type": "Polygon", "coordinates": [...] },
    "source_datasets": ["drone_survey_oct2025.geojson"],
    "confidence": 0.92,
    "iou": 0.91,
    "centroid_drift": 0.45,
    "decision": "AUTO_RECONCILED",
    "review_status": "APPROVED",
    "reviewer": "TerraNode Auto Reconciliation Engine",
    "change_reason": "High-confidence orthomosaic feature alignment."
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Parcel not found in registry.
  - `409 Conflict`: Version number already exists in ledger (`DuplicateVersionError`).
  - `422 Unprocessable Entity`: Invalid geometry or non-monotonic version decrement.

---

## 5. Frontend User Experience

The TerraNode React UI provides a dedicated, accessible **Parcel Version History Modal** accessible directly from the parcel table or map view:

1. **Version Timeline**:
   - Chronological card progression displaying Version tags (`v1`, `v2`, `v3`).
   - Visual badges for decisions (`AUTO_RECONCILED`, `OFFICER_APPROVED`, `REVIEW_REQUIRED`).
   - Audit trail metadata: Reviewer, Timestamp, Confidence, IoU, and Centroid drift.
2. **Version Comparison & Geometric Diff**:
   - Dropdown selectors allowing pairwise comparison of any two versions.
   - Dual-layer SVG spatial overlay rendering previous boundary (dashed amber) and current boundary (solid emerald).
   - High-contrast metric difference summary:
     - Area Delta ($\Delta\text{m}^2$ and $\%$)
     - Boundary IoU ($0-100\%$)
     - Centroid Drift ($\text{m}$)
3. **Structured Legal Audit Narrative**:
   - **What changed**: Detailed boundary difference and geometric shifts.
   - **Why changed**: Legally binding change reason submitted during ingestion or review.
   - **Who approved it**: Officer identification or automated engine provenance.

---

## 6. Verification & Automated Test Suite

Tested in [`tests/test_version_history.py`](../tests/test_version_history.py) with 100% pass rate:
- `test_create_sequential_versions`: Ingestion and append-only version increments.
- `test_duplicate_version_constraint_raises_error`: Enforces `(parcel_uuid, version_number)` uniqueness and HTTP 409 Conflict.
- `test_version_monotonicity_constraint`: Prevents out-of-order version retro-fitting.
- `test_immutable_history_no_deletion`: Asserts historical records cannot be deleted.
- `test_geometry_comparison_metrics`: Validates metric UTM calculations for Area Delta, IoU, and Centroid Shift distance.
- `test_api_endpoints_history_and_versions`: Validates live FastAPI endpoint responses.
- `test_api_parcel_not_found`: Validates HTTP 404 behavior for unknown parcels.
