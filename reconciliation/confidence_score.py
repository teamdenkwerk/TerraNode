"""
reconciliation/confidence_score.py

confidence = w_match * match_score + w_agreement * inter_source_agreement
           + w_extraction * ai_extraction_confidence

This restores a regression from an earlier draft, which dropped the
matching engine's own score from the confidence formula entirely and
substituted a source-count bonus (more sources agreeing = higher
confidence, regardless of how well they actually matched). That let a
weak three-source match outscore a near-perfect two-source match — the
formula here always includes real match quality (avg_match_score) as the
largest-weighted term, per the original design.

Agreement is derived from avg_iou_agreement (the same geometric IoU
metric used throughout matching/similarity.py), not a separate
area-percentage metric.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from config import (
    CONFIDENCE_WEIGHT_MATCH, CONFIDENCE_WEIGHT_AGREEMENT, CONFIDENCE_WEIGHT_EXTRACTION,
    CONFIDENCE_REVIEW_THRESHOLD, UNMATCHED_MATCH_SCORE_PROXY, UNMATCHED_AGREEMENT,
    NO_EXTRACTION_CONFIDENCE_DEFAULT, MATCH_SRID,
)
from db.connection import get_connection
from reconciliation.resolve_conflicts import ReconciledEntity

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfidenceWeights:
    w_match: float = CONFIDENCE_WEIGHT_MATCH
    w_agreement: float = CONFIDENCE_WEIGHT_AGREEMENT
    w_extraction: float = CONFIDENCE_WEIGHT_EXTRACTION

    def __post_init__(self):
        total = self.w_match + self.w_agreement + self.w_extraction
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"ConfidenceWeights must sum to 1.0, got {total}")


DEFAULT_WEIGHTS = ConfidenceWeights()


def _extraction_confidence(entity: ReconciledEntity) -> float:
    value = entity.attrs.get("extraction_confidence")
    return float(value) if value is not None else NO_EXTRACTION_CONFIDENCE_DEFAULT


from backend.config.reconciliation_policy import (
    evaluate_reconciliation,
    compute_confidence_score,
    ReconciliationStatus,
    DecisionResult,
)


@dataclass
class ScoredEntity:
    entity: ReconciledEntity
    confidence: float
    centroid_drift: float
    needs_review: bool
    decision: str
    decision_reason: str
    match_score: Optional[float] = None
    iou_average: Optional[float] = None
    extraction_score: float = NO_EXTRACTION_CONFIDENCE_DEFAULT

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity.entity_id,
            "confidence": self.confidence,
            "centroid_drift": self.centroid_drift,
            "needs_review": self.needs_review,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "match_score": self.match_score,
            "iou_average": self.iou_average,
            "extraction_score": self.extraction_score,
            "source_count": self.entity.source_count,
            "sources": self.entity.sources,
        }


def compute_confidence(entity: ReconciledEntity, weights: ConfidenceWeights = DEFAULT_WEIGHTS) -> float:
    match_score = entity.avg_match_score if entity.avg_match_score is not None else UNMATCHED_MATCH_SCORE_PROXY
    agreement = entity.avg_iou_agreement if entity.avg_iou_agreement is not None else UNMATCHED_AGREEMENT
    extraction = _extraction_confidence(entity)

    # Use authoritative formula: 0.50 * match + 0.35 * agreement + 0.15 * extraction
    confidence = compute_confidence_score(
        match_score=match_score,
        iou_agreement=agreement,
        extraction_score=extraction,
    )

    if entity.duplicate_source_warning:
        confidence = min(confidence, CONFIDENCE_REVIEW_THRESHOLD - 0.01)

    return round(min(max(confidence, 0.0), 1.0), 4)


def score_entities(
    entities: list[ReconciledEntity],
    review_threshold: float = CONFIDENCE_REVIEW_THRESHOLD,
    weights: ConfidenceWeights = DEFAULT_WEIGHTS,
) -> list[ScoredEntity]:
    scored = []
    for entity in entities:
        confidence = compute_confidence(entity, weights=weights)
        drift = getattr(entity, "centroid_drift_m", 0.0)
        eval_res: DecisionResult = evaluate_reconciliation(
            confidence=confidence,
            centroid_drift_meters=drift,
            duplicate_source_collision=entity.duplicate_source_warning,
        )

        match_score = entity.avg_match_score
        iou_avg = entity.avg_iou_agreement
        ext_score = _extraction_confidence(entity)

        scored.append(
            ScoredEntity(
                entity=entity,
                confidence=confidence,
                centroid_drift=drift,
                needs_review=eval_res.needs_review,
                decision=eval_res.status.value,
                decision_reason=eval_res.reason,
                match_score=match_score,
                iou_average=iou_avg,
                extraction_score=ext_score,
            )
        )

    n_review = sum(1 for s in scored if s.needs_review)
    n_conflict = sum(1 for s in scored if s.decision == ReconciliationStatus.CONFLICT.value)
    n_auto = sum(1 for s in scored if s.decision == ReconciliationStatus.AUTO_RECONCILED.value)

    logger.info(
        "scored %d entities: %d auto-reconciled, %d review-required, %d conflicts",
        len(scored), n_auto, n_review - n_conflict, n_conflict,
    )
    return scored


# ---------------------------------------------------------------------------
# Writing to PostGIS (canonical_entities)
# ---------------------------------------------------------------------------

def write_scored_entities(scored: list[ScoredEntity], tile_id: str | None = None) -> None:
    if not scored:
        logger.info("no scored entities to write")
        return

    rows = [
        (
            s.entity.entity_id,
            s.entity.geom.wkt,
            s.entity.geom.area,
            s.entity.source_count,
            s.entity.sources,
            s.entity.member_feature_ids,
            s.entity.avg_match_score,
            s.entity.avg_iou_agreement,
            s.confidence,
            s.needs_review,
            tile_id,
        )
        for s in scored
    ]

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                f"""
                INSERT INTO canonical_entities
                    (canonical_uid, geom, area_m2, source_count, sources,
                     member_feature_ids, avg_match_score, avg_iou_agreement,
                     confidence_score, needs_review, tile_id)
                VALUES (%s, ST_GeomFromText(%s, {MATCH_SRID}), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (canonical_uid) DO UPDATE SET
                    confidence_score = EXCLUDED.confidence_score,
                    needs_review = EXCLUDED.needs_review
                """,
                rows,
            )
        conn.commit()
    logger.info("wrote %d canonical entities", len(rows))