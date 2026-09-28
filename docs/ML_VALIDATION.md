# TERRANODE Machine Learning Validation & Readiness Report

## 1. Scientific Integrity Policy

TERRANODE maintains a strict anti-fabrication stance regarding Artificial Intelligence and Machine Learning. The platform never claims "99% AI accuracy" or displays pseudo-ML confidence badges without verified, defensible ground truth.

---

## 2. Current Model Status

**Status:**
`ML validation unavailable — insufficient verified labelled data`

### Data Evaluation:
- **Verified Ground-Truth Checkpoints Indexed:** 11 RTK field points (Bengaluru — Domlur Sector).
- **Statistically Defensible Minimum for ML Training:** 500 verified parcel samples.
- **Operational Reconciliation Mode:** Deterministic Rule-Based Consensus Engine (v2026.1).

---

## 3. ML-Ready Feature Pipeline

The platform includes a complete, operational 12-dimensional feature extraction pipeline in `backend/ml/features.py`:
1. `iou`: Geometric Intersection-over-Union [0, 1]
2. `centroid_drift_m`: Euclidean distance in projected meters
3. `area_difference_pct`: Relative percentage area difference
4. `perimeter_difference_pct`: Relative boundary length difference
5. `shape_compactness_a`: Polsby-Popper compactness of geometry A
6. `shape_compactness_b`: Polsby-Popper compactness of geometry B
7. `vertex_count_a`: Number of boundary vertices in A
8. `vertex_count_b`: Number of boundary vertices in B
9. `overlap_ratio_a`: Intersection area divided by area A
10. `overlap_ratio_b`: Intersection area divided by area B
11. `source_count`: Number of independent sources
12. `extraction_quality`: Upstream model extraction quality [0, 1]

Feature vectors are extracted and logged during reconciliation runs to prepare the training corpus for future supervised XGBoost training once sufficient field labels are collected.
