"""
tests/test_conflict_state_machine.py

Unit tests for TERRANODE FEATURE 05 — CONFLICT LIFECYCLE STATE MACHINE

Tests:
1. Valid transitions along the standard resolution path:
   DETECTED -> UNDER_REVIEW -> SURVEY_REQUIRED -> SURVEY_RECEIVED -> RECONCILIATION_PENDING -> RESOLVED -> APPROVED -> REOPENED -> UNDER_REVIEW
2. Alternative valid transitions:
   UNDER_REVIEW -> RESOLVED
   UNDER_REVIEW -> REJECTED
   REJECTED -> REOPENED
   SURVEY_REQUIRED -> UNDER_REVIEW
   SURVEY_RECEIVED -> UNDER_REVIEW
   RECONCILIATION_PENDING -> UNDER_REVIEW
   RESOLVED -> UNDER_REVIEW
3. Invalid transitions that must raise InvalidTransitionError:
   DETECTED -> APPROVED, DETECTED -> RESOLVED, UNDER_REVIEW -> APPROVED,
   SURVEY_REQUIRED -> APPROVED, SURVEY_RECEIVED -> APPROVED,
   RECONCILIATION_PENDING -> APPROVED, APPROVED -> UNDER_REVIEW,
   REJECTED -> APPROVED, etc.
4. Mandatory audit trail fields: parcel_uuid, previous_state, new_state, actor, timestamp, reason, evidence.
5. FastAPI REST API endpoints:
   GET /api/conflicts
   GET /api/conflicts/{id}
   POST /api/conflicts/{id}/transition (200 for valid, 400 for invalid, 404 for unknown)
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.conflicts.state_machine import (
    ConflictNotFoundError,
    ConflictRecord,
    ConflictState,
    ConflictStateMachineService,
    CreateConflictRequest,
    InvalidTransitionError,
    TransitionRequest,
    VALID_TRANSITIONS,
)


@pytest.fixture
def clean_conflict_service(tmp_path):
    """Provides an isolated ConflictStateMachineService using a temporary directory."""
    ledger_file = tmp_path / "test_conflicts_ledger.json"
    return ConflictStateMachineService(ledger_path=ledger_file, auto_seed=False)


# ---------------------------------------------------------------------------
# 1. VALID TRANSITION TESTS
# ---------------------------------------------------------------------------

def test_full_standard_lifecycle(clean_conflict_service):
    """Verifies complete chronological path from DETECTED to REOPENED to UNDER_REVIEW."""
    svc = clean_conflict_service
    c = svc.create_conflict(
        CreateConflictRequest(
            parcel_uuid="TEST-UUID-001",
            source_parcel_id="BLR-TEST-1",
            title="Boundary Overlap Discrepancy",
            severity="HIGH",
            discrepancy_metrics={"centroid_drift_m": 2.5},
        )
    )
    assert c.current_state == ConflictState.DETECTED
    assert c.allowed_transitions == ["UNDER_REVIEW"]

    # 1. DETECTED -> UNDER_REVIEW
    c1 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.UNDER_REVIEW,
            actor="Officer A. Sharma (#402)",
            reason="Assigned to desk review for inspection",
            evidence={"assignment_ticket": "TCK-101"},
        ),
    )
    assert c1.current_state == ConflictState.UNDER_REVIEW
    assert sorted(c1.allowed_transitions) == ["REJECTED", "RESOLVED", "SURVEY_REQUIRED"]

    # 2. UNDER_REVIEW -> SURVEY_REQUIRED
    c2 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.SURVEY_REQUIRED,
            actor="Officer A. Sharma (#402)",
            reason="Ambiguous setback requires physical ground survey",
            evidence={"dispatch_code": "SURV-REQ-99"},
        ),
    )
    assert c2.current_state == ConflictState.SURVEY_REQUIRED
    assert sorted(c2.allowed_transitions) == ["SURVEY_RECEIVED", "UNDER_REVIEW"]

    # 3. SURVEY_REQUIRED -> SURVEY_RECEIVED
    c3 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.SURVEY_RECEIVED,
            actor="Rover Field Team (Badge #12)",
            reason="RTK GNSS rover coordinates collected and uploaded",
            evidence={"gnss_fix": "RTK_FIXED", "accuracy_cm": 1.2},
        ),
    )
    assert c3.current_state == ConflictState.SURVEY_RECEIVED
    assert sorted(c3.allowed_transitions) == ["RECONCILIATION_PENDING", "UNDER_REVIEW"]

    # 4. SURVEY_RECEIVED -> RECONCILIATION_PENDING
    c4 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.RECONCILIATION_PENDING,
            actor="Queue Worker",
            reason="Submitted for automated consensus calculation",
            evidence={"queue_id": "Q-88"},
        ),
    )
    assert c4.current_state == ConflictState.RECONCILIATION_PENDING
    assert sorted(c4.allowed_transitions) == ["RESOLVED", "UNDER_REVIEW"]

    # 5. RECONCILIATION_PENDING -> RESOLVED
    c5 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.RESOLVED,
            actor="TerraNode Consensus Engine",
            reason="Consensus geometry computed with IoU 96.5% and drift 0.18m",
            evidence={"iou": 0.965, "drift_m": 0.18},
        ),
    )
    assert c5.current_state == ConflictState.RESOLVED
    assert sorted(c5.allowed_transitions) == ["APPROVED", "UNDER_REVIEW"]

    # 6. RESOLVED -> APPROVED
    c6 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.APPROVED,
            actor="Senior Surveyor Ramesh K. (#401)",
            reason="Official approval and sign-off on consensus boundary",
            evidence={"seal_id": "SEAL-2026-44"},
        ),
    )
    assert c6.current_state == ConflictState.APPROVED
    assert sorted(c6.allowed_transitions) == ["REOPENED"]

    # 7. APPROVED -> REOPENED
    c7 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.REOPENED,
            actor="District Magistrate Court Order",
            reason="Land title dispute appeal filed by adjacent plot owner",
            evidence={"case_number": "DISP-2026-HC-402"},
        ),
    )
    assert c7.current_state == ConflictState.REOPENED
    assert sorted(c7.allowed_transitions) == ["UNDER_REVIEW"]

    # 8. REOPENED -> UNDER_REVIEW
    c8 = svc.transition(
        c.conflict_id,
        TransitionRequest(
            new_state=ConflictState.UNDER_REVIEW,
            actor="Senior Legal Surveyor (#501)",
            reason="Re-investigating boundary evidence following appeal",
            evidence={},
        ),
    )
    assert c8.current_state == ConflictState.UNDER_REVIEW


def test_direct_resolution_and_rejection(clean_conflict_service):
    """Verifies UNDER_REVIEW -> RESOLVED and UNDER_REVIEW -> REJECTED -> REOPENED."""
    svc = clean_conflict_service
    c_res = svc.create_conflict(
        CreateConflictRequest(parcel_uuid="UUID-DIRECT-RES", title="Minor Attribute Typo")
    )
    # DETECTED -> UNDER_REVIEW -> RESOLVED
    svc.transition(c_res.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Reviewing"))
    c_resolved = svc.transition(c_res.conflict_id, TransitionRequest(new_state=ConflictState.RESOLVED, actor="Analyst", reason="Immediate resolution"))
    assert c_resolved.current_state == ConflictState.RESOLVED

    # DETECTED -> UNDER_REVIEW -> REJECTED -> REOPENED
    c_rej = svc.create_conflict(
        CreateConflictRequest(parcel_uuid="UUID-REJECT-TEST", title="Spurious Claim")
    )
    svc.transition(c_rej.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Reviewing"))
    c_rejected = svc.transition(c_rej.conflict_id, TransitionRequest(new_state=ConflictState.REJECTED, actor="Analyst", reason="False positive complaint"))
    assert c_rejected.current_state == ConflictState.REJECTED
    assert c_rejected.allowed_transitions == ["REOPENED"]

    # REJECTED -> REOPENED
    c_reopened = svc.transition(c_rej.conflict_id, TransitionRequest(new_state=ConflictState.REOPENED, actor="Appellate Officer", reason="Appeal granted"))
    assert c_reopened.current_state == ConflictState.REOPENED


def test_recovery_transitions_back_to_under_review(clean_conflict_service):
    """Verifies states that can step back to UNDER_REVIEW for re-examination."""
    svc = clean_conflict_service

    # SURVEY_REQUIRED -> UNDER_REVIEW (cancelled survey)
    c1 = svc.create_conflict(CreateConflictRequest(parcel_uuid="UUID-REC-1", title="Rec 1"))
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Desk review"))
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.SURVEY_REQUIRED, actor="Analyst", reason="Need survey"))
    c1_back = svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Survey cancelled"))
    assert c1_back.current_state == ConflictState.UNDER_REVIEW

    # SURVEY_RECEIVED -> UNDER_REVIEW (poor GNSS fix)
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.SURVEY_REQUIRED, actor="Analyst", reason="Need survey"))
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.SURVEY_RECEIVED, actor="Analyst", reason="Data received"))
    c1_back2 = svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Poor PDOP satellite geometry"))
    assert c1_back2.current_state == ConflictState.UNDER_REVIEW

    # RECONCILIATION_PENDING -> UNDER_REVIEW (inconclusive fusion)
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.SURVEY_REQUIRED, actor="Analyst", reason="Need survey"))
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.SURVEY_RECEIVED, actor="Analyst", reason="Data received"))
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.RECONCILIATION_PENDING, actor="Analyst", reason="Queueing"))
    c1_back3 = svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Inconclusive consensus"))
    assert c1_back3.current_state == ConflictState.UNDER_REVIEW

    # RESOLVED -> UNDER_REVIEW (officer rejects proposed resolution)
    svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.RESOLVED, actor="Analyst", reason="Preliminary resolution"))
    c1_back4 = svc.transition(c1.conflict_id, TransitionRequest(new_state=ConflictState.UNDER_REVIEW, actor="Analyst", reason="Resolution rejected by senior surveyor"))
    assert c1_back4.current_state == ConflictState.UNDER_REVIEW


# ---------------------------------------------------------------------------
# 2. INVALID TRANSITION TESTS (REJECTION GUARDS)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start_state, illegal_target",
    [
        (ConflictState.DETECTED, ConflictState.APPROVED),
        (ConflictState.DETECTED, ConflictState.RESOLVED),
        (ConflictState.DETECTED, ConflictState.SURVEY_REQUIRED),
        (ConflictState.DETECTED, ConflictState.SURVEY_RECEIVED),
        (ConflictState.DETECTED, ConflictState.RECONCILIATION_PENDING),
        (ConflictState.DETECTED, ConflictState.REJECTED),
        (ConflictState.DETECTED, ConflictState.REOPENED),
        (ConflictState.UNDER_REVIEW, ConflictState.APPROVED),  # cannot approve before resolving
        (ConflictState.UNDER_REVIEW, ConflictState.SURVEY_RECEIVED),
        (ConflictState.UNDER_REVIEW, ConflictState.RECONCILIATION_PENDING),
        (ConflictState.UNDER_REVIEW, ConflictState.REOPENED),
        (ConflictState.SURVEY_REQUIRED, ConflictState.APPROVED),
        (ConflictState.SURVEY_REQUIRED, ConflictState.RESOLVED),
        (ConflictState.SURVEY_REQUIRED, ConflictState.RECONCILIATION_PENDING),
        (ConflictState.SURVEY_REQUIRED, ConflictState.REJECTED),
        (ConflictState.SURVEY_RECEIVED, ConflictState.APPROVED),
        (ConflictState.SURVEY_RECEIVED, ConflictState.RESOLVED),
        (ConflictState.SURVEY_RECEIVED, ConflictState.SURVEY_REQUIRED),
        (ConflictState.RECONCILIATION_PENDING, ConflictState.APPROVED),
        (ConflictState.RECONCILIATION_PENDING, ConflictState.SURVEY_REQUIRED),
        (ConflictState.RECONCILIATION_PENDING, ConflictState.REJECTED),
        (ConflictState.RESOLVED, ConflictState.SURVEY_REQUIRED),
        (ConflictState.RESOLVED, ConflictState.RECONCILIATION_PENDING),
        (ConflictState.RESOLVED, ConflictState.REJECTED),
        (ConflictState.APPROVED, ConflictState.UNDER_REVIEW),  # must go via REOPENED
        (ConflictState.APPROVED, ConflictState.RESOLVED),
        (ConflictState.APPROVED, ConflictState.DETECTED),
        (ConflictState.REJECTED, ConflictState.APPROVED),
        (ConflictState.REJECTED, ConflictState.RESOLVED),
        (ConflictState.REOPENED, ConflictState.APPROVED),
        (ConflictState.REOPENED, ConflictState.RESOLVED),
    ],
)
def test_invalid_transitions_raise_error(clean_conflict_service, start_state, illegal_target):
    """Tests that every illegal transition throws InvalidTransitionError."""
    svc = clean_conflict_service
    c = svc.create_conflict(CreateConflictRequest(parcel_uuid="TEST-INVALID", title="Invalid Transition Test"))
    # Manually position conflict in start_state for testing the guard
    c.current_state = start_state

    with pytest.raises(InvalidTransitionError) as exc_info:
        svc.transition(
            c.conflict_id,
            TransitionRequest(
                new_state=illegal_target,
                actor="Bad Actor",
                reason="Attempting illegal skip",
            ),
        )

    assert exc_info.value.current_state == start_state
    assert exc_info.value.requested_state == illegal_target


# ---------------------------------------------------------------------------
# 3. MANDATORY AUDIT TRAIL FIELD TESTS
# ---------------------------------------------------------------------------

def test_transition_records_mandatory_audit_fields(clean_conflict_service):
    """Verifies parcel_uuid, previous_state, new_state, actor, timestamp, reason, evidence are stored."""
    svc = clean_conflict_service
    parcel_uuid = "PARCEL-AUDIT-1234"
    c = svc.create_conflict(
        CreateConflictRequest(
            parcel_uuid=parcel_uuid,
            title="Audit Field Completeness Check",
            severity="HIGH",
            evidence={"initial_iou": 0.55},
        )
    )

    t_req = TransitionRequest(
        new_state=ConflictState.UNDER_REVIEW,
        actor="Officer S. Varma (Badge #88)",
        reason="Statutory verification order issued",
        evidence={"order_no": "ORD-2026-789", "drift_m": 3.12},
    )
    c_updated = svc.transition(c.conflict_id, t_req)

    # Check last transition
    assert len(c_updated.transitions) == 2  # initial DETECTED + transition to UNDER_REVIEW
    latest = c_updated.transitions[-1]

    assert latest.parcel_uuid == parcel_uuid
    assert latest.previous_state == ConflictState.DETECTED
    assert latest.new_state == ConflictState.UNDER_REVIEW
    assert latest.actor == "Officer S. Varma (Badge #88)"
    assert latest.reason == "Statutory verification order issued"
    assert latest.evidence["order_no"] == "ORD-2026-789"
    assert latest.evidence["drift_m"] == 3.12
    assert "T" in latest.timestamp  # valid ISO timestamp


# ---------------------------------------------------------------------------
# 4. REST API INTEGRATION TESTS
# ---------------------------------------------------------------------------

client = TestClient(app)


def test_api_get_conflicts_list():
    """GET /api/conflicts returns populated list with allowed transitions."""
    res = client.get("/api/conflicts")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    first = data[0]
    assert "conflict_id" in first
    assert "current_state" in first
    assert "allowed_transitions" in first
    assert isinstance(first["allowed_transitions"], list)


def test_api_get_conflict_by_id_and_parcel_lookup():
    """GET /api/conflicts/{id} accepts conflict_id or source_parcel_id."""
    import uuid
    uniq = uuid.uuid4().hex[:6].upper()
    src_id = f"SRC-LKUP-{uniq}"
    # Create fresh conflict
    c_res = client.post(
        "/api/conflicts",
        json={
            "parcel_uuid": f"UUID-LKUP-{uniq}",
            "source_parcel_id": src_id,
            "title": "Hermetic Lookup Test",
            "severity": "HIGH",
        },
    )
    assert c_res.status_code == 201
    cnf_id = c_res.json()["conflict_id"]

    res = client.get(f"/api/conflicts/{cnf_id}")
    assert res.status_code == 200
    body = res.json()
    assert body["conflict_id"] == cnf_id
    assert body["current_state"] == "DETECTED"
    assert body["allowed_transitions"] == ["UNDER_REVIEW"]

    # Lookup by source parcel ID
    res2 = client.get(f"/api/conflicts/{src_id}")
    assert res2.status_code == 200
    assert res2.json()["conflict_id"] == cnf_id


def test_api_transition_success_and_rejection():
    """POST /api/conflicts/{id}/transition enforces state machine via API."""
    import uuid
    uniq = uuid.uuid4().hex[:6].upper()
    # Create fresh conflict
    c_res = client.post(
        "/api/conflicts",
        json={
            "parcel_uuid": f"UUID-TRN-{uniq}",
            "source_parcel_id": f"SRC-TRN-{uniq}",
            "title": "Hermetic Transition Test",
            "severity": "HIGH",
        },
    )
    assert c_res.status_code == 201
    cnf_id = c_res.json()["conflict_id"]

    # 1. Illegal transition: DETECTED -> APPROVED -> HTTP 400
    res_bad = client.post(
        f"/api/conflicts/{cnf_id}/transition",
        json={
            "new_state": "APPROVED",
            "actor": "Unverified Operator",
            "reason": "Direct approval without review",
        },
    )
    assert res_bad.status_code == 400
    err = res_bad.json()["detail"]
    assert err["error"] == "INVALID_STATE_TRANSITION"
    assert err["current_state"] == "DETECTED"
    assert err["requested_state"] == "APPROVED"
    assert err["allowed_transitions"] == ["UNDER_REVIEW"]

    # 2. Valid transition: DETECTED -> UNDER_REVIEW -> HTTP 200
    res_good = client.post(
        f"/api/conflicts/{cnf_id}/transition",
        json={
            "new_state": "UNDER_REVIEW",
            "actor": "Officer K. Sharma (#402)",
            "reason": "Opening conflict investigation ticket",
            "evidence": {"method": "MANUAL_DISPATCH"},
        },
    )
    assert res_good.status_code == 200
    body = res_good.json()
    assert body["current_state"] == "UNDER_REVIEW"
    assert "SURVEY_REQUIRED" in body["allowed_transitions"]
    assert len(body["transitions"]) >= 2

    # Check last transition in body
    last_tr = body["transitions"][-1]
    assert last_tr["previous_state"] == "DETECTED"
    assert last_tr["new_state"] == "UNDER_REVIEW"
    assert last_tr["actor"] == "Officer K. Sharma (#402)"


def test_api_conflict_not_found():
    """GET and POST return 404 for unknown conflict ID."""
    res_get = client.get("/api/conflicts/NONEXISTENT-CONFLICT-999")
    assert res_get.status_code == 404

    res_post = client.post(
        "/api/conflicts/NONEXISTENT-CONFLICT-999/transition",
        json={"new_state": "UNDER_REVIEW", "actor": "Officer", "reason": "Test"},
    )
    assert res_post.status_code == 404
