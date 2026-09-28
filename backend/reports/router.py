"""
backend/reports/router.py

FastAPI router for TERRANODE Reconciliation Audit Center.
Provides endpoints for report summaries, authority-grade PDF export,
reconciled GeoJSON export, CSV summaries, evidence JSON, and audit logs.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from backend.dataset_manager import get_active_dataset_id, get_dataset
from backend.reports.summary_service import compute_report_summary
from backend.reports.pdf_generator import generate_audit_pdf

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


@router.get("/api/reports/summary")
@router.get("/api/datasets/{dataset_id}/reports/summary")
def get_dataset_report_summary(dataset_id: Optional[str] = None):
    """
    GET /api/reports/summary or /api/datasets/{dataset_id}/reports/summary

    Returns complete structured summary for the Reconciliation Audit Center,
    including reconciliation status, source contributions, spatial conflict breakdown,
    quality benchmarks, evidence coverage, pipeline stages, audit history, and conflict ledger.
    """
    target_id = dataset_id or get_active_dataset_id()
    try:
        return compute_report_summary(target_id)
    except Exception as e:
        logger.error("Error computing report summary for '%s': %s", target_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to generate report summary: {str(e)}")


@router.get("/api/reports/audit-pdf")
@router.post("/api/reports/audit-pdf")
@router.get("/api/datasets/{dataset_id}/reports/audit-pdf")
@router.post("/api/datasets/{dataset_id}/reports/audit-pdf")
def get_dataset_audit_pdf(dataset_id: Optional[str] = None):
    """
    GET/POST /api/reports/audit-pdf or /api/datasets/{dataset_id}/reports/audit-pdf

    Generates and returns the official 11-section printable TERRANODE Reconciliation Audit Report PDF.
    """
    target_id = dataset_id or get_active_dataset_id()
    ds = get_dataset(target_id)
    city_name = ds.get("city", "Terranode") if ds else "Terranode"
    clean_city = city_name.replace(" ", "_")

    try:
        pdf_bytes = generate_audit_pdf(target_id)
        filename = f"TERRANODE_Reconciliation_Audit_{clean_city}_{target_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Report-Dataset": target_id,
            },
        )
    except Exception as e:
        logger.error("Error generating audit PDF for '%s': %s", target_id, e)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/api/reports/geojson")
@router.get("/api/datasets/{dataset_id}/reports/geojson")
def get_dataset_reconciled_geojson(dataset_id: Optional[str] = None):
    """
    Exports the reconciled spatial geometries for the active dataset as standard GeoJSON.
    """
    target_id = dataset_id or get_active_dataset_id()
    ds = get_dataset(target_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    entities = ds.get("entities", [])
    features = []
    for e in entities:
        props = dict(e.get("properties", {}))
        props["canonical_uid"] = e.get("canonical_uid")
        props["area_m2"] = e.get("area_m2")
        props["confidence_score"] = e.get("confidence_score")
        props["needs_review"] = e.get("needs_review")
        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": e.get("geometry", {}),
        })

    geojson_payload = {
        "type": "FeatureCollection",
        "name": f"TERRANODE_{ds.get('city', 'Area')}_{ds.get('aoi', 'AOI')}_Reconciled",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}
        },
        "features": features,
    }

    return Response(
        content=json.dumps(geojson_payload, indent=2),
        media_type="application/geo+json",
        headers={
            "Content-Disposition": f'attachment; filename="TERRANODE_{target_id}_Reconciled.geojson"',
        },
    )


@router.get("/api/reports/csv")
@router.get("/api/datasets/{dataset_id}/reports/csv")
def get_dataset_csv_summary(dataset_id: Optional[str] = None):
    """
    Exports the tabular parcel ledger as a CSV summary.
    """
    summary = compute_report_summary(dataset_id)
    ledger = summary.get("conflict_ledger", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Parcel ID",
        "Survey Number",
        "Status",
        "Conflict Type",
        "Confidence (%)",
        "IoU",
        "Boundary Drift (m)",
        "Area (m2)",
        "Land Use",
        "Contributing Sources",
    ])

    for p in ledger:
        writer.writerow([
            p["parcel_id"],
            p["survey_number"],
            p["status"],
            p["conflict_type"],
            p["confidence_pct"],
            p["iou"],
            p["boundary_drift_m"],
            p["area_m2"],
            p["land_use"],
            p["sources_text"],
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="TERRANODE_{summary["dataset_id"]}_Parcels_Summary.csv"',
        },
    )


@router.get("/api/reports/evidence")
@router.get("/api/datasets/{dataset_id}/reports/evidence")
def get_dataset_evidence_json(dataset_id: Optional[str] = None):
    """
    Exports machine-readable unified evidence package for the dataset.
    """
    summary = compute_report_summary(dataset_id)
    payload = {
        "report_type": "TERRANODE_UNIFIED_EVIDENCE_PACKAGE",
        "specification": "2026.4-LOD3",
        "dataset_id": summary["dataset_id"],
        "dataset_name": summary["name"],
        "city": summary["city"],
        "aoi": summary["aoi"],
        "generated_at": summary["last_processed"],
        "reconciliation_status": summary["reconciliation_status"],
        "source_contribution": summary["source_contribution"],
        "spatial_quality": summary["spatial_quality"],
        "evidence_coverage": summary["evidence_coverage"],
        "pipeline_stages": summary["pipeline_stages"],
        "audit_history": summary["audit_history"],
        "parcels_evaluated": len(summary["conflict_ledger"]),
    }

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="TERRANODE_{summary["dataset_id"]}_Evidence_Package.json"',
        },
    )


@router.get("/api/reports/audit-log")
@router.get("/api/datasets/{dataset_id}/reports/audit-log")
def get_dataset_audit_log_json(dataset_id: Optional[str] = None):
    """
    Exports complete immutable audit trail of all processing lifecycle events.
    """
    summary = compute_report_summary(dataset_id)
    log_payload = {
        "system": "TERRANODE Autonomous Reconciliation Audit Core",
        "dataset_id": summary["dataset_id"],
        "city": summary["city"],
        "audit_events": summary["audit_history"],
        "conflict_ledger_summary": {
            "total_parcels": summary["reconciliation_status"]["total"],
            "verified": summary["reconciliation_status"]["verified"],
            "review": summary["reconciliation_status"]["review"],
            "conflict": summary["reconciliation_status"]["conflict"],
        },
    }

    return Response(
        content=json.dumps(log_payload, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="TERRANODE_{summary["dataset_id"]}_Audit_Log.json"',
        },
    )
