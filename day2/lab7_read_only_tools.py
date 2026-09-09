"""
Lab 7: Implement read-only tools.

An agent that selects and executes the correct read-only tools
(get_service_health, search_recent_incidents, get_on_call_engineer) based
on natural-language requests. Uses enable_auto_function_calls so the SDK
handles the tool-call/tool-result loop automatically.
"""
import time

from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import MessageRole, FunctionTool

from config import FOUNDRY_ENDPOINT, MODEL_DEPLOYMENT_NAME
from tools_readonly import get_service_health, search_recent_incidents, get_on_call_engineer


def get_agent_reply(client: AgentsClient, thread_id: str, retries: int = 5) -> str | None:
    """Fetch the agent's reply text, retrying briefly for message-list read-after-write lag."""
    for attempt in range(retries):
        for msg in client.messages.list(thread_id):
            if msg.role == MessageRole.AGENT:
                text = "".join(c.text.value for c in msg.content if hasattr(c, "text"))
                if text:
                    return text
        if attempt < retries - 1:
            time.sleep(1.5)
    return None

TEST_REQUESTS = [
    "Is payment-service healthy in production right now?",
    "What's the health of database-cluster-prod in production?",
    "Check the health of an unknown-service in production",             # unknown service
    "Check payment-service health in the 'prod-typo' environment",      # invalid environment
    "Check the health of slow-service in production",                   # downstream timeout
    "Check the health of throttled-service in production",              # rate-limit response
    "Who is on-call for payment-service, and were there any recent incidents in the last 24 hours?",
]


def main():
    client = AgentsClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())

    functions = FunctionTool({get_service_health, search_recent_incidents, get_on_call_engineer})
    client.enable_auto_function_calls(functions)

    agent = client.create_agent(
        model=MODEL_DEPLOYMENT_NAME,
        name="tool-using-readonly-agent-demo",
        instructions=(
            "You help diagnose incidents using read-only tools: get_service_health, "
            "search_recent_incidents, get_on_call_engineer. Always call the "
            "appropriate tool rather than guessing. If a tool returns an error "
            "(unknown_service, invalid_environment, downstream_timeout, rate_limited, "
            "or malformed/empty data), report that clearly to the user instead of "
            "inventing a plausible-sounding answer."
        ),
        tools=functions.definitions,
    )
    print(f"Created agent: {agent.id}")

    try:
        for request in TEST_REQUESTS:
            thread = client.threads.create()
            client.messages.create(thread.id, role=MessageRole.USER, content=request)
            run = client.runs.create_and_process(thread.id, agent_id=agent.id)

            print(f"\n--- Request: {request}")
            print(f"    Status: {run.status}")
            if run.status == "failed":
                print(f"    Error: {run.last_error}")
                continue

            reply = get_agent_reply(client, thread.id)
            print(f"    Agent: {reply if reply else '(no reply text found after retries)'}")
    finally:
        client.delete_agent(agent.id)
        print(f"\nCleaned up agent {agent.id}")


if __name__ == "__main__":
    main()
