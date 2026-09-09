"""
Lab 9: Build the approval-controlled workflow.

Drives workflow.py + tools_actions.py directly (no LLM in the loop here —
Module 4 is about the state machine and approval mechanics themselves,
independent of the agent; Lab 7's agent is what would call these tools in
a full system). Demonstrates every item in the syllabus's Lab 9 checklist:
persist state, enforce valid transitions, propose an action, pause for
approval, validate the approver/scope, execute once, resume, handle
rejection, and produce an audit trail.
"""
import json

import workflow
from workflow import State, Workflow, InvalidTransitionError
from tools_actions import request_service_restart


def run_scenario(label: str, fn):
    print(f"\n{'='*70}\n{label}")
    fn()


def scenario_happy_path():
    correlation_id = "corr-demo-001"
    wf = Workflow(correlation_id=correlation_id)
    workflow.save(wf)

    wf.transition(State.CLASSIFIED)
    wf.transition(State.EVIDENCE_COLLECTED)
    wf.propose_action("restart_service", scope="restart:payment-service:production")
    print(f"State after proposal: {wf.state.value} (paused, waiting for a human)")

    # Attempt execution BEFORE approval exists — must be rejected.
    result = json.loads(request_service_restart(
        service_name="payment-service", environment="production",
        justification="Pool saturation confirmed via evidence", idempotency_key="restart-corr-001",
        correlation_id=correlation_id, approval_token="not-a-real-token",
    ))
    print(f"Execution attempt with no valid approval: {result}")
    assert result["error"] == "approval_rejected"

    # A human approves out-of-band.
    approval = workflow.issue_approval(correlation_id, scope="restart:payment-service:production")
    print(f"Human issued approval token (scope={approval.scope}, expires_at={approval.expires_at:.0f})")

    wf.transition(State.APPROVED)
    wf.transition(State.EXECUTING)

    result = json.loads(request_service_restart(
        service_name="payment-service", environment="production",
        justification="Pool saturation confirmed via evidence", idempotency_key="restart-corr-001",
        correlation_id=correlation_id, approval_token=approval.token,
    ))
    print(f"Execution with valid approval: {result}")
    assert result["status"] == "restart_initiated"

    wf.transition(State.COMPLETED)
    print(f"Final state: {wf.state.value}")
    print(f"Audit trail ({len(wf.audit_log)} events):")
    for event in wf.audit_log:
        print(f"  {event}")


def scenario_duplicate_action_prevented():
    correlation_id = "corr-demo-002"
    approval = workflow.issue_approval(correlation_id, scope="restart:payment-service:production")

    first = json.loads(request_service_restart(
        service_name="payment-service", environment="production", justification="test",
        idempotency_key="restart-corr-002", correlation_id=correlation_id, approval_token=approval.token,
    ))
    print(f"First call: {first['status']}")

    # Same idempotency_key again — must not restart twice, even with a fresh (unused) token concept.
    second = json.loads(request_service_restart(
        service_name="payment-service", environment="production", justification="test",
        idempotency_key="restart-corr-002", correlation_id=correlation_id, approval_token="irrelevant-now",
    ))
    print(f"Second call (same idempotency_key): {second['status']}")
    assert second["status"] == "already_executed"
    print("Duplicate action correctly prevented by idempotency key.")


def scenario_reused_approval_token_rejected():
    """Attack simulation from Module 5: 'Reused approval token'."""
    correlation_id = "corr-demo-003"
    approval = workflow.issue_approval(correlation_id, scope="restart:payment-service:production")

    first = json.loads(request_service_restart(
        service_name="payment-service", environment="production", justification="legit request",
        idempotency_key="restart-corr-003-a", correlation_id=correlation_id, approval_token=approval.token,
    ))
    print(f"First (legitimate) use of token: {first['status']}")
    assert first["status"] == "restart_initiated"

    # Attacker (or a buggy retry) reuses the SAME token for a DIFFERENT action.
    replay = json.loads(request_service_restart(
        service_name="payment-service", environment="production", justification="replayed request",
        idempotency_key="restart-corr-003-b", correlation_id=correlation_id, approval_token=approval.token,
    ))
    print(f"Reused token on a different action: {replay}")
    assert replay["error"] == "approval_rejected"
    assert replay["reason"] == "token_already_used"
    print("Token replay correctly rejected.")


def scenario_scope_mismatch_rejected():
    """Attack simulation: token issued for one service, used to act on another."""
    correlation_id = "corr-demo-004"
    approval = workflow.issue_approval(correlation_id, scope="restart:payment-service:production")

    result = json.loads(request_service_restart(
        service_name="database-cluster-prod",  # different service than the token was scoped to
        environment="production", justification="scope confusion attempt",
        idempotency_key="restart-corr-004", correlation_id=correlation_id, approval_token=approval.token,
    ))
    print(f"Attempt to use payment-service approval to restart database-cluster-prod: {result}")
    assert result["error"] == "approval_rejected"
    assert result["reason"] == "token_scope_mismatch"
    print("Scope mismatch correctly rejected.")


def scenario_invalid_transition_rejected():
    wf = Workflow(correlation_id="corr-demo-005")
    try:
        wf.transition(State.EXECUTING)  # cannot jump straight from RECEIVED to EXECUTING
        print("FAIL: invalid transition was allowed")
    except InvalidTransitionError as e:
        print(f"Invalid transition correctly rejected: {e}")


def scenario_pause_resume():
    correlation_id = "corr-demo-006"
    wf = Workflow(correlation_id=correlation_id)
    wf.transition(State.CLASSIFIED)
    wf.transition(State.EVIDENCE_COLLECTED)
    wf.propose_action("restart_service", scope="restart:payment-service:production")
    print(f"Workflow paused at: {wf.state.value}. Simulating process restart...")

    # Simulate a fresh process: don't reuse the in-memory `wf`, reload from disk.
    reloaded = workflow.load(correlation_id)
    print(f"Reloaded from persisted state: {reloaded.state.value} (matches: {reloaded.state == wf.state})")
    assert reloaded.state == State.AWAITING_APPROVAL


if __name__ == "__main__":
    run_scenario("Scenario 1: Happy path (approval required, then granted)", scenario_happy_path)
    run_scenario("Scenario 2: Duplicate action prevented by idempotency key", scenario_duplicate_action_prevented)
    run_scenario("Scenario 3: Reused approval token rejected (replay attack)", scenario_reused_approval_token_rejected)
    run_scenario("Scenario 4: Scope-mismatched token rejected", scenario_scope_mismatch_rejected)
    run_scenario("Scenario 5: Invalid state transition rejected", scenario_invalid_transition_rejected)
    run_scenario("Scenario 6: Workflow survives a process restart (persisted state)", scenario_pause_resume)
    print("\nAll Lab 9 scenarios passed.")
