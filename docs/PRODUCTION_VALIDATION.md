# TERRANODE Production Validation Dashboard Documentation

## 1. Overview

The Technical Production Validation Dashboard is served via:
- Backend: `GET /validation/production` and `GET /api/validation/production`
- Frontend: `Validation -> Production Validation Dashboard (/validation/production)`

Every statistic on this dashboard is computed live from actual uploaded datasets in `data/uploads/` without hardcoded mocks.

---

## 2. Telemetry Modules

### 1. Data Quality & CRS
- **Total Ingested Records:** 75 (Cadastral 37 + Municipal 38)
- **Valid Records:** 75 (100% passed all 20 invariant checks)
- **Invalid Geometries:** 0
- **Detected CRS:** EPSG:4326 (WGS 84)
- **Projected Target CRS:** EPSG:32644 / EPSG:32643 (UTM projected for metric safety)

### 2. Reconciliation Quality
- **Parcels Processed:** 37
- **Matched Parcels:** 37 (100%)
- **Auto-Reconciled:** 3 (8.1%)
- **Desk Review Required:** 29 (78.4%)
- **Spatial Conflicts:** 5 (13.5%)

### 3. Geometric Quality
- **Mean IoU:** 0.784 (78.4%)
- **Median IoU:** 0.825 (82.5%)
- **Mean Centroid Drift:** 1.30 m
- **95th Percentile Drift:** 2.42 m
- **Parcels Within 2.0m Safety Limit:** 86.5%

### 4. Ground-Truth Validation (Field RTK Survey)
- **Reference Checkpoints:** 11 GNSS RTK survey points
- **Field Survey Accuracy:** &plusmn; 0.81 m
- **Mean Displacement:** 0.742 m
- **RTK Ground-Truth Compliance (< 2m):** 100.0%

### 5. Machine Learning Validation Status
- **Status:** `ML validation unavailable — insufficient verified labelled data`
- **Current Verified Count:** 11 (minimum required: 500)
- **Operational Engine:** Deterministic Authoritative Engine (v2026.1)
