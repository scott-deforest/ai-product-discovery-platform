"""OpenAI embedding, Chroma storage, and assessment-scoped retrieval."""

import os
from pathlib import Path
from typing import Optional

import chromadb
from dotenv import load_dotenv
from openai import OpenAI

from src.config import CHROMA_PATH


COLLECTION_NAME = "product_discovery_documents"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


def embedding_model() -> str:
    """Return the configured embedding model."""
    load_dotenv()
    return os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)


def get_collection(chroma_path: Path = CHROMA_PATH):
    """Open the shared local collection used by all assessments."""
    client = chromadb.PersistentClient(path=chroma_path)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def create_embeddings(
    texts: list[str],
    openai_client: Optional[OpenAI] = None,
) -> list[list[float]]:
    """Create one OpenAI embedding for each supplied text."""
    if not texts:
        return []

    load_dotenv()
    client = openai_client or OpenAI()
    response = client.embeddings.create(
        model=embedding_model(),
        input=texts,
        encoding_format="float",
    )
    ordered_embeddings = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered_embeddings]


def index_document_chunks(
    chunks: list[dict[str, object]],
    filename: str,
    collection=None,
    openai_client: Optional[OpenAI] = None,
) -> int:
    """Embed and upsert a document's chunks into Chroma."""
    if not chunks:
        raise ValueError("Create document chunks before indexing.")

    active_collection = collection or get_collection()
    texts = [str(chunk["content"]) for chunk in chunks]
    embeddings = create_embeddings(texts, openai_client)
    document_id = str(chunks[0]["document_id"])
    active_collection.delete(where={"document_id": document_id})
    active_collection.upsert(
        ids=[str(chunk["id"]) for chunk in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[
            {
                "assessment_id": str(chunk["assessment_id"]),
                "document_id": str(chunk["document_id"]),
                "filename": filename,
                "chunk_index": int(chunk["chunk_index"]),
            }
            for chunk in chunks
        ],
    )
    return len(chunks)


def count_indexed_document_chunks(
    document_id: str,
    collection=None,
) -> int:
    """Count the vectors currently stored for one document."""
    active_collection = collection or get_collection()
    result = active_collection.get(
        where={"document_id": document_id},
        include=[],
    )
    return len(result["ids"])


def count_indexed_assessment_chunks(
    assessment_id: str,
    collection=None,
) -> int:
    """Count vectors available to an assessment-scoped retrieval."""
    active_collection = collection or get_collection()
    result = active_collection.get(
        where={"assessment_id": assessment_id},
        include=[],
    )
    return len(result["ids"])


def delete_document_vectors(document_id: str, collection=None) -> None:
    """Remove stale vectors after extraction or chunking changes."""
    active_collection = collection or get_collection()
    active_collection.delete(where={"document_id": document_id})


def search_assessment(
    query: str,
    assessment_id: str,
    limit: int = 3,
    collection=None,
    openai_client: Optional[OpenAI] = None,
) -> list[dict[str, object]]:
    """Return the most relevant chunks from one assessment only."""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Enter a search question.")

    active_collection = collection or get_collection()
    query_embedding = create_embeddings([clean_query], openai_client)[0]
    result = active_collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where={"assessment_id": assessment_id},
        include=["documents", "metadatas", "distances"],
    )

    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    return [
        {
            "content": document,
            "metadata": metadata,
            "distance": distance,
            "similarity": max(0.0, 1.0 - float(distance)),
        }
        for document, metadata, distance in zip(
            documents,
            metadatas,
            distances,
        )
    ]
