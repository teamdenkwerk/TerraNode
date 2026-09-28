"""
verification/evaluate_matching.py

Phase 1 — evaluates the PRODUCTION matcher (matching/match_entities.py,
via the match_edges it already wrote during the pipeline run) against the
stricter reference oracle from build_reference_oracle.py.

Computes precision, recall, F1, and average IoU on agreed matches — the
numbers to say out loud in the demo instead of just showing output.

Usage (after pipeline/run_offline_batch.py has populated raw_features +
match_edges):
    python -m verification.evaluate_matching
"""

import sys
import csv
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import SCRATCH_DIR
from db.connection import get_connection
from matching.similarity import iou
from verification.build_reference_oracle import load_features_by_source, build_oracle_matches

RESULTS_PATH = SCRATCH_DIR / "verification_results.csv"


def load_predicted_pairs(source_a: str, source_b: str) -> set[tuple[int, int]]:
    query = """
        SELECT me.feature_id_a, me.feature_id_b, fa.source AS source_a_actual, fb.source AS source_b_actual
        FROM match_edges me
        JOIN raw_features fa ON fa.id = me.feature_id_a
        JOIN raw_features fb ON fb.id = me.feature_id_b
        WHERE (fa.source = %s AND fb.source = %s)
           OR (fa.source = %s AND fb.source = %s)
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (source_a, source_b, source_b, source_a))
            rows = cur.fetchall()

    pairs = set()
    for r in rows:
        if r["source_a_actual"] == source_a:
            pairs.add((r["feature_id_a"], r["feature_id_b"]))
        else:
            pairs.add((r["feature_id_b"], r["feature_id_a"]))
    return pairs


def compute_precision_recall_f1(predicted: set, oracle: set) -> dict:
    tp = len(predicted & oracle)
    fp = len(predicted - oracle)
    fn = len(oracle - predicted)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": round(precision, 3), "recall": round(recall, 3), "f1_score": round(f1, 3),
    }


def compute_avg_iou_on_true_positives(
    predicted: set, oracle: set, features_a: list[dict], features_b: list[dict],
) -> float:
    """For pairs both the oracle and the production matcher agree on, what's
    the actual geometric overlap quality? Higher = tighter, more accurate matches."""
    tp_pairs = predicted & oracle
    if not tp_pairs:
        return 0.0

    a_by_id = {f["id"]: f for f in features_a}
    b_by_id = {f["id"]: f for f in features_b}

    ious = [iou(a_by_id[id_a]["geometry"], b_by_id[id_b]["geometry"]) for id_a, id_b in tp_pairs
            if id_a in a_by_id and id_b in b_by_id]
    return round(sum(ious) / len(ious), 3) if ious else 0.0


def run_evaluation(source_a: str = "osm", source_b: str = "google_open_buildings") -> dict:
    print(f"=== Evaluating matching: {source_a} <-> {source_b} ===\n")

    oracle = build_oracle_matches(source_a, source_b)
    predicted = load_predicted_pairs(source_a, source_b)

    metrics = compute_precision_recall_f1(predicted, oracle)

    features_a = load_features_by_source(source_a)
    features_b = load_features_by_source(source_b)
    metrics["avg_iou_on_agreed_matches"] = compute_avg_iou_on_true_positives(
        predicted, oracle, features_a, features_b
    )

    print("\n--- Results ---")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    with open(RESULTS_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in metrics.items():
            writer.writerow([k, v])
    print(f"\nSaved results to {RESULTS_PATH}")

    return metrics


if __name__ == "__main__":
    run_evaluation()