"""
Lab 10 (Day 3, Module 1): Instrument the complete agent.

Traces a full request path: classification -> tool selection -> tool
execution -> approval check -> final response, using OpenTelemetry spans
exported to Azure Monitor / Application Insights. Also demonstrates
correlation IDs threaded through every span, and sensitive-data redaction
(the malicious-runbook content is NOT logged verbatim into span
attributes, only its document ID and a redaction flag).

Verification note: this script confirms spans are created and exported
without error, and prints the trace/span IDs so you can search for them
in Application Insights (Transaction Search / Logs). Ingestion into App
Insights typically takes 1-5 minutes to become queryable, so this script
cannot itself prove the data landed — check the portal after running it.
"""
import time
import uuid

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import MessageRole, FunctionTool

from config import FOUNDRY_ENDPOINT, MODEL_DEPLOYMENT_NAME, APPLICATIONINSIGHTS_CONNECTION_STRING

configure_azure_monitor(connection_string=APPLICATIONINSIGHTS_CONNECTION_STRING)
tracer = trace.get_tracer(__name__)


def get_service_health(service_name: str, environment: str) -> str:
    """Get current health status of a service.

    :param service_name: Name of the service.
    :param environment: Deployment environment.
    :return: JSON status string.
    """
    with tracer.start_as_current_span("tool.get_service_health") as span:
        span.set_attribute("tool.service_name", service_name)
        span.set_attribute("tool.environment", environment)
        time.sleep(0.05)  # simulate backend latency
        return '{"status": "degraded", "pool_acquisition_ms": 5200}'


def redact_if_sensitive(text: str) -> str:
    """Never write raw retrieved/user content into a span attribute — log a
    fingerprint instead. Real systems should apply this to anything that
    might contain secrets, PII, or injected instructions."""
    if len(text) > 200 or "SYSTEM OVERRIDE" in text:
        return f"[REDACTED: {len(text)} chars, content hash omitted for demo]"
    return text


def run_traced_request(client: AgentsClient, agent_id: str, request_text: str, correlation_id: str):
    with tracer.start_as_current_span("agent_workflow.user_request") as root_span:
        root_span.set_attribute("correlation_id", correlation_id)
        root_span.set_attribute("request.redacted_preview", redact_if_sensitive(request_text))

        with tracer.start_as_current_span("workflow.classification") as span:
            span.set_attribute("correlation_id", correlation_id)
            thread = client.threads.create()
            client.messages.create(thread.id, role=MessageRole.USER, content=request_text)
            span.set_attribute("thread_id", thread.id)

        with tracer.start_as_current_span("workflow.agent_run") as span:
            span.set_attribute("correlation_id", correlation_id)
            span.set_attribute("model", MODEL_DEPLOYMENT_NAME)
            start = time.perf_counter()
            run = client.runs.create_and_process(thread.id, agent_id=agent_id)
            latency_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("run.status", str(run.status))
            span.set_attribute("run.latency_ms", latency_ms)
            if run.usage:
                span.set_attribute("run.prompt_tokens", run.usage.prompt_tokens)
                span.set_attribute("run.completion_tokens", run.usage.completion_tokens)

        with tracer.start_as_current_span("workflow.final_response") as span:
            reply = None
            for msg in client.messages.list(thread.id):
                if msg.role == MessageRole.AGENT:
                    reply = "".join(c.text.value for c in msg.content if hasattr(c, "text"))
                    break
            span.set_attribute("response.redacted_preview", redact_if_sensitive(reply or ""))

        trace_id = format(root_span.get_span_context().trace_id, "032x")
        print(f"correlation_id={correlation_id}  trace_id={trace_id}  latency_ms={latency_ms:.0f}")
        print(f"Reply: {reply}\n")


def main():
    client = AgentsClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())
    functions = FunctionTool({get_service_health})
    client.enable_auto_function_calls(functions)

    agent = client.create_agent(
        model=MODEL_DEPLOYMENT_NAME,
        name="traced-agent-demo",
        instructions="Diagnose incidents using get_service_health when relevant.",
        tools=functions.definitions,
    )
    print(f"Created agent: {agent.id}\n")

    try:
        requests = [
            ("Is payment-service healthy in production?", str(uuid.uuid4())),
            ("What's 2+2?", str(uuid.uuid4())),  # no tool call needed, still traced
        ]
        for text, correlation_id in requests:
            run_traced_request(client, agent.id, text, correlation_id)
    finally:
        client.delete_agent(agent.id)
        print(f"Cleaned up agent {agent.id}")
        print(
            "\nTo verify these traces landed in Azure: portal.azure.com -> "
            "Application Insights 'appi-agent-demo' -> Transaction Search, "
            "search for one of the trace_id values above. Allow 1-5 minutes "
            "for ingestion."
        )


if __name__ == "__main__":
    main()
