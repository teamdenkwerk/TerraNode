# TERRANODE FEATURE 02 — LEGACY CRS INTELLIGENCE SPECIFICATION

## 1. Executive Summary & Problem Formulation

Cadastral datasets across Indian land administrations (Survey of India, State Revenue Departments, Urban Local Bodies) frequently present severe spatial reference inconsistencies:
- **Missing CRS metadata**: Scanned paper maps and digitized DXF/SHP files frequently omit `.prj` sidecars or OGC WKT strings.
- **Coordinate-range mismatches**: Datasets declare projected metric coordinate systems (e.g. UTM Zone 43N) in header metadata, but their coordinates are unprojected angular degrees (e.g. `[77.64, 12.97]`).
- **Unverified local grids**: Historic cadastre sheets using local village stone datum or arbitrary millimeter offsets.
- **Incorrectly declared CRS**: Arbitrary or deprecated projection codes assigned during bulk GIS conversion.

**TERRANODE Legacy CRS Intelligence** (`backend/geospatial/crs_intelligence.py`) provides an automated, mathematically defensible diagnostic layer that detects, validates, suggests, and reprojects datasets while strictly preventing silent data corruption.

---

## 2. Architectural Workflow

```
Input Dataset (SHP, GeoJSON, TIFF, CSV)
      ↓
Read Declared CRS (extract header / .prj)
      ↓
Validate Declared CRS via PyProj (Strict EPSG/WKT compliance)
      ↓
Inspect Coordinate Ranges (sample vertices, compute bounds & magnitudes)
      ↓
Inspect AOI Metadata (cross-reference known administrative centers)
      ↓
Detect Inconsistencies & Anomalies (mismatch, overflow, local grid)
      ↓
Calculate Mathematical Confidence (deterministic; zero fabricated scores)
      ↓
Require Confirmation if Uncertain (Guardrail: threshold < 0.75 triggers officer review)
      ↓
Transform to Metric Processing CRS (UTM projected coordinate system for IoU/Drift)
      ↓
Preserve Original & Output Display CRS (EPSG:4326 for Leaflet Web Map)
```

---

## 3. Verified Indian CRS Catalog

TerraNode uses an authoritative catalog of verified Indian coordinate reference systems. Zero historical definitions are invented:

| EPSG Code | System Name | Type | Central Meridian / Region | Primary Jurisdictions |
|:---|:---|:---|:---|:---|
| **EPSG:4326** | WGS 84 2D | Geographic | Prime Meridian (Degrees) | Global standard / Display CRS |
| **EPSG:32642** | WGS 84 / UTM zone 42N | Projected (m) | $69^\circ\text{ E}$ | Western India / Gujarat / Rajasthan |
| **EPSG:32643** | WGS 84 / UTM zone 43N | Projected (m) | $75^\circ\text{ E}$ | Western & Southern India (Mumbai, Bengaluru, Goa) |
| **EPSG:32644** | WGS 84 / UTM zone 44N | Projected (m) | $81^\circ\text{ E}$ | Central & Southern India (Chennai, Hyderabad, Delhi NCR) |
| **EPSG:32645** | WGS 84 / UTM zone 45N | Projected (m) | $87^\circ\text{ E}$ | Eastern India (Kolkata, Odisha, Bihar, West Bengal) |
| **EPSG:32646** | WGS 84 / UTM zone 46N | Projected (m) | $93^\circ\text{ E}$ | Northeast India (Assam, Meghalaya, Tripura, Mizoram) |
| **EPSG:7760** | WGS 84 / Delhi LCC | Projected (m) | State Grid | Survey of India / State Official Cadastral Survey |
| **EPSG:24379** | Kalianpur 1975 / Zone IIa | Projected (m) | Historical Topo | Survey of India Historical Cadastre |
| **EPSG:24380** | Kalianpur 1975 / Zone IIb | Projected (m) | Historical Topo | Survey of India Historical Cadastre |
| **EPSG:3857** | WGS 84 / Pseudo-Mercator | Projected (m) | Auxiliary Sphere | Web Mercator Metric Grid |

---

## 4. Anomaly Detection Matrix

| Anomaly Condition | Detection Heuristic | Remediation Action | Status |
|:---|:---|:---|:---|
| **Coordinate-Range Mismatch (Projected $\rightarrow$ Degrees)** | Declared projected CRS (`is_projected=True`), but coordinates satisfy $-180 \le X \le 180$ and $-90 \le Y \le 90$. | Resolves to `EPSG:4326` with confidence $0.85$. Flags inconsistency and demands officer confirmation. | `REQUIRES_CONFIRMATION` |
| **Coordinate-Range Overflow (Geographic $\rightarrow$ Meters)** | Declared geographic CRS (`is_geographic=True`), but coordinate magnitudes $|X| > 180$ or $|Y| > 90$. | Flags coordinate overflow. Re-evaluates extent against regional UTM zones. | `REQUIRES_CONFIRMATION` |
| **Missing CRS Metadata (Degrees)** | Declared CRS is missing (`None`), but coordinates fall within Indian bounds ($68 \le X \le 98$, $6 \le Y \le 38$). | Resolves to `EPSG:4326` with confidence $0.95$. Calculates UTM processing CRS. | `READY` |
| **Missing CRS Metadata (Projected)** | Declared CRS is missing, coordinates are metric meters, but no AOI metadata exists. | Guardrail prevents silent guess across UTM zones (42N–46N). Confidence set to $0.65$. Presents options for human selection. | `REQUIRES_CONFIRMATION` |
| **Invalid / Unparseable EPSG** | PyProj throws `CRSError` on user input string (e.g. `EPSG:999999`). | Logs unparseable definition. Falls back to coordinate range analysis with explicit warning. | `REQUIRES_CONFIRMATION` |
| **Local Sheet Cartesian Grid** | Coordinates are non-geographic and small-scale ($< 1000$ units) without georeferencing. | Flags local village sheet grid. Requires tie-point affine transformation. | `REQUIRES_CONFIRMATION` |

---

## 5. Non-Silent Guardrail Invariant

```python
# Absolute safety invariant in LegacyCRSIntelligence:
if confidence < 0.75 or inconsistencies:
    requires_confirmation = True
    if transformation_status == TransformationStatus.READY:
        transformation_status = TransformationStatus.REQUIRES_CONFIRMATION
```

**Rule**: The system **never silently guesses** or alters spatial references when confidence falls below the $75\%$ threshold. An officer must explicitly review and sign off on the suggested reference system.

---

## 6. Audit Data Model

Every evaluated dataset persists all 7 mandatory audit attributes:

```json
{
  "dataset_id": "bengaluru-ward112",
  "declared_crs": "EPSG:7760 / EPSG:32643 → EPSG:4326",
  "original_crs": "EPSG:7760 / EPSG:32643",
  "detected_crs": "EPSG:4326",
  "processing_crs": "EPSG:32643",
  "display_crs": "EPSG:4326",
  "coordinate_range": {
    "min_x": 77.638046,
    "max_x": 77.643596,
    "min_y": 12.97598,
    "max_y": 12.980891,
    "units": "degrees",
    "is_geographic": true,
    "is_projected": false,
    "sample_count": 320
  },
  "crs_detection_method": "DECLARED_AUTHORITATIVE",
  "crs_confidence": 1.0,
  "crs_warning": null,
  "warnings": [],
  "inconsistencies": [],
  "requires_confirmation": false,
  "transformation_status": "READY",
  "suggested_crs_options": []
}
```

---

## 7. REST API Endpoints

### 7.1 Diagnostic Audit Report
- **Route**: `GET /api/datasets/{dataset_id}/crs-report`
- **Response**: Full `CRSIntelligenceReport` JSON with detected reference systems, coordinate bounds, anomaly warnings, and confidence scoring.

### 7.2 Officer CRS Confirmation
- **Route**: `POST /api/datasets/{dataset_id}/crs-confirm`
- **Payload**:
  ```json
  {
    "confirmed_crs": "EPSG:32643",
    "officer_id": "OFFICER-GNSS-42",
    "notes": "Verified against local cadastral survey sheet #104"
  }
  ```
- **Response**: Confirmation receipt with updated catalog metadata and signature timestamp.

---

## 8. Verification & Test Suite

The test suite in [`tests/test_crs_intelligence.py`](file:///tests/test_crs_intelligence.py) verifies all core behaviors (13 automated tests):
1. `test_valid_geographic_epsg`: Authoritative resolution of `EPSG:4326` ($1.0$ confidence).
2. `test_valid_projected_epsg`: Authoritative resolution of `EPSG:32643` with metric coords.
3. `test_missing_crs_indian_geographic_extent`: Inferred `EPSG:4326` from India bounds ($0.95$ confidence).
4. `test_missing_crs_projected_uncertainty_guardrail`: Guardrail verification ($0.65$ confidence $< 0.75$, requires confirmation).
5. `test_invalid_epsg_code`: Flagging `EPSG:999999` with anomaly tracking.
6. `test_mismatch_declared_projected_with_degree_coordinates`: Critical coordinate-range mismatch detection.
7. `test_mismatch_declared_geographic_with_projected_coordinates`: Coordinate overflow detection.
8. `test_coordinate_range_geographic_classification`: Degree bounding unit deduction.
9. `test_coordinate_range_projected_classification`: Metric projection unit deduction.
10. `test_transform_geometry_safely`: PyProj polygon transformation and inverse round-trip consistency.
11. `test_api_get_crs_report_bengaluru`: API endpoint return verification.
12. `test_api_get_crs_report_not_found`: Proper HTTP 404 response for invalid dataset IDs.
13. `test_api_confirm_crs`: Authoritative officer confirmation flow.
