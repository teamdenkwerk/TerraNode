# TERRANODE System Architecture

## 1. High-Level Architecture Overview

TERRANODE is an enterprise geospatial reconciliation platform engineered to ingest, cross-reference, validate, and harmonize disparate land boundary data across multiple government and commercial sources (Revenue Cadastral surveys, Municipal GIS, Satellite/Drone orthomosaics, and Field GNSS RTK survey checkpoints).

```mermaid
graph TD
    A["Raw Geospatial Inputs\n(SHP, GeoJSON, TIF, CSV)"] --> B["Phase 2: Ingestion & 20-Check Invariant Validator"]
    B --> C["Phase 3: CRS & Spatial Safety Engine\n(Auto-UTM Projection EPSG:32643/32644)"]
    C --> D["Phase 4: Geometry Quality Engine\n(Disciplined Repair & Anti-Collapse)"]
    D --> E["Phase 5: STRtree Spatial Indexer\n(BBox Candidate Pruning)"]
    E --> F["Pairwise Spatial Scoring\n(IoU, Centroid Drift, Area Ratio)"]
    F --> G["Phase 1: Authoritative Reconciliation Policy\n(Auto >=85% & Drift <2m | Review 70-84% | Conflict)"]
    G --> H["Phase 6: Consensus Footprint Synthesis\n(Provenance Ledger)"]
    H --> I["Phase 10: Ground-Truth Validation Service\n(Field RTK Comparison)"]
    H --> J["Phase 17 & 22: Audit Trail & Official Certificate"]
```

## 2. Core Subsystems

1. **Authoritative Reconciliation Policy Engine (`backend/config/reconciliation_policy.py`)**:
   - Single point of truth defining auto-reconciliation, review, and conflict rules.
   - Confidence Formula: $\text{Confidence} = 0.50 \times \text{Match} + 0.35 \times \text{IoU Agreement} + 0.15 \times \text{Extraction}$.
2. **CRS & Metrology Engine (`backend/crs/transformer.py`)**:
   - Strictly enforces projected CRS (meters) for all Euclidean drift and area computations.
   - Prevents calculations on angular degrees.
3. **Geometry Quality Engine (`backend/geometry/validator.py`)**:
   - Returns structured `GeometryValidationResult`. Rejects unsafe repairs where area alters by $> 5\%$.
4. **Spatial Matching & Consensus (`matching/match_entities.py`, `reconciliation/resolve_conflicts.py`)**:
   - STRtree indexing with $O(N \log N)$ complexity.
   - Greedy union-find clustering with same-source collision protection.
5. **Ground Truth Validation (`backend/verification/ground_truth.py`)**:
   - Benchmarks canonical boundaries against GNSS RTK field survey points.
6. **Async Job Processing (`backend/routers/jobs.py`)**:
   - Non-blocking pipeline execution tracking progress from 0% to 100%.
