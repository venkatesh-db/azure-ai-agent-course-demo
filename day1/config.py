import os
from pathlib import Path
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FOUNDRY_ENDPOINT = os.environ["FOUNDRY_ENDPOINT"]
MODEL_DEPLOYMENT_NAME = os.environ["MODEL_DEPLOYMENT_NAME"]
EMBEDDING_DEPLOYMENT_NAME = os.environ["EMBEDDING_DEPLOYMENT_NAME"]
SEARCH_ENDPOINT = os.environ["SEARCH_ENDPOINT"]
SEARCH_INDEX_NAME = "runbooks"

# The AIServices resource behind the Foundry project — derived from
# FOUNDRY_ENDPOINT ("https://<resource>.services.ai.azure.com/api/projects/<project>")
# because the project-scoped OpenAI client (AIProjectClient.get_openai_client())
# only proxies chat/agent calls, not /embeddings. Embeddings need the raw
# Cognitive Services resource endpoint instead.
_RESOURCE_NAME = FOUNDRY_ENDPOINT.split("//")[1].split(".")[0]
COGNITIVE_SERVICES_ENDPOINT = f"https://{_RESOURCE_NAME}.cognitiveservices.azure.com/"


def get_embedding_client() -> AzureOpenAI:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=COGNITIVE_SERVICES_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-10-21",
    )
