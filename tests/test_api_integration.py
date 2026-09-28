"""
tests/test_api_integration.py

INTEGRATION TESTS: FASTAPI PRODUCTION ENDPOINTS

Tests:
- GET /health
- GET /health/ready
- GET /api/policy
- GET /validation/production
- POST /api/jobs and GET /api/jobs/{id}/status
- GET /api/audit/{id}
- GET /api/certificates/{id}
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "service" in data


def test_health_ready_endpoint():
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert "ready" in data
    assert "subsystems" in data
    assert "api" in data["subsystems"]
    assert "database" in data["subsystems"]
    assert "storage" in data["subsystems"]
    assert "ml_engine" in data["subsystems"]


def test_authoritative_policy_endpoint():
    res = client.get("/api/policy")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    rules = data["rules"]
    assert "Confidence >= 85%" in rules["auto_reconciled"]
    assert "Centroid Drift < 2.0m" in rules["auto_reconciled"]
    assert "70% <= Confidence < 85%" in rules["review_required"]
    assert "Confidence < 70%" in rules["conflict"]
    assert "Centroid Drift >= 2.0m" in rules["conflict"]


def test_production_validation_dashboard_endpoint():
    res = client.get("/validation/production")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "data_quality" in data
    assert "reconciliation_quality" in data
    assert "geometric_quality" in data
    assert "ground_truth_validation" in data
    assert "model_validation" in data
    # Verify strict honesty of ML model validation
    assert "insufficient" in data["model_validation"]["status_message"].lower()


def test_jobs_state_machine_endpoint():
    # 1. Create job
    create_res = client.post("/api/jobs", json={
        "dataset_a_filename": "d61deb54-ea55-4bbc-a888-2d57a018fee3.geojson",
        "dataset_b_filename": "85f02bb7-ec7a-4285-ae1f-450c5f9c2768.geojson",
    })
    assert create_res.status_code == 200
    job_id = create_res.json()["job_id"]
    assert job_id.startswith("job-")

    # 2. Check status
    status_res = client.get(f"/api/jobs/{job_id}/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["job_id"] == job_id
    assert "progress_percent" in status_data


def test_parcel_audit_trail_endpoint():
    res = client.get("/api/audit/CAD-01-001")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    record = data["audit_record"]
    assert record["decision"] == "AUTO-RECONCILED"
    assert "who" in record
    assert "what" in record
    assert "why" in record


def test_reconciliation_certificate_endpoint():
    res = client.get("/api/certificates/CAD-01-001")
    assert res.status_code == 200
    cert = res.json()
    assert "CERT-TRN-" in cert["certificate_id"]
    assert cert["spatial_metrology"]["max_drift_threshold_m"] == 2.0
    assert cert["reconciliation_decision"]["status"] == "AUTO-RECONCILED"
