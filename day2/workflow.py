"""
Module 4 / Lab 9: Workflow state and human approval.

An external, persisted state machine that sits outside the agent loop.
The agent proposes actions; this module is the only thing that can move a
request from AWAITING_APPROVAL to APPROVED, and only a human-issued,
single-use, scoped approval token can do that. Persists to a local JSON
file to demonstrate pause/resume across process restarts (a real system
would use a database).
"""
import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

STORE_PATH = Path(__file__).parent / "workflow_state.json"


class State(str, Enum):
    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


VALID_TRANSITIONS = {
    State.RECEIVED: {State.CLASSIFIED, State.ESCALATED},
    State.CLASSIFIED: {State.EVIDENCE_COLLECTED, State.ESCALATED},
    State.EVIDENCE_COLLECTED: {State.ACTION_PROPOSED, State.ESCALATED},
    State.ACTION_PROPOSED: {State.AWAITING_APPROVAL, State.ESCALATED},
    State.AWAITING_APPROVAL: {State.APPROVED, State.FAILED, State.ESCALATED},
    State.APPROVED: {State.EXECUTING},
    State.EXECUTING: {State.COMPLETED, State.FAILED},
    State.FAILED: {State.ESCALATED},
    State.COMPLETED: set(),
    State.ESCALATED: set(),
}


class InvalidTransitionError(Exception):
    pass


@dataclass
class ApprovalToken:
    token: str
    scope: str          # e.g. "restart:payment-service"
    correlation_id: str
    issued_at: float
    expires_at: float
    used: bool = False


@dataclass
class Workflow:
    correlation_id: str
    state: State = State.RECEIVED
    proposed_action: Optional[str] = None
    proposed_scope: Optional[str] = None
    audit_log: list = field(default_factory=list)
    executed_idempotency_keys: set = field(default_factory=set)

    def _record(self, event: str):
        self.audit_log.append({"ts": time.time(), "event": event, "state": self.state.value})

    def transition(self, new_state: State):
        if new_state not in VALID_TRANSITIONS[self.state]:
            raise InvalidTransitionError(f"{self.state} -> {new_state} is not a valid transition")
        self._record(f"transition:{self.state.value}->{new_state.value}")
        self.state = new_state
        save(self)

    def propose_action(self, action: str, scope: str):
        self.proposed_action = action
        self.proposed_scope = scope
        self.transition(State.ACTION_PROPOSED)
        self.transition(State.AWAITING_APPROVAL)

    def to_dict(self) -> dict:
        return {
            "correlation_id": self.correlation_id,
            "state": self.state.value,
            "proposed_action": self.proposed_action,
            "proposed_scope": self.proposed_scope,
            "audit_log": self.audit_log,
            "executed_idempotency_keys": list(self.executed_idempotency_keys),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Workflow":
        wf = cls(correlation_id=d["correlation_id"], state=State(d["state"]))
        wf.proposed_action = d.get("proposed_action")
        wf.proposed_scope = d.get("proposed_scope")
        wf.audit_log = d.get("audit_log", [])
        wf.executed_idempotency_keys = set(d.get("executed_idempotency_keys", []))
        return wf


def _load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return {}


def save(workflow: Workflow):
    store = _load_store()
    store[workflow.correlation_id] = workflow.to_dict()
    STORE_PATH.write_text(json.dumps(store, indent=2))


def load(correlation_id: str) -> Optional[Workflow]:
    store = _load_store()
    record = store.get(correlation_id)
    return Workflow.from_dict(record) if record else None


# --- Approval tokens: single-use, scoped, expiring -----------------------

_APPROVALS_PATH = Path(__file__).parent / "approval_tokens.json"


def issue_approval(correlation_id: str, scope: str, ttl_seconds: int = 300) -> ApprovalToken:
    """Simulates a human clicking 'Approve' in a UI. In production this
    would be an authenticated endpoint, not a Python function."""
    token = ApprovalToken(
        token=secrets.token_urlsafe(24),
        scope=scope,
        correlation_id=correlation_id,
        issued_at=time.time(),
        expires_at=time.time() + ttl_seconds,
    )
    store = json.loads(_APPROVALS_PATH.read_text()) if _APPROVALS_PATH.exists() else {}
    store[token.token] = token.__dict__
    _APPROVALS_PATH.write_text(json.dumps(store, indent=2))
    return token


def validate_and_consume_approval(token_str: str, required_scope: str, correlation_id: str) -> tuple[bool, str]:
    """Returns (ok, reason). Consumes the token on success so it cannot be reused."""
    if not _APPROVALS_PATH.exists():
        return False, "no_approvals_issued"
    store = json.loads(_APPROVALS_PATH.read_text())
    record = store.get(token_str)
    if record is None:
        return False, "token_not_found"
    if record["used"]:
        return False, "token_already_used"
    if record["correlation_id"] != correlation_id:
        return False, "token_wrong_correlation_id"
    if record["scope"] != required_scope:
        return False, "token_scope_mismatch"
    if time.time() > record["expires_at"]:
        return False, "token_expired"

    record["used"] = True
    store[token_str] = record
    _APPROVALS_PATH.write_text(json.dumps(store, indent=2))
    return True, "ok"
