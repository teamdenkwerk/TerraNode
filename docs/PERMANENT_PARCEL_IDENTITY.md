# TERRANODE FEATURE 03 — PERMANENT PARCEL IDENTITY SPECIFICATION

## 1. Executive Summary & Problem Formulation

In Indian land administration, government source identifiers are inherently unstable across departments and time:
- **Revenue Survey Numbers** mutate during resurveys, sub-divisions, and consolidation (e.g. `101` $\rightarrow$ `101/A` $\rightarrow$ `101/4B`).
- **Municipal Property Tax IDs (PIDs)** are re-indexed during municipal ward delimitation and GIS digitization drives.
- **Source Filenames & Dataset Versions** change with every ingestion cycle.

If an identity system generates a new random UUID upon each processing run, historical lineage collapses, parcel provenance is lost, and identical land parcels become duplicated.

**TERRANODE Permanent Parcel Identity** (`backend/identity/identity_service.py`) provides an immutable internal identity layer that resolves, tracks, and preserves `parcel_uuid` across changing government identifiers using verified geometric and topological evidence.

---

## 2. Core Architectural Workflow

```
Incoming Source Record (Dataset, Source ID, Survey No, Municipal ID, Geometry)
                         ↓
               Validate Input Geometry (Repair bowtie/self-intersections)
                         ↓
           Spatial Candidate Search via R-Tree (STRtree Index)
                         ↓
            Calculate Metric Spatial Evidence (UTM Projection)
         (Metric IoU Agreement, Metric Centroid Drift in meters)
                         ↓
         Evaluate Continuity vs Authoritative Policy Thresholds
                         ↓
  ┌──────────────────────┼──────────────────────┬──────────────────────┐
  │                      │                      │                      │
[Continuity Verified]  [Sub-Threshold Drift/IoU] [Duplicate Record] [No Overlap Found]
(IoU >= 70%, Drift <2m) (IoU < 70% or Drift >=2m) (Exact same source) (IoU < 15%)
  │                      │                      │                      │
  ↓                      ↓                      ↓                      ↓
PRESERVE parcel_uuid   IDENTITY_UNCERTAIN    PRESERVE parcel_uuid   GENERATE NEW
- Append new Survey No - needs_review = True - No duplicate records  Deterministic UUID
- Append new PID       - Require Officer      - Timestamp updated    - Version = v1.0
- Bump Geometry Version  Review
```

---

## 3. Strict Safety Guardrail

> [!IMPORTANT]
> **SAFETY INVARIANT: NEVER MERGE PARCELS SOLELY BECAUSE NAMES OR IDS LOOK SIMILAR.**
>
> If two incoming records have the exact same survey number (e.g. `Plot-1` or `Sy.No. 104`) but their physical geometries are in different geographic locations (or their centroid drift exceeds authoritative thresholds), TerraNode **strictly refuses to merge them**.
> - If distance is large ($> 50\text{ m}$), they are registered as distinct, isolated permanent parcels.
> - If distance is moderate ($2.0\text{ m} \le \text{drift} < 10.0\text{ m}$), they are flagged as `IDENTITY_UNCERTAIN` requiring officer review.

---

## 4. Stored Parcel Identity Schema

Every internal parcel record stores all 8 mandatory audit attributes alongside geometry, metric area, centroid, and lineage:

```json
{
  "parcel_uuid": "2dec5c4d-cc5b-525f-b9f4-d90d447a455e",
  "source_ids": ["CAD-101", "REV-2025-99", "MUN-2026-X"],
  "survey_numbers": ["101/A", "101/A-REV", "101/4B"],
  "municipal_ids": ["PID-DOM-101", "PID-2026-X"],
  "current_geometry_version": "v2.0",
  "status": "ACTIVE",
  "created_at": "2026-09-27T05:25:53Z",
  "updated_at": "2026-09-27T05:27:34Z",
  "geometry": {
    "type": "Polygon",
    "coordinates": [...]
  },
  "centroid": [12.9782, 77.64025],
  "area_m2": 2403.5,
  "confidence_score": 1.0,
  "needs_review": false,
  "review_reason": null,
  "source_records": [
    {
      "source_record_id": "SRC-2feebaa6",
      "source_dataset": "cadastre_2024",
      "source_id": "CAD-101",
      "survey_number": "101/A",
      "municipal_id": "PID-DOM-101",
      "geometry_version": "v1.0",
      "recorded_at": "2026-09-27T05:25:53Z",
      "match_evidence": { "action": "NEW_PARCEL_CREATED" }
    }
  ],
  "lineage": [
    {
      "event_id": "EVT-1b070ff9",
      "event_type": "PARCEL_CREATED",
      "timestamp": "2026-09-27T05:25:53Z",
      "description": "Registered new permanent parcel from cadastre_2024 (ID: CAD-101)"
    },
    {
      "event_id": "EVT-7ab76a35",
      "event_type": "SURVEY_NUMBER_EVOLVED",
      "timestamp": "2026-09-27T05:26:10Z",
      "description": "Survey number evolved: added '101/A-REV' (Historical: ['101/A'])"
    },
    {
      "event_id": "EVT-bd93a604",
      "event_type": "GEOMETRY_REVISED",
      "timestamp": "2026-09-27T05:27:34Z",
      "description": "Geometry revised from v1.0 to v2.0 (IoU: 95.7%, Drift: 0.77m)"
    }
  ]
}
```

---

## 5. REST API Specification

### 5.1 Identity Resolution Endpoint
- **Route**: `POST /api/parcels/identity/resolve`
- **Payload**:
  ```json
  {
    "source_dataset": "revenue_survey_2026",
    "source_id": "REV-9912",
    "survey_number": "101/4B-NEW",
    "municipal_id": "PID-9912",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[77.6400, 12.9780], [77.6405, 12.9780], [77.6405, 12.9784], [77.6400, 12.9784], [77.6400, 12.9780]]]
    }
  }
  ```
- **Response**: `IdentityResolutionResult` detailing `parcel_uuid`, `resolution_action`, `status`, `current_geometry_version`, `iou`, `centroid_drift_m`, and `needs_review`.

### 5.2 Parcel Retrieval Endpoint
- **Route**: `GET /api/parcels/{parcel_uuid}`
- **Response**: Complete `ParcelIdentityRecord` with permanent identity, historical identifiers, timestamps, and current geometry. Returns HTTP 404 if not found.

### 5.3 Source Provenance & Lineage Endpoint
- **Route**: `GET /api/parcels/{parcel_uuid}/sources`
- **Response**: Full snapshot history of every ingested dataset contributing to this parcel, match evidence, and chronological lineage events. Returns HTTP 404 if not found.

---

## 6. Automated Test Coverage

The test suite in [`tests/test_parcel_identity.py`](file:///tests/test_parcel_identity.py) provides 11 rigorous automated tests:
1. `test_new_parcel_registration`: Deterministic UUID issuance and initial `v1.0` state.
2. `test_same_parcel_reupload`: Verifies idempotence without creating duplicate entities.
3. `test_changed_survey_number`: Preserves `parcel_uuid` when government survey number changes.
4. `test_changed_municipal_id`: Preserves `parcel_uuid` when municipal property ID changes.
5. `test_geometry_revision`: Advances `current_geometry_version` (`v1.0` $\rightarrow$ `v2.0`) upon verified boundary adjustments.
6. `test_duplicate_source_records`: Detects and ignores redundant submissions.
7. `test_uncertain_identity`: Enforces `IDENTITY_UNCERTAIN` status and `needs_review=True` on sub-threshold continuity.
8. `test_guardrail_never_merge_solely_on_id_similarity`: Refuses to merge parcels sharing identical survey numbers at different physical locations.
9. `test_api_resolve_and_get_parcel`: Tests REST POST resolve and GET parcel profile.
10. `test_api_get_parcel_sources`: Tests REST GET sources and lineage audit trail.
11. `test_api_parcel_not_found`: Verifies HTTP 404 handling.
