"""
Lab 8: Azure Functions as agent tools.

Real Azure Functions implementation of the same create_incident /
request_service_restart contract used locally in tools_actions.py, this
time as an HTTP-triggered Function using the app's system-assigned managed
identity for outbound auth (no secrets in config) — matching the
"secretless configuration" topic from the syllabus.

NOT YET DEPLOYED. `func` (Azure Functions Core Tools) isn't installed on
this machine, so this code is written and reviewable but unverified by an
actual run. To deploy and test for real:

    brew tap azure/functions && brew install azure-functions-core-tools@4
    cd day2/azure_function
    func azure functionapp publish func-agent-demo-20674 --python

Then update tools_actions.py's demo to call this HTTP endpoint (with a
DefaultAzureCredential-issued token) instead of the in-process Python
functions, to show tool execution actually crossing a network boundary.
"""
import json
import logging
import time

import azure.functions as func

app = func.FunctionApp()

# In-memory idempotency store for this demo. A real deployment would use
# Azure Table Storage or Cosmos DB so it survives restarts and scale-out.
_IDEMPOTENCY_STORE: dict[str, dict] = {}


@app.function_name(name="create_incident")
@app.route(route="create-incident", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def create_incident(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "invalid_json_body"}), status_code=400, mimetype="application/json"
        )

    idempotency_key = body.get("idempotency_key")
    if not idempotency_key:
        return func.HttpResponse(
            json.dumps({"error": "missing_idempotency_key"}), status_code=400, mimetype="application/json"
        )

    if idempotency_key in _IDEMPOTENCY_STORE:
        logging.info("create_incident: replayed idempotency_key=%s, returning cached result", idempotency_key)
        return func.HttpResponse(
            json.dumps({"status": "already_exists", "ticket": _IDEMPOTENCY_STORE[idempotency_key]}),
            status_code=200, mimetype="application/json",
        )

    approval_token = body.get("approval_token")
    if not approval_token:
        return func.HttpResponse(
            json.dumps({"error": "approval_required"}), status_code=403, mimetype="application/json"
        )
    # In a real deployment: validate approval_token against the workflow
    # service (a separate call, e.g. via managed identity to an internal
    # approvals API) rather than trusting the caller's claim.

    ticket = {
        "ticket_id": f"INC-{int(time.time()) % 100000}",
        "severity": body.get("severity"),
        "affected_service": body.get("affected_service"),
        "summary": body.get("summary"),
        "evidence": body.get("evidence"),
        "created_at": time.time(),
    }
    _IDEMPOTENCY_STORE[idempotency_key] = ticket
    logging.info("create_incident: created %s", ticket["ticket_id"])
    return func.HttpResponse(
        json.dumps({"status": "created", "ticket": ticket}), status_code=201, mimetype="application/json"
    )


@app.function_name(name="request_service_restart")
@app.route(route="request-service-restart", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def request_service_restart(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "invalid_json_body"}), status_code=400, mimetype="application/json"
        )

    idempotency_key = body.get("idempotency_key")
    if not idempotency_key:
        return func.HttpResponse(
            json.dumps({"error": "missing_idempotency_key"}), status_code=400, mimetype="application/json"
        )

    if idempotency_key in _IDEMPOTENCY_STORE:
        logging.info("request_service_restart: replayed idempotency_key=%s", idempotency_key)
        return func.HttpResponse(
            json.dumps({"status": "already_executed", "result": _IDEMPOTENCY_STORE[idempotency_key]}),
            status_code=200, mimetype="application/json",
        )

    approval_token = body.get("approval_token")
    if not approval_token:
        return func.HttpResponse(
            json.dumps({"error": "approval_required"}), status_code=403, mimetype="application/json"
        )

    result = {
        "idempotency_key": idempotency_key,
        "service_name": body.get("service_name"),
        "environment": body.get("environment"),
        "justification": body.get("justification"),
        "executed_at": time.time(),
        "status": "restart_initiated",
    }
    _IDEMPOTENCY_STORE[idempotency_key] = result
    logging.info("request_service_restart: executed for %s", result["service_name"])
    return func.HttpResponse(
        json.dumps({"status": "restart_initiated", "result": result}), status_code=200, mimetype="application/json"
    )
