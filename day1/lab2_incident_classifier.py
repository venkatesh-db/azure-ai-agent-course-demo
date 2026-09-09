"""
Lab 2: Create an incident-classification agent.

A basic Foundry agent, invoked through the Python SDK, with no structured
output enforcement yet (that's Lab 3) and no retrieval grounding yet
(that's Lab 4/5). Demonstrates the core agent lifecycle: create agent,
create thread, post message, run, read response.
"""
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import MessageRole

from config import FOUNDRY_ENDPOINT, MODEL_DEPLOYMENT_NAME

TEST_REQUESTS = [
    "Database timeout on database-cluster-prod, connections not releasing",
    "Kubernetes pods for kubernetes-prod are CrashLoopBackOff",
    "payment-service p95 latency climbing, downstream bank API slow",
    "A user says their access to the admin panel was just revoked, is that expected?",
    "Someone found a leaked API key in a public repo",
    "The report generator service is acting weird",  # unknown service
    "Something's broken",  # incomplete request
]


def main():
    client = AgentsClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())

    agent = client.create_agent(
        model=MODEL_DEPLOYMENT_NAME,
        name="incident-classifier-demo",
        instructions=(
            "You classify IT incident reports. For each request, identify: "
            "category (database, network, application, security, unknown), "
            "affected service, and rough severity. "
            "If the request is missing information needed to classify it, "
            "ask a specific clarifying question instead of guessing. "
            "If the request describes a security incident, say it must be "
            "escalated to security on-call and do not attempt remediation."
        ),
    )
    print(f"Created agent: {agent.id}")

    try:
        for request in TEST_REQUESTS:
            thread = client.threads.create()
            client.messages.create(thread.id, role=MessageRole.USER, content=request)
            run = client.runs.create_and_process(thread.id, agent_id=agent.id)

            print(f"\n--- Request: {request}")
            print(f"    Run status: {run.status}")
            if run.status == "failed":
                print(f"    Error: {run.last_error}")
                continue

            messages = client.messages.list(thread.id)
            for msg in messages:
                if msg.role == MessageRole.AGENT:
                    text = "".join(c.text.value for c in msg.content if hasattr(c, "text"))
                    print(f"    Agent: {text}")
                    break
    finally:
        client.delete_agent(agent.id)
        print(f"\nCleaned up agent {agent.id}")


if __name__ == "__main__":
    main()
