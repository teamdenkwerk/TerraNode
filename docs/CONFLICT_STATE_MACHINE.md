# TERRANODE FEATURE 05 — CONFLICT LIFECYCLE STATE MACHINE SPECIFICATION

## 1. Executive Summary & Problem Formulation

In cadastral governance and municipal land administration, boundary disputes, overlapping claims, and survey discrepancies cannot be handled with informal, mutable status strings or ad-hoc button clicks:
- **Legal Accountability**: Every state transition must record *who* triggered it, *when*, *why*, and with *what evidence*.
- **Process Integrity**: An entity cannot jump straight from `DETECTED` to `APPROVED` without undergoing systematic desk review, field rover surveys, and consensus reconciliation.
- **Audit Defensibility**: Appellate challenges, land tribunal appeals, and municipal audits require an immutable chronological timeline of all decisions and telemetry.

**TERRANODE Conflict Lifecycle State Machine** (`backend/conflicts/state_machine.py`) replaces informal review queue handling with an explicit, auditable, non-bypassable finite state machine (FSM).

---

## 2. Complete State Machine Specification

### The 9 Lifecycle States
| State | Category | Operational Definition |
| :--- | :--- | :--- |
| **`DETECTED`** | Initial | Boundary divergence or attribute discrepancy flagged by the automated reconciliation policy or ingestion checks. |
| **`UNDER_REVIEW`** | Active Investigation | Case assigned to a land records analyst or review officer for desk examination. |
| **`SURVEY_REQUIRED`** | Field Escalation | Desk review determined that satellite or paper maps are inconclusive; physical DGPS rover or drone survey ordered. |
| **`SURVEY_RECEIVED`** | Data Ingested | Field survey rover coordinates (RTK fix, corner pegs) uploaded and logged to the case. |
| **`RECONCILIATION_PENDING`** | Processing | Queued for consensus geometry fusion between registered cadastre and field survey points. |
| **`RESOLVED`** | Proposed Solution | Harmonized boundary consensus computed and accepted by the technical review team. |
| **`APPROVED`** | Final Sign-Off | Senior Surveyor General or District Revenue Officer has formally authorized and sealed the resolution. |
| **`REJECTED`** | Dismissed | Conflict determined to be a false positive, duplicate claim, or legally invalid dispute. |
| **`REOPENED`** | Appellate Appeal | Previously approved or rejected conflict re-opened following an administrative appeal, court order, or new survey evidence. |

---

### Finite State Transition Graph

```
                                  ┌──────────────┐
                                  │   DETECTED   │
                                  └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │ UNDER_REVIEW ├─────────────────────────┐
                                  └──┬─────────┬─┘                         │
                                     │         │                           │
                   ┌─────────────────┘         └─────────────────┐         │
                   ▼                                             ▼         ▼
          ┌─────────────────┐                           ┌──────────┐ ┌──────────┐
   ┌─────►│ SURVEY_REQUIRED │                           │ RESOLVED │ │ REJECTED │
   │      └────────┬────────┘                           └────┬─────┘ └────┬─────┘
   │               │                                         │            │
   │               ▼                                         ▼            │
   │      ┌─────────────────┐                           ┌──────────┐      │
   │      │ SURVEY_RECEIVED │                           │ APPROVED │      │
   │      └────────┬────────┘                           └────┬─────┘      │
   │               │                                         │            │
   │               ▼                                         │            │
   │    ┌────────────────────────┐                           │            │
   │    │ RECONCILIATION_PENDING │                           │            │
   │    └──────────┬─────────────┘                           │            │
   │               │                                         │            │
   │               └───────────────────────────┐             │            │
   │                                           ▼             ▼            ▼
   │                                     ┌───────────────────────────────────┐
   │                                     │             REOPENED              │
   │                                     └─────────────────┬─────────────────┘
   │                                                       │
   └───────────────────────────────────────────────────────┘
                     (Re-enters UNDER_REVIEW)
```

### Transition Table & Guard Rules
| Current State | Allowed Next States | Guard Invariant / Rationale |
| :--- | :--- | :--- |
| **`DETECTED`** | `UNDER_REVIEW` | Must be acknowledged and assigned to an officer before any actions can be taken. |
| **`UNDER_REVIEW`** | `SURVEY_REQUIRED`, `RESOLVED`, `REJECTED` | Officer can order field rover survey, resolve directly if evidence is conclusive, or dismiss invalid claims. |
| **`SURVEY_REQUIRED`** | `SURVEY_RECEIVED`, `UNDER_REVIEW` | Moves forward when survey coordinates are received, or reverts to desk review if survey is cancelled. |
| **`SURVEY_RECEIVED`** | `RECONCILIATION_PENDING`, `UNDER_REVIEW` | Moves forward to automated consensus engine, or reverts if survey data has high PDOP / poor fix. |
| **`RECONCILIATION_PENDING`** | `RESOLVED`, `UNDER_REVIEW` | Moves forward once consensus boundary is computed, or reverts if automated fusion is inconclusive. |
| **`RESOLVED`** | `APPROVED`, `UNDER_REVIEW` | Requires senior authority signature for approval, or reverts if reviewer challenges proposed boundary. |
| **`APPROVED`** | `REOPENED` | Terminal operational state; can only transition to `REOPENED` via formal appeal or court order. |
| **`REJECTED`** | `REOPENED` | Terminal dismissal state; can only transition to `REOPENED` via administrative appeal or critical evidence. |
| **`REOPENED`** | `UNDER_REVIEW` | Reopened cases re-enter active review under an assigned officer. |

> [!IMPORTANT]
> **SAFETY GUARD: REJECTION OF INVALID TRANSITIONS**  
> Any transition not explicitly permitted above (e.g. `DETECTED` $\rightarrow$ `APPROVED`, `SURVEY_REQUIRED` $\rightarrow$ `RESOLVED`, `UNDER_REVIEW` $\rightarrow$ `APPROVED`) is **strictly rejected** by the state machine with an `InvalidTransitionError` mapped to HTTP **400 Bad Request**.

---

## 3. Data Schema & Models

### `ConflictTransitionRecord`
Every single state transition creates an immutable audit record:
```json
{
  "transition_id": "TR-a7f41e0b",
  "parcel_uuid": "58039d15-328e-5d1d-a453-a06e4f3cbfa3",
  "previous_state": "SURVEY_REQUIRED",
  "new_state": "SURVEY_RECEIVED",
  "actor": "Field Rover Team Bravo (RTK Rover #12)",
  "timestamp": "2026-09-27T05:52:10Z",
  "reason": "Ground RTK rover checkpoint log uploaded (4 corner pegs pinned)",
  "evidence": {
    "gnss_fix_type": "RTK_FIXED",
    "horizontal_accuracy_cm": 1.4,
    "points_collected": 4
  }
}
```

### `ConflictRecord`
```json
{
  "conflict_id": "CNF-BLR-114",
  "parcel_uuid": "58039d15-328e-5d1d-a453-a06e4f3cbfa3",
  "source_parcel_id": "BLR-114",
  "current_state": "SURVEY_RECEIVED",
  "previous_state": "SURVEY_REQUIRED",
  "title": "Road Widening Encroachment Discrepancy",
  "severity": "HIGH",
  "category": "BOUNDARY_OVERLAP",
  "discrepancy_metrics": {
    "centroid_drift_m": 2.82,
    "iou": 0.589,
    "confidence": 0.61
  },
  "assigned_officer": "Officer K. Sharma (#402)",
  "created_at": "2026-09-26T08:00:00Z",
  "updated_at": "2026-09-27T05:52:10Z",
  "allowed_transitions": ["RECONCILIATION_PENDING", "UNDER_REVIEW"],
  "transitions": [ ... chronological array of ConflictTransitionRecord ... ]
}
```

---

## 4. REST API Specification

### `GET /api/conflicts`
Lists all active and historical conflicts with filtering by `state`, `severity`, or `parcel_uuid`.
- **Response** (`200 OK`): Array of `ConflictRecord` objects with populated `allowed_transitions`.

### `GET /api/conflicts/{id}`
Retrieves conflict record by conflict ID or parcel reference (e.g. `CNF-BLR-102` or `BLR-102`).
- **Response** (`200 OK`): Single `ConflictRecord` object with full immutable audit history.
- **Error** (`404 Not Found`): If conflict ID or parcel reference does not exist.

### `POST /api/conflicts/{id}/transition`
Executes an authoritative state transition.
- **Request Body**:
  ```json
  {
    "new_state": "UNDER_REVIEW",
    "actor": "Officer K. Sharma (Senior Analyst #402)",
    "reason": "Opening formal investigation into multi-meter setback discrepancy",
    "evidence": { "method": "MANUAL_DISPATCH", "ticket": "REV-2026-99" }
  }
  ```
- **Response** (`200 OK`): Updated `ConflictRecord` with new state and appended transition record.
- **Error** (`400 Bad Request`): Returned if transition is invalid:
  ```json
  {
    "detail": {
      "error": "INVALID_STATE_TRANSITION",
      "message": "Invalid conflict transition from 'DETECTED' to 'APPROVED'. Allowed next states from 'DETECTED': ['UNDER_REVIEW'].",
      "current_state": "DETECTED",
      "requested_state": "APPROVED",
      "allowed_transitions": ["UNDER_REVIEW"]
    }
  }
  ```

---

## 5. Frontend User Experience & UI Safety

1. **Non-Bypassable UI Guard**:
   - The user interface **never modifies status locally**. All status updates require dispatching a verified payload to `POST /api/conflicts/{id}/transition`.
   - The UI dropdown and action buttons dynamically render **only** the `allowed_transitions` returned by the backend.
2. **Review Queue View Integration** (`frontend/src/components/ReviewQueueView.tsx`):
   - Every review card displays a high-contrast State Machine badge (`DETECTED`, `UNDER_REVIEW`, etc.).
   - Clicking **"State Machine"** on any card immediately opens the dedicated **Conflict Lifecycle Modal**.
3. **Conflict Lifecycle Modal** (`frontend/src/components/ConflictLifecycleModal.tsx`):
   - **Chronological Audit Timeline**: Renders the complete progression of states with previous/new state badges, actors, UTC timestamps, reasons, and evidence payloads.
   - **Guarded Action Form**: Allows selecting only valid next states, requires a minimum 3-character statutory justification, logs telemetry notes, and provides real-time feedback with error banners or confirmation confetti.

---

## 6. Automated Test Suite

Tested in [`tests/test_conflict_state_machine.py`](../tests/test_conflict_state_machine.py) with 100% pass rate:
- Standard lifecycle sequence (`DETECTED` $\rightarrow$ `UNDER_REVIEW` $\rightarrow$ `SURVEY_REQUIRED` $\rightarrow$ `SURVEY_RECEIVED` $\rightarrow$ `RECONCILIATION_PENDING` $\rightarrow$ `RESOLVED` $\rightarrow$ `APPROVED` $\rightarrow$ `REOPENED` $\rightarrow$ `UNDER_REVIEW`).
- Alternative direct paths (`UNDER_REVIEW` $\rightarrow$ `RESOLVED`, `UNDER_REVIEW` $\rightarrow$ `REJECTED` $\rightarrow$ `REOPENED`).
- Recovery transitions back to `UNDER_REVIEW`.
- Rejection of 31 distinct illegal transition permutations (`test_invalid_transitions_raise_error`).
- Mandatory audit fields persistence (`parcel_uuid`, `previous_state`, `new_state`, `actor`, `timestamp`, `reason`, `evidence`).
- REST API integration tests (`GET /api/conflicts`, `GET /api/conflicts/{id}`, `POST /api/conflicts/{id}/transition` with HTTP 200, 400, and 404).
