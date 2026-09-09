"""
Lab 1: Verify the Azure environment.

Authenticates with Azure, connects to the Foundry project, validates the
deployed model is reachable, invokes it once, and reports latency + token
usage. Run this first on any machine before the other labs — it's the
fastest way to prove credentials and quotas are working.
"""
import time

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

from config import FOUNDRY_ENDPOINT, MODEL_DEPLOYMENT_NAME


def main():
    print(f"Connecting to Foundry project: {FOUNDRY_ENDPOINT}")
    project = AIProjectClient(endpoint=FOUNDRY_ENDPOINT, credential=DefaultAzureCredential())

    print(f"Requesting OpenAI-compatible client for deployment: {MODEL_DEPLOYMENT_NAME}")
    client = project.get_openai_client()

    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=MODEL_DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": "Reply with exactly: environment ok"}],
        )
    except Exception as exc:
        print(f"FAILED to invoke model: {exc}")
        print("Check: az login, RBAC role assignment, model deployment name, quota.")
        raise
    latency_ms = (time.perf_counter() - start) * 1000

    print("\n--- Result ---")
    print("Response:", response.choices[0].message.content)
    print(f"Latency: {latency_ms:.0f} ms")
    if response.usage:
        print(f"Tokens: prompt={response.usage.prompt_tokens} "
              f"completion={response.usage.completion_tokens} "
              f"total={response.usage.total_tokens}")
    print("\nEnvironment verified.")


if __name__ == "__main__":
    main()
