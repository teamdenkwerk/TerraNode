# TERRANODE Immutable Audit Trail Specification

## 1. Audit Principles

Every administrative decision, spatial modification, and reconciliation step in TERRANODE is recorded in an immutable ledger satisfying the Six Fundamental Inquiries:
- **WHO?** The executing algorithm, officer, or service component.
- **WHAT?** The exact operation executed (e.g. boundary merge, review resolution).
- **WHEN?** High-precision UTC timestamp.
- **WHY?** Dual explanation (plain-English officer rationale + technical metric justification).
- **USING WHICH DATA?** Input datasets, dataset versions, and detected CRS.
- **WITH WHICH RESULT?** Resulting canonical polygon, IoU, centroid drift, confidence score, and decision status.

---

## 2. Sample Audit Record (`/api/audit/{parcel_id}`)

```json
{
  "parcel_id": "CAD-01-001",
  "audit_record": {
    "what": "Parcel boundary consensus & title ledger verification",
    "who": "TERRANODE Authoritative Consensus Engine (v2026.1)",
    "when": "2026-09-27 10:01:09 UTC",
    "using_which_data": [
      {
        "source": "Cadastral Survey Layer",
        "crs": "EPSG:4326 -> EPSG:32644",
        "status": "validated"
      },
      {
        "source": "Municipal GIS Layer",
        "crs": "EPSG:4326 -> EPSG:32644",
        "status": "validated"
      },
      {
        "source": "Field GNSS RTK Ground Truth",
        "accuracy_m": 0.81,
        "status": "verified"
      }
    ],
    "why": {
      "boundary_agreement": "Boundary agreement is very high (84.0% spatial match)",
      "centroid_shift": "Centroid shift is acceptable (0.92m shift, within allowable 2.0m limit)",
      "source_agreement": "Cadastral and Municipal boundaries strongly align",
      "recommended_action": "Approved for automated registration in the digital spatial registry."
    },
    "technical_metrics": {
      "iou_agreement": 0.84,
      "centroid_drift_meters": 0.92,
      "confidence_score": 0.88,
      "formula_breakdown": {
        "weight_match_term (50%)": 0.445,
        "weight_iou_term (35%)": 0.294,
        "weight_extraction_term (15%)": 0.1275,
        "sum_confidence": 0.88
      }
    },
    "decision": "AUTO-RECONCILED",
    "canonical_geometry_version": "v2.0",
    "review_status": "Passed automated validation"
  }
}
```
