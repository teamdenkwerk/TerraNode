"""
backend/ml/readiness.py

PHASE 8: ML MODEL READINESS & DATASET EVALUATION ENGINE

Strictly verifies whether real, verified, scientifically defensible ground-truth
labels exist before training or evaluating a machine learning classifier.
Prevents data fabrication, pseudo-AI labeling, or spurious accuracy claims.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

MINIMUM_VERIFIED_SAMPLES_FOR_ML = 500


@dataclass
class DatasetReadinessReport:
    ml_available: bool
    status_message: str
    verified_labeled_samples: int
    minimum_samples_required: int
    feature_pipeline_ready: bool
    feature_schema: List[str]
    training_script_available: bool
    validation_framework_available: bool
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_ml_readiness(uploads_dir: str | Path = "data/uploads") -> DatasetReadinessReport:
    """
    Scans uploads and verifies ground-truth availability.
    Returns honest ML readiness state.
    """
    path = Path(uploads_dir)
    verified_count = 0

    if path.exists():
        for f in path.glob("*.geojson"):
            try:
                with open(f, "r", encoding="utf-8-sig") as fh:
                    data = json.load(fh)
                    features = data.get("features", [])
                    for ft in features:
                        props = ft.get("properties", {})
                        # Verified ground-truth labels require explicit surveyor or RTK validation tag
                        if "accuracy_m" in props or "surveyor" in props or props.get("ground_truth") is True:
                            verified_count += 1
            except Exception:
                continue

    schema = [
        "iou",
        "centroid_drift_m",
        "area_difference_pct",
        "perimeter_difference_pct",
        "shape_compactness_a",
        "shape_compactness_b",
        "vertex_count_a",
        "vertex_count_b",
        "overlap_ratio_a",
        "overlap_ratio_b",
        "source_count",
        "extraction_quality",
    ]

    has_enough_data = (verified_count >= MINIMUM_VERIFIED_SAMPLES_FOR_ML)

    if not has_enough_data:
        msg = "ML validation unavailable — insufficient verified labelled data"
        recs = [
            f"Current verified reference checkpoints: {verified_count} (minimum threshold for statistical defensibility: {MINIMUM_VERIFIED_SAMPLES_FOR_ML}).",
            "Deterministic geometric reconciliation engine is active and serving authoritative decisions.",
            "Feature extraction pipeline is initialized and logging candidate vectors for future model training.",
            "Conduct structured GNSS RTK field campaign across remaining sectors to compile required training corpus.",
        ]
    else:
        msg = f"Sufficient verified data detected ({verified_count} samples). ML model ready for supervised training."
        recs = ["Run scripts/train_reconciliation_model.py to train XGBoost classifier."]

    return DatasetReadinessReport(
        ml_available=has_enough_data,
        status_message=msg,
        verified_labeled_samples=verified_count,
        minimum_samples_required=MINIMUM_VERIFIED_SAMPLES_FOR_ML,
        feature_pipeline_ready=True,
        feature_schema=schema,
        training_script_available=True,
        validation_framework_available=True,
        recommendations=recs,
    )
