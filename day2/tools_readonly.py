"""
Module 1/2 (Lab 6/7): Read-only tools with a mock backend.

These simulate real internal APIs (service-health dashboard, incident
history, on-call schedule) so the demo doesn't depend on real production
systems. Each function's docstring uses Sphinx-style `:param:` tags because
that's what azure-ai-agents' FunctionTool parses to build the tool schema
(verified against the installed SDK source, not guessed).

Test conditions covered (mirrors the syllabus's Lab 7 list): valid service,
unknown service, invalid environment, downstream timeout, empty response,
malformed tool output, rate-limit response.
"""
import json
import time

_KNOWN_SERVICES = {"payment-service", "database-cluster-prod", "kubernetes-prod"}
_VALID_ENVIRONMENTS = {"production", "staging", "development"}

# Mock backend state, keyed by service name, to simulate different failure modes.
_MOCK_HEALTH = {
    "payment-service": {"status": "degraded", "pool_acquisition_ms": 5200, "error_rate": 0.12},
    "database-cluster-prod": {"status": "unhealthy", "pool_acquisition_ms": 8100, "error_rate": 0.31},
    "kubernetes-prod": {"status": "healthy", "pool_acquisition_ms": 0, "error_rate": 0.0},
    "slow-service": "__TIMEOUT__",       # simulates a downstream timeout
    "empty-service": "__EMPTY__",        # simulates an empty response
    "malformed-service": "__MALFORMED__",  # simulates a corrupt upstream response
    "throttled-service": "__RATE_LIMITED__",  # simulates a 429 from the backend
}

_ON_CALL = {
    "payment-service": {"engineer": "Priya Shah", "pager": "PAY-ONCALL"},
    "database-cluster-prod": {"engineer": "Marcus Lee", "pager": "DATA-ONCALL"},
    "kubernetes-prod": {"engineer": "Jon Alves", "pager": "INFRA-ONCALL"},
}

_RECENT_INCIDENTS = {
    "payment-service": [
        {"id": "INC-4821", "summary": "P95 latency spike during traffic surge, pool saturation + retry amplification"},
    ],
    "database-cluster-prod": [
        {"id": "INC-3390", "summary": "Connection pool exhaustion from a long-running migration"},
    ],
}


def get_service_health(service_name: str, environment: str) -> str:
    """Get the current health status of an internal service.

    Read-only. No approval required.

    :param service_name: Name of the service to check, e.g. 'payment-service'.
    :param environment: Deployment environment, one of production/staging/development.
    :return: JSON string with status, pool_acquisition_ms, and error_rate, or an error object.
    """
    if environment not in _VALID_ENVIRONMENTS:
        return json.dumps({"error": "invalid_environment", "environment": environment})

    record = _MOCK_HEALTH.get(service_name)
    if record is None:
        return json.dumps({"error": "unknown_service", "service_name": service_name})
    if record == "__TIMEOUT__":
        time.sleep(0.1)
        return json.dumps({"error": "downstream_timeout", "service_name": service_name})
    if record == "__EMPTY__":
        return json.dumps({})
    if record == "__MALFORMED__":
        return "{not valid json"
    if record == "__RATE_LIMITED__":
        return json.dumps({"error": "rate_limited", "retry_after_seconds": 5})

    return json.dumps({"service_name": service_name, "environment": environment, **record})


def search_recent_incidents(service_name: str, lookback_hours: int) -> str:
    """Search recent incident history for a service.

    Read-only. No approval required.

    :param service_name: Name of the service to search incidents for.
    :param lookback_hours: How many hours back to search.
    :return: JSON string listing matching incidents.
    """
    if service_name not in _RECENT_INCIDENTS and service_name not in _KNOWN_SERVICES:
        return json.dumps({"error": "unknown_service", "service_name": service_name})
    incidents = _RECENT_INCIDENTS.get(service_name, [])
    return json.dumps({"service_name": service_name, "lookback_hours": lookback_hours, "incidents": incidents})


def get_on_call_engineer(service_name: str) -> str:
    """Get the current on-call engineer for a service.

    Read-only. No approval required.

    :param service_name: Name of the service to look up on-call for.
    :return: JSON string with engineer name and pager rotation, or an error object.
    """
    record = _ON_CALL.get(service_name)
    if record is None:
        return json.dumps({"error": "unknown_service", "service_name": service_name})
    return json.dumps({"service_name": service_name, **record})
