# TERRANODE Reconciliation Method & Mathematical Foundation

## 1. Authoritative Reconciliation Policy

All modules in TERRANODE adhere strictly to the centralized policy in `backend/config/reconciliation_policy.py`.

### Decision Rules:
1. **AUTO-RECONCILED**:
   $$\text{Confidence} \ge 85\% \quad \text{AND} \quad \text{Centroid Drift} < 2.0\text{ meters}$$
2. **REVIEW REQUIRED**:
   $$70\% \le \text{Confidence} < 85\% \quad \text{AND} \quad \text{Centroid Drift} < 2.0\text{ meters}$$
3. **CONFLICT**:
   $$\text{Confidence} < 70\% \quad \text{OR} \quad \text{Centroid Drift} \ge 2.0\text{ meters}$$

---

## 2. Confidence Formula

$$\text{Confidence} = 0.50 \times \text{Match Score} + 0.35 \times \text{IoU Agreement} + 0.15 \times \text{Extraction Score}$$

Where:
- $\text{Match Score} = 0.50 \times \text{IoU} + 0.30 \times (1 - \text{norm\_drift}) + 0.20 \times \text{Attribute Similarity}$.
- $\text{IoU Agreement} = \frac{\text{Area}(A \cap B)}{\text{Area}(A \cup B)}$ computed in projected metric CRS.
- $\text{Extraction Score}$: Model confidence for AI segmentations (or default 0.85 for verified survey layers).

---

## 3. Boundary Consensus & Provenance

When multiple sources match a real-world entity, the canonical footprint is synthesized via geometric consensus:
- **Default Strategy**: Geometric `unary_union` preserving the combined extents of agreeing authorities.
- **Conservative Strategy**: Geometric `intersection` requiring strict mutual agreement.
- **Provenance Logging**: Records contributing source IDs, area variance, and centroid drift to justify: *"Why did TerraNode choose this boundary?"*
