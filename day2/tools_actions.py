"""
Lab 8/9: Controlled write ("action") tools.

Unlike the read-only tools, these can change production state, so every
call is checked against the workflow's approval-token store before it does
anything, and every call is idempotency-keyed so a retried tool call (the
model re-asking, a network retry, etc.) cannot execute twice.
"""
import json
import time

import workflow

_INCIDENT_STORE: dict[str, dict] = {}       # idempotency_key -> created ticket
_RESTART_LOG: list[dict] = []               # audit trail of restarts actually performed


def create_incident(
    severity: str,
    affected_service: str,
    summary: str,
    evidence: str,
    idempotency_key: str,
    correlation_id: str,
    approval_token: str,
) -> str:
    """Create an incident ticket. Write operation, Medium risk, approval required.

    :param severity: One of SEV-1, SEV-2, SEV-3, SEV-4.
    :param affected_service: The service this incident is about.
    :param summary: One-line incident summary.
    :param evidence: Supporting evidence for why this incident is being created.
    :param idempotency_key: Unique key for this specific incident-creation attempt;
        calling again with the same key returns the original result instead of duplicating.
    :param correlation_id: The workflow correlation ID this action belongs to.
    :param approval_token: A human-issued approval token scoped to 'create_incident:<affected_service>'.
    :return: JSON string with the created ticket, or an error object.
    """
    if idempotency_key in _INCIDENT_STORE:
        return json.dumps({"status": "already_exists", "ticket": _INCIDENT_STORE[idempotency_key]})

    required_scope = f"create_incident:{affected_service}"
    ok, reason = workflow.validate_and_consume_approval(approval_token, required_scope, correlation_id)
    if not ok:
        return json.dumps({"error": "approval_rejected", "reason": reason})

    ticket = {
        "ticket_id": f"INC-{int(time.time()) % 100000}",
        "severity": severity,
        "affected_service": affected_service,
        "summary": summary,
        "evidence": evidence,
        "created_at": time.time(),
    }
    _INCIDENT_STORE[idempotency_key] = ticket
    return json.dumps({"status": "created", "ticket": ticket})


def request_service_restart(
    service_name: str,
    environment: str,
    justification: str,
    idempotency_key: str,
    correlation_id: str,
    approval_token: str,
) -> str:
    """Request a controlled restart of a service. Write operation, Critical risk, approval required.

    :param service_name: The service to restart.
    :param environment: Deployment environment; restarts in 'production' require
        the strictest approval scope.
    :param justification: Why this restart is being requested.
    :param idempotency_key: Unique key for this specific restart attempt;
        calling again with the same key returns the original result instead of restarting twice.
    :param correlation_id: The workflow correlation ID this action belongs to.
    :param approval_token: A human-issued approval token scoped to 'restart:<service_name>:<environment>'.
    :return: JSON string confirming the restart, or an error object.
    """
    for entry in _RESTART_LOG:
        if entry["idempotency_key"] == idempotency_key:
            return json.dumps({"status": "already_executed", "result": entry})

    required_scope = f"restart:{service_name}:{environment}"
    ok, reason = workflow.validate_and_consume_approval(approval_token, required_scope, correlation_id)
    if not ok:
        return json.dumps({"error": "approval_rejected", "reason": reason})

    result = {
        "idempotency_key": idempotency_key,
        "service_name": service_name,
        "environment": environment,
        "justification": justification,
        "executed_at": time.time(),
        "status": "restart_initiated",
    }
    _RESTART_LOG.append(result)
    return json.dumps({"status": "restart_initiated", "result": result})
