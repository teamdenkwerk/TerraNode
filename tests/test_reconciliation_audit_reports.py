"""
tests/test_reconciliation_audit_reports.py

Tests for TERRANODE Reconciliation Audit Center endpoints:
- Summary report data structure
- Active dataset scoping and isolation (Bengaluru vs Chennai)
- 4 primary visualization data structures
- Audit PDF generation (valid PDF stream)
- Reconciled GeoJSON, CSV, Evidence JSON, and Audit Log exports
"""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_reports_summary_structure():
    """Verifies that the report summary returns all 8 required sections with real metrics."""
    res = client.get("/api/reports/summary")
    assert res.status_code == 200
    data = res.json()

    # Core metadata
    assert "dataset_id" in data
    assert "city" in data
    assert "aoi" in data
    assert "status" in data

    # 1. Reconciliation status (for donut chart)
    rec = data["reconciliation_status"]
    assert rec["total"] > 0
    assert rec["verified"] + rec["review"] + rec["conflict"] == rec["total"]
    assert "overall_confidence" in rec

    # 2. Source contribution (for vertical bar chart)
    srcs = data["source_contribution"]
    assert len(srcs) >= 4
    for s in srcs:
        assert "source_name" in s
        assert "count" in s
        assert s["count"] > 0

    # 3. Spatial conflict breakdown (for horizontal bar chart)
    c_break = data["spatial_conflict_breakdown"]
    assert isinstance(c_break, list)

    # 4. Spatial quality (for dot benchmark visualization)
    sq = data["spatial_quality"]
    assert "iou" in sq
    assert "boundary_agreement" in sq
    assert "ground_truth_agreement" in sq
    assert "verification_confidence" in sq
    assert sq["iou"]["threshold"] == 0.85

    # 5. Evidence coverage
    ec = data["evidence_coverage"]
    assert len(ec) >= 6

    # 6. Pipeline stages
    stages = data["pipeline_stages"]
    assert len(stages) == 6

    # 7. Audit history
    ah = data["audit_history"]
    assert len(ah) >= 4

    # 8. Conflict ledger
    ledger = data["conflict_ledger"]
    assert len(ledger) == rec["total"]


def test_dataset_isolation_bengaluru_vs_chennai():
    """Verifies strict isolation: Chennai report must not contain Bengaluru data and vice-versa."""
    blr_res = client.get("/api/datasets/bengaluru-ward112/reports/summary")
    assert blr_res.status_code == 200
    blr_data = blr_res.json()
    assert blr_data["city"] == "Bengaluru"
    assert "Domlur" in blr_data["aoi"] or "112" in blr_data["aoi"]

    maa_res = client.get("/api/datasets/chennai-tnagar/reports/summary")
    assert maa_res.status_code == 200
    maa_data = maa_res.json()
    assert maa_data["city"] == "Chennai"
    assert "T. Nagar" in maa_data["aoi"]

    # Verify parcel prefixes are isolated
    blr_ids = [p["parcel_id"] for p in blr_data["conflict_ledger"]]
    maa_ids = [p["parcel_id"] for p in maa_data["conflict_ledger"]]

    for pid in blr_ids:
        assert "MAA" not in pid
    for pid in maa_ids:
        assert "BLR" not in pid


def test_audit_pdf_generation():
    """Verifies the backend generates a valid, printable ReportLab PDF binary."""
    res = client.get("/api/reports/audit-pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    # PDF magic number header
    assert res.content.startswith(b"%PDF")
    assert len(res.content) > 5000  # Multi-page professional document


def test_audit_pdf_generation_for_chennai():
    """Verifies Chennai dataset generates isolated Chennai PDF report."""
    res = client.get("/api/datasets/chennai-tnagar/reports/audit-pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_export_endpoints():
    """Verifies GeoJSON, CSV, Evidence JSON, and Audit Log export endpoints."""
    # GeoJSON
    res_geo = client.get("/api/reports/geojson")
    assert res_geo.status_code == 200
    assert "application/geo+json" in res_geo.headers["content-type"]
    geo_data = res_geo.json()
    assert geo_data["type"] == "FeatureCollection"
    assert len(geo_data["features"]) > 0

    # CSV
    res_csv = client.get("/api/reports/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Parcel ID,Survey Number,Status" in res_csv.text

    # Evidence JSON
    res_ev = client.get("/api/reports/evidence")
    assert res_ev.status_code == 200
    assert res_ev.json()["report_type"] == "TERRANODE_UNIFIED_EVIDENCE_PACKAGE"

    # Audit Log
    res_log = client.get("/api/reports/audit-log")
    assert res_log.status_code == 200
    assert "audit_events" in res_log.json()
