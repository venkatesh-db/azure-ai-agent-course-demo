"""
Lab 4: Build the search index.

Loads the runbook dataset, generates embeddings via the deployed embedding
model, and indexes into Azure AI Search with both keyword (BM25) and vector
fields so we can demonstrate hybrid retrieval in Lab 5.
"""
import json
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

from config import EMBEDDING_DEPLOYMENT_NAME, SEARCH_ENDPOINT, SEARCH_INDEX_NAME, get_embedding_client

DATASET_PATH = Path(__file__).parent / "dataset" / "runbooks.json"
EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small default dimension


def create_index(index_client: SearchIndexClient):
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="service", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="status", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="default-vector-profile",
        ),
    ]
    vector_search = VectorSearch(
        profiles=[VectorSearchProfile(name="default-vector-profile", algorithm_configuration_name="default-hnsw")],
        algorithms=[HnswAlgorithmConfiguration(name="default-hnsw")],
    )
    index = SearchIndex(name=SEARCH_INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print(f"Index '{SEARCH_INDEX_NAME}' created/updated.")


def embed(openai_client, texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(model=EMBEDDING_DEPLOYMENT_NAME, input=texts)
    return [d.embedding for d in response.data]


def main():
    credential = DefaultAzureCredential()

    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
    create_index(index_client)

    docs = json.loads(DATASET_PATH.read_text())
    print(f"Loaded {len(docs)} documents (including 1 obsolete + 1 malicious, for later lab tests).")

    openai_client = get_embedding_client()

    print("Generating embeddings...")
    vectors = embed(openai_client, [d["content"] for d in docs])

    search_docs = [
        {
            "id": d["id"],
            "title": d["title"],
            "content": d["content"],
            "service": d["service"],
            "status": d["status"],
            "content_vector": vector,
        }
        for d, vector in zip(docs, vectors)
    ]

    search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=SEARCH_INDEX_NAME, credential=credential)
    result = search_client.upload_documents(documents=search_docs)
    failed = [r for r in result if not r.succeeded]
    print(f"Indexed {len(result) - len(failed)}/{len(result)} documents.")
    if failed:
        print(f"Failed: {[r.key for r in failed]}")


if __name__ == "__main__":
    main()
