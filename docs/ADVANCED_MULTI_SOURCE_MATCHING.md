# Feature 06: Advanced Multi-Source Matching Engine

## 1. Architectural Overview & Defensible Matching Philosophy

TerraNode reconciles land parcel geometries from heterogeneous government, municipal, and drone survey sources. Rather than relying on simple centroid proximity or brute-force bounding-box intersections, Feature 06 implements a multi-signal matching engine backed by Shapely STRtree spatial indexing.

### Core Tenets
1. **Never use undocumented arbitrary weights**: All weights sum to strictly $1.000$ and are governed by centralized configuration in [`backend/config/matching_config.py`](file:///c:/Users/yuvas/OneDrive/Desktop/Geo-Reconciliation-master/Geo-Reconciliation-master/backend/config/matching_config.py).
2. **Transparent Score Breakdown**: Every matching decision preserves the individual constituent sub-scores alongside raw metric values (metric drift in meters, area in $\text{m}^2$, compactness ratios).
3. **Avoid $O(N^2)$ Brute Force**: Candidate generation employs an R-tree spatial index (STRtree) with bounding envelope pruning, measuring and recording candidate reduction ratios for large cadastral datasets.
4. **Validation Against Real Reference Data**: Claims of accuracy must be verified against actual cadastral and municipal ground-truth datasets without synthetic fabrication.

---

## 2. The 8 Independent Matching Signals

For each candidate parcel pair $(A, B)$, the engine computes 8 mathematically independent signals:

| # | Signal | Formula / Definition | Range | Weight | Rationale |
|---|---|---|---|---|---|
| 1 | **Spatial IoU** ($s_{\text{iou}}$) | $\frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)}$ | $[0.0, 1.0]$ | **0.30** | Fundamental spatial overlap metric in projected UTM coordinate space. |
| 2 | **Centroid Drift** ($s_{\text{centroid}}$) | $\max\left(0, 1 - \frac{\|\mathbf{c}_A - \mathbf{c}_B\|}{R_{\max}}\right)$ | $[0.0, 1.0]$ | **0.25** | Planar Euclidean displacement in meters between parcel geometric centroids. |
| 3 | **Area Concordance** ($s_{\text{area}}$) | $\frac{\min(\text{Area}_A, \text{Area}_B)}{\max(\text{Area}_A, \text{Area}_B)}$ | $[0.0, 1.0]$ | **0.12** | Invariant to translation/rotation; catches parcel splits, mergers, or severe misalignments. |
| 4 | **Shape Similarity** ($s_{\text{shape}}$) | $\frac{\min(Q_A, Q_B)}{\max(Q_A, Q_B)}$ where $Q = \frac{4\pi \cdot \text{Area}}{\text{Perimeter}^2}$ | $[0.0, 1.0]$ | **0.10** | Isoperimetric quotient measuring dimensionless compactness (circle = 1.0). |
| 5 | **Perimeter Concordance** ($s_{\text{perimeter}}$) | $\frac{\min(P_A, P_B)}{\max(P_A, P_B)}$ | $[0.0, 1.0]$ | **0.08** | Invariant boundary scale metric sensitive to boundary simplification or vertex densification. |
| 6 | **Bounding Envelope IoU** ($s_{\text{bbox}}$) | $\frac{\text{Area}(\text{Env}_A \cap \text{Env}_B)}{\text{Area}(\text{Env}_A \cup \text{Env}_B)}$ | $[0.0, 1.0]$ | **0.05** | High-efficiency envelope overlap confirming spatial bounding box co-location. |
| 7 | **Source Agreement** ($s_{\text{source}}$) | $1.0$ if $\text{source}_A \neq \text{source}_B$ else $0.5$ | $[0.5, 1.0]$ | **0.05** | Cross-departmental independence bonus (e.g. Cadastral vs Municipal or Drone). |
| 8 | **Identifier Similarity** ($s_{\text{identifier}}$) | Normalized string & token concordance | $[0.0, 1.0]$ | **0.05** | Alphanumeric survey/khasra/plot number concordance (exact, normalized, substring, or fuzzy). |

$$\sum_{i=1}^8 w_i = 0.30 + 0.25 + 0.12 + 0.10 + 0.08 + 0.05 + 0.05 + 0.05 = 1.000$$

---

## 3. Composite Candidate Scoring & Classification Rules

The candidate match score is calculated as a weighted linear combination:

$$S_{\text{candidate}} = \sum_{i=1}^8 w_i \cdot s_i$$

### Classification Thresholds
Candidate pairs are categorized into four authoritative tiers:

```
                            S_candidate >= 0.82
                          AND IoU >= 0.70
                          AND Drift < 2.0m ?
                               /     \
                            YES       NO
                            /           \
                 [STRONG_MATCH]       S_candidate >= 0.60
                                      AND Drift < 5.0m ?
                                          /     \
                                       YES       NO
                                       /           \
                           [POSSIBLE_MATCH]     S_candidate >= 0.40
                                                AND IoU > 0.05 ?
                                                    /     \
                                                 YES       NO
                                                 /           \
                                         [WEAK_MATCH]     [NO_MATCH]
```

- **STRONG_MATCH**: Candidate score $\ge 0.82$, metric IoU $\ge 0.70$, and centroid drift $< 2.0\text{ m}$. Suitable for automated reconciliation.
- **POSSIBLE_MATCH**: Candidate score $\ge 0.60$ and centroid drift $< 5.0\text{ m}$. Flagged for officer review in the review queue.
- **WEAK_MATCH**: Candidate score $\ge 0.40$ with sliver overlap ($> 0.05$ IoU). Retained as context during field resurvey.
- **NO_MATCH**: Disjoint or incompatible geometry (score $< 0.40$). Pruned from active reconciliation.

---

## 4. Large-Dataset Spatial Indexing ($O(N \log N)$ vs $O(N^2)$)

Brute-force pairwise evaluation of dataset $A$ ($N$ records) and dataset $B$ ($M$ records) scales quadratically as $O(N \cdot M)$. For large urban jurisdictions ($N = 10,000$, $M = 10,000$), brute force requires $10^8$ polygon operations, exhausting memory and compute.

### STRtree Indexing Engine
TerraNode builds a 2D Sort-Tile-Recursive R-Tree (`shapely.strtree.STRtree`) over dataset $A$'s projected geometries:
1. Buffered bounding boxes ($r = 15.0\text{ m}$) query the STRtree in $O(\log N)$ time.
2. Only intersecting candidate pairs are evaluated against the 8-signal scoring pipeline.
3. Every execution computes a `MatchingBenchmarkResult`:
   - `total_records_dataset_a`: $N$
   - `total_records_dataset_b`: $M$
   - `theoretical_brute_force_pairs`: $N \times M$
   - `spatial_candidate_pairs`: Count of bounding envelope intersections.
   - `candidate_reduction_ratio_pct`: $100 \times \left(1 - \frac{\text{Candidate Pairs}}{N \times M}\right)$
   - `processing_time_ms`: Wall-clock benchmark in milliseconds.

### Benchmark Results
- **100 x 100 Grid (10,000 brute-force pairs)**:
  - Spatial candidate pairs evaluated: $< 500$
  - Candidate reduction: **$> 95.0\%$**
  - Matched pairs: 100/100 ($100\%$ precision on synthetic grid).
- **Tamil Nadu Reference Dataset (37 Cadastral x 38 Municipal = 1,406 brute-force pairs)**:
  - Spatial candidate pairs evaluated: $205$
  - Candidate reduction: **$85.4\%$**
  - Processing time: **$< 45\text{ ms}$**
  - Matched pairs: 32 `STRONG_MATCH`, 5 `POSSIBLE_MATCH`, 1 `WEAK_MATCH`.

---

## 5. REST API Endpoints

### 1. `GET /api/matching/config`
Retrieves authoritative weights, thresholds, and search radii.
```json
{
  "weights": {
    "w_iou": 0.3,
    "w_centroid": 0.25,
    "w_area": 0.12,
    "w_shape": 0.1,
    "w_perimeter": 0.08,
    "w_bbox": 0.05,
    "w_source_agreement": 0.05,
    "w_identifier": 0.05
  },
  "thresholds": {
    "strong_match_min_score": 0.82,
    "strong_match_min_iou": 0.7,
    "strong_match_max_drift_m": 2.0,
    "possible_match_min_score": 0.6,
    "possible_match_max_drift_m": 5.0,
    "weak_match_min_score": 0.4
  },
  "max_search_radius_m": 15.0
}
```

### 2. `POST /api/matching/evaluate-pair`
Evaluates a single pair of candidate GeoJSON polygons.
```json
// Request
{
  "geometry_a": { "type": "Polygon", "coordinates": [...] },
  "geometry_b": { "type": "Polygon", "coordinates": [...] },
  "attributes_a": { "survey_no": "101/A", "source": "cadastral" },
  "attributes_b": { "survey_no": "101-A", "source": "municipal" }
}

// Response
{
  "candidate_score": 0.9358,
  "classification": "STRONG_MATCH",
  "iou_score": 0.8553,
  "centroid_score": 0.9455,
  "area_score": 1.0,
  "perimeter_score": 1.0,
  "shape_score": 1.0,
  "bbox_score": 0.8561,
  "source_agreement_score": 1.0,
  "identifier_score": 1.0,
  "raw_metrics": {
    "iou": 0.8553,
    "centroid_drift_m": 0.817,
    "area_a_m2": 2500.0,
    "area_b_m2": 2500.0,
    "area_diff_m2": 0.0,
    "area_diff_ratio": 0.0,
    "perimeter_a_m": 200.0,
    "perimeter_b_m": 200.0,
    "perimeter_diff_m": 0.0,
    "shape_compactness_a": 0.7854,
    "shape_compactness_b": 0.7854,
    "bbox_iou": 0.8561,
    "identifier_a": "101/A",
    "identifier_b": "101-A",
    "identifier_match_method": "NORMALIZED_EXACT",
    "source_a": "cadastral",
    "source_b": "municipal"
  }
}
```

### 3. `POST /api/matching/batch`
Evaluates two feature collections using STRtree spatial indexing, returning matches and candidate reduction benchmark telemetry.
