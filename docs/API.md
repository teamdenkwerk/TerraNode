# TERRANODE REST API Specification

**Base URL:** `http://localhost:8000`  
**Swagger UI:** `http://localhost:8000/docs`  
**API Version:** `2026.1.0`  

---

## 1. System Health & Readiness

### `GET /health`
Returns basic service availability and PostgreSQL connection state.

### `GET /health/ready`
Performs comprehensive deep check of all platform subsystems:
- `api`: FastAPI runtime and version
- `database`: PostgreSQL connectivity
- `postgis`: PostGIS extension presence
- `storage`: Upload folder read/write capability
- `ml_engine`: Truthful ML readiness status

---

## 2. Policy & Telemetry

### `GET /api/policy`
Returns the centralized authoritative reconciliation policy configuration.
```json
{
  "success": true,
  "policy": {
    "version": "2026.1",
    "auto_reconcile_confidence_min": 0.85,
    "review_confidence_min": 0.70,
    "max_centroid_drift_meters": 2.0,
    "weight_match_score": 0.50,
    "weight_iou_agreement": 0.35,
    "weight_extraction_score": 0.15
  },
  "rules": {
    "auto_reconciled": "Confidence >= 85% AND Centroid Drift < 2.0m",
    "review_required": "70% <= Confidence < 85% AND Centroid Drift < 2.0m",
    "conflict": "Confidence < 70% OR Centroid Drift >= 2.0m"
  }
}
```

### `GET /validation/production`
Returns live 5-module production validation metrics computed on active datasets.

---

## 3. Asynchronous Job Processing

### `POST /api/jobs`
Initiates a background reconciliation batch.
```json
{
  "dataset_a_filename": "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson",
  "dataset_b_filename": "85f02bb7-ec7a-4285-ae1f-450c5f9c2768.geojson"
}
```

### `GET /api/jobs/{job_id}/status`
Returns real progress percent (0–100%) and current stage (`CREATED`, `INGESTING`, `VALIDATING`, `PROJECTING`, `MATCHING`, `RECONCILING`, `COMPLETED`).

---

## 4. Audit Trail & Certificates

### `GET /api/audit/{parcel_id}`
Returns complete immutable ledger record for a reconciled parcel.

### `GET /api/certificates/{parcel_id}`
Generates official Digital Reconciliation Certificate for land administration.

---

## 5. Feature 01: Smart Schema Mapping

### `POST /api/schema/mapping`
Inspects uploaded dataset columns, normalizes abbreviations, evaluates semantic equivalence against the 10 canonical fields, and returns suggestions with mathematically derived confidence scores.

### `GET /api/schema/mapping/{dataset_id}`
Retrieves active schema suggestions and persisted officer confirmation record for the given dataset.

### `POST /api/schema/mapping/{dataset_id}/confirm`
Persists manual officer confirmation or rejection of suggested field mappings with dataset versioning and an immutable audit trail.
See full specification in [`docs/SMART_SCHEMA_MAPPING.md`](./SMART_SCHEMA_MAPPING.md).

---

## 6. Feature 02: Legacy CRS Intelligence

### `GET /api/datasets/{dataset_id}/crs-report`
Runs comprehensive CRS diagnostic analysis for the dataset. Evaluates declared CRS via PyProj, inspects coordinate extents, checks regional administrative AOI mappings, detects coordinate-range mismatches, and calculates non-fabricated confidence.
Guardrail: datasets with confidence $< 0.75$ require officer review before processing.

### `POST /api/datasets/{dataset_id}/crs-confirm`
Persists officer-confirmed CRS assignment when initial confidence required review. Updates dataset catalog record with audit notes.
See full specification in [`docs/CRS_INTELLIGENCE.md`](./CRS_INTELLIGENCE.md).

---

## 7. Feature 03: Permanent Parcel Identity

### `POST /api/parcels/identity/resolve`
Resolves an incoming parcel representation (or array of representations) against the permanent parcel identity registry.
Preserves `parcel_uuid` when geometric continuity ($\text{IoU} \ge 70\%$, $\text{Drift} < 2.0\text{ m}$) is established across changing survey numbers, municipal IDs, or source filenames.
Flags `IDENTITY_UNCERTAIN` and requires review when continuity falls below policy thresholds.
Guardrail: Never merges parcels solely because names or IDs look similar.

### `GET /api/parcels/{parcel_uuid}`
Returns the complete parcel profile including `parcel_uuid`, `source_ids`, `survey_numbers`, `municipal_ids`, `current_geometry_version`, `status`, `created_at`, `updated_at`, `geometry`, `area_m2`, and `centroid`.

### `GET /api/parcels/{parcel_uuid}/sources`
Returns all historical source snapshots, contributing datasets, match evidence, and chronological lineage events for the permanent parcel.
See full specification in [`docs/PERMANENT_PARCEL_IDENTITY.md`](./PERMANENT_PARCEL_IDENTITY.md).

---

## 8. Feature 04: Parcel Version History

### `GET /api/parcels/{parcel_uuid}/history`
Returns chronological immutable version timeline for the parcel, including all recorded geometries, decisions, confidence metrics, and approval reasons.

### `GET /api/parcels/{parcel_uuid}/versions/{version}`
Returns full record of a specific version with metric UTM geometric comparison against the immediately preceding version (`area_change`, `boundary_change`, `centroid_shift`).

### `POST /api/parcels/{parcel_uuid}/new-version`
Appends a new version to the immutable ledger. Enforces compound uniqueness `(parcel_uuid, version_number)` returning HTTP 409 Conflict if duplicate.
See full specification in [`docs/PARCEL_VERSION_HISTORY.md`](./PARCEL_VERSION_HISTORY.md).

---

## 9. Feature 05: Conflict Lifecycle State Machine

### `GET /api/conflicts`
Lists all active and historical conflicts with filtering by `state`, `severity`, or `parcel_uuid`.

### `GET /api/conflicts/{id}`
Retrieves a specific conflict record by its conflict ID or parcel reference. Returns current state, allowed next transitions, discrepancy metrics, and full chronological transition audit history.

### `POST /api/conflicts/{id}/transition`
Executes an authoritative state transition across the 9 defined states (`DETECTED`, `UNDER_REVIEW`, `SURVEY_REQUIRED`, `SURVEY_RECEIVED`, `RECONCILIATION_PENDING`, `RESOLVED`, `APPROVED`, `REJECTED`, `REOPENED`).
Strictly validates against the finite state machine graph; rejects invalid transitions with HTTP 400 Bad Request.
Records `parcel_uuid`, `previous_state`, `new_state`, `actor`, `timestamp`, `reason`, and `evidence`.
See full specification in [`docs/CONFLICT_STATE_MACHINE.md`](./CONFLICT_STATE_MACHINE.md).

---

## 10. Feature 06: Advanced Multi-Source Matching

### `GET /api/matching/config`
Returns authoritative configuration including the 8 normalized signal weights (strictly summing to 1.000) and classification thresholds (`STRONG_MATCH`, `POSSIBLE_MATCH`, `WEAK_MATCH`, `NO_MATCH`).

### `POST /api/matching/evaluate-pair`
Evaluates a single pair of geometries and associated property attributes. Returns composite candidate score, categorical classification, all 8 sub-scores (`iou_score`, `centroid_score`, `area_score`, `perimeter_score`, `shape_score`, `bbox_score`, `source_agreement_score`, `identifier_score`), and raw physical metrics.

### `POST /api/matching/batch`
Executes spatial candidate generation and multi-signal scoring between two GeoJSON feature collections using STRtree indexing.
Returns matched candidate pairs and `MatchingBenchmarkResult` containing theoretical brute-force pairs, actual comparisons, candidate reduction ratio ($> 85-95\%$), and execution timing.
See full specification in [`docs/ADVANCED_MULTI_SOURCE_MATCHING.md`](./ADVANCED_MULTI_SOURCE_MATCHING.md).

---

## 11. Enhancement 07: Infrastructure & Utility Crossing Intelligence

### `GET /api/infrastructure/layers`
Lists all supported infrastructure layers (Roads, Drainage, Water, Electricity, Railway, Public Utilities) with feature counts, verification statuses, and transparent unavailability descriptions.
```json
[
  {
    "category": "road",
    "display_name": "Public Roads & Right of Way",
    "feature_count": 5,
    "source_dataset_id": "bbmp_arterial_roads_2026",
    "source_name": "BBMP Major Roads Division",
    "verification_status": "VERIFIED",
    "is_available": true,
    "unavailable_reason": null,
    "required_dataset": null
  },
  {
    "category": "water",
    "display_name": "Water Supply Pipelines",
    "feature_count": 0,
    "source_dataset_id": null,
    "source_name": "Bangalore Water Supply and Sewerage Board (BWSSB)",
    "verification_status": "REFERENCE_ONLY",
    "is_available": false,
    "unavailable_reason": "No water distribution network GIS dataset has been ingested.",
    "required_dataset": "BWSSB GIS pipeline distribution layer (SHP/GeoJSON/DXF)"
  }
]
```

### `GET /api/infrastructure/features?layer_type={layer_type}`
Returns GeoJSON FeatureCollection of verified infrastructure line/polygon features for Leaflet client rendering.

### `GET /api/parcels/{parcel_uuid}/infrastructure-intersections`
Evaluates whether a reconciled parcel spatially intersects infrastructure networks. Computes exact metric length (meters), affected area (m²), percentage, and minimum proximity distance in projected UTM CRS.
Uses strictly neutral terminology (`Spatial Intersection Detected`, `Infrastructure Overlap`, never legal accusations).

---

## 12. Enhancement 08: Historical Ground Truth & Spatial Change Evidence

### `GET /api/parcels/{parcel_uuid}/timeline`
Retrieves chronological timeline of dated verified historical snapshots (Cadastral, Municipal, Drone ORI, CORS RTK). Handles missing historical data transparently by specifying required second epoch.
```json
{
  "parcel_uuid": "58039d15-8889-497d-a111-923f5b7ea577",
  "has_historical_data": true,
  "message": "Verified historical parcel versions available.",
  "required_dataset": null,
  "total_versions": 3,
  "timeline": [
    {
      "version_number": 1,
      "source_type": "Official Cadastral",
      "source_name": "Karnataka Revenue Cadastral Survey",
      "source_date": "2022-04-15",
      "verification_status": "VERIFIED",
      "area_m2": 207.44,
      "centroid": [12.9628, 77.6391]
    }
  ]
}
```

### `GET /api/parcels/{parcel_uuid}/compare?version_a={va}&version_b={vb}`
Performs rigorous metric geometric comparison between two historical versions in projected UTM CRS (`EPSG:32643` / `EPSG:32644`).
Returns `area_change_m2`, `area_change_percentage`, `centroid_shift_m`, `iou`, `boundary_change`, and `source_agreement`.

---

## 13. Enhancement 09: Unified Reconciliation Evidence & Decision Card

### `GET /api/parcels/{parcel_uuid}/evidence`
Synthesizes the single comprehensive 9-pillar Reconciliation Evidence object for a parcel:
1. Multilateral Source Evidence
2. Projected UTM Metric Geometry (area, perimeter, validation)
3. Advanced 8-Signal Matching Breakdown & Weights
4. Centralized Threshold & Policy Consensus
5. CORS/RTK GNSS Ground Truth Checkpoint
6. Dated Historical Continuity & Version Lineage
7. Infrastructure & Utility Spatial Crossing Analysis
8. Finite State Machine Review Audit Trail
9. Final Certified Decision Card

### `GET /api/reconciliation/{reconciliation_id}/evidence`
Retrieves the 9-pillar evidence ledger for an entire reconciliation batch or session run.



