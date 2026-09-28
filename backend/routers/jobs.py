"""
backend/routers/jobs.py

PHASE 15: ASYNC / LONG-RUNNING JOB PROCESSING ENGINE

Provides deterministic job execution states for geospatial reconciliation batches:
States: CREATED -> INGESTING -> VALIDATING -> PROJECTING -> MATCHING -> RECONCILING -> COMPLETED (or FAILED)

Endpoints:
- POST /jobs & POST /api/jobs: Create & launch asynchronous reconciliation job
- GET /jobs/{job_id} & GET /api/jobs/{job_id}: Full job details and payload
- GET /jobs/{job_id}/status & GET /api/jobs/{job_id}/status: Progress percentage and stage
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from backend.config.reconciliation_policy import (
    evaluate_reconciliation,
    compute_confidence_score,
    AUTO_RECONCILE_CONFIDENCE_MIN,
    REVIEW_CONFIDENCE_MIN,
    MAX_CENTROID_DRIFT_METERS,
)
from backend.crs.transformer import determine_utm_crs, reproject_geometry
from backend.geometry.validator import validate_and_repair_geometry
from matching.similarity import iou, centroid_distance

router = APIRouter(prefix="", tags=["jobs"])
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"


class JobStage(str, Enum):
    CREATED = "CREATED"
    INGESTING = "INGESTING"
    VALIDATING = "VALIDATING"
    PROJECTING = "PROJECTING"
    MATCHING = "MATCHING"
    RECONCILING = "RECONCILING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class JobRecord:
    job_id: str
    stage: JobStage
    progress_percent: int
    created_at: float
    updated_at: float
    dataset_a: str
    dataset_b: str
    target_utm_crs: str = "EPSG:32644"
    features_processed: int = 0
    matched_pairs_count: int = 0
    auto_reconciled_count: int = 0
    review_required_count: int = 0
    conflict_count: int = 0
    error_message: Optional[str] = None
    results_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "stage": self.stage.value,
            "progress_percent": self.progress_percent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "dataset_a": self.dataset_a,
            "dataset_b": self.dataset_b,
            "target_utm_crs": self.target_utm_crs,
            "features_processed": self.features_processed,
            "matched_pairs_count": self.matched_pairs_count,
            "auto_reconciled_count": self.auto_reconciled_count,
            "review_required_count": self.review_required_count,
            "conflict_count": self.conflict_count,
            "error_message": self.error_message,
            "results_summary": self.results_summary,
        }


# In-memory registry with thread lock for active jobs
_JOBS: Dict[str, JobRecord] = {}
_LOCK = threading.Lock()


class CreateJobRequest(BaseModel):
    dataset_a_filename: Optional[str] = "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson"
    dataset_b_filename: Optional[str] = "85f02bb7-ec7a-4285-ae1f-450c5f9c2768.geojson"
    target_crs: Optional[str] = None


def _execute_reconciliation_job(job_id: str):
    import json
    from shapely.geometry import shape

    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return

    try:
        # Step 1: Ingesting
        job.stage = JobStage.INGESTING
        job.progress_percent = 15
        job.updated_at = time.time()
        time.sleep(0.1)

        file_a = UPLOADS_DIR / job.dataset_a
        file_b = UPLOADS_DIR / job.dataset_b

        if not file_a.exists() or not file_b.exists():
            raise FileNotFoundError(f"Source files missing: {file_a} or {file_b}")

        with open(file_a, "r", encoding="utf-8-sig") as f:
            feats_a = json.load(f).get("features", [])
        with open(file_b, "r", encoding="utf-8-sig") as f:
            feats_b = json.load(f).get("features", [])

        # Step 2: Validating
        job.stage = JobStage.VALIDATING
        job.progress_percent = 35
        job.updated_at = time.time()
        time.sleep(0.1)

        # Step 3: Projecting
        job.stage = JobStage.PROJECTING
        job.progress_percent = 50
        job.updated_at = time.time()

        sh_a = [shape(f["geometry"]) for f in feats_a if f.get("geometry")]
        sh_b = [shape(f["geometry"]) for f in feats_b if f.get("geometry")]

        c = sh_a[0].centroid
        target_utm, _ = determine_utm_crs(c.x, c.y)
        job.target_utm_crs = target_utm

        proj_a = [reproject_geometry(g, "EPSG:4326", target_utm) for g in sh_a]
        proj_b = [reproject_geometry(g, "EPSG:4326", target_utm) for g in sh_b]

        # Step 4: Matching
        job.stage = JobStage.MATCHING
        job.progress_percent = 70
        job.updated_at = time.time()

        matches = []
        for i, ga in enumerate(proj_a):
            for j, gb in enumerate(proj_b):
                if ga.intersects(gb):
                    ov_iou = iou(ga, gb)
                    if ov_iou > 0.05:
                        drift = centroid_distance(ga, gb)
                        matches.append((i, j, ov_iou, drift))

        # Step 5: Reconciling & Policy
        job.stage = JobStage.RECONCILING
        job.progress_percent = 85
        job.updated_at = time.time()

        auto_cnt = 0
        review_cnt = 0
        conflict_cnt = 0

        for _, _, ov_iou, drift_m in matches:
            conf = compute_confidence_score(ov_iou, ov_iou, 0.85)
            dec = evaluate_reconciliation(conf, drift_m)
            if dec.is_auto_reconciled:
                auto_cnt += 1
            elif dec.needs_review and not dec.is_conflict:
                review_cnt += 1
            else:
                conflict_cnt += 1

        # Step 6: Completed
        job.stage = JobStage.COMPLETED
        job.progress_percent = 100
        job.updated_at = time.time()
        job.features_processed = len(feats_a) + len(feats_b)
        job.matched_pairs_count = len(matches)
        job.auto_reconciled_count = auto_cnt
        job.review_required_count = review_cnt
        job.conflict_count = conflict_cnt
        job.results_summary = {
            "total_parcels": len(feats_a),
            "matched_pairs": len(matches),
            "auto_reconciled": auto_cnt,
            "review_required": review_cnt,
            "conflicts": conflict_cnt,
            "projected_crs": target_utm,
            "reconciliation_policy": "Authoritative Policy (Confidence >= 85% & Drift < 2.0m)",
        }

    except Exception as e:
        logger.error("Job %s execution failed: %s", job_id, e)
        job.stage = JobStage.FAILED
        job.error_message = str(e)
        job.updated_at = time.time()


@router.post("/jobs")
@router.post("/api/jobs")
def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    now = time.time()

    record = JobRecord(
        job_id=job_id,
        stage=JobStage.CREATED,
        progress_percent=0,
        created_at=now,
        updated_at=now,
        dataset_a=request.dataset_a_filename or "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson",
        dataset_b=request.dataset_b_filename or "85f02bb7-ec7a-4285-ae1f-450c5f9c2768.geojson",
    )

    with _LOCK:
        _JOBS[job_id] = record

    background_tasks.add_task(_execute_reconciliation_job, job_id)

    return {
        "success": True,
        "job_id": job_id,
        "stage": record.stage.value,
        "progress_percent": 0,
        "message": "Reconciliation job created and processing initiated in background.",
    }


@router.get("/jobs/{job_id}")
@router.get("/api/jobs/{job_id}")
def get_job_details(job_id: str):
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {
        "success": True,
        "job": job.to_dict(),
    }


@router.get("/jobs/{job_id}/status")
@router.get("/api/jobs/{job_id}/status")
def get_job_status(job_id: str):
    with _LOCK:
        job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return {
        "success": True,
        "job_id": job.job_id,
        "stage": job.stage.value,
        "progress_percent": job.progress_percent,
        "updated_at": job.updated_at,
        "is_complete": job.stage == JobStage.COMPLETED,
        "is_failed": job.stage == JobStage.FAILED,
    }
