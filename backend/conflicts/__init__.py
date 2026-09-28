"""
backend/conflicts

TERRANODE FEATURE 05 — CONFLICT LIFECYCLE STATE MACHINE
"""

from backend.conflicts.state_machine import (
    ConflictNotFoundError,
    ConflictRecord,
    ConflictState,
    ConflictStateMachineService,
    ConflictTransitionRecord,
    CreateConflictRequest,
    InvalidTransitionError,
    TransitionRequest,
    VALID_TRANSITIONS,
    get_conflict_service,
)

__all__ = [
    "ConflictNotFoundError",
    "ConflictRecord",
    "ConflictState",
    "ConflictStateMachineService",
    "ConflictTransitionRecord",
    "CreateConflictRequest",
    "InvalidTransitionError",
    "TransitionRequest",
    "VALID_TRANSITIONS",
    "get_conflict_service",
]
