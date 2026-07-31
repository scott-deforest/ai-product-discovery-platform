"""Tests for embedding, indexing, and assessment-scoped retrieval."""

import tempfile
import unittest
from pathlib import Path

from src.vector_store import (
    count_indexed_document_chunks,
    get_collection,
    index_document_chunks,
    search_assessment,
)


class FakeEmbedding:
    def __init__(self, index: int, text: str) -> None:
        self.index = index
        lowered = text.lower()
        self.embedding = [
            float("support" in lowered),
            float("billing" in lowered),
            1.0,
        ]


class FakeEmbeddingResponse:
    def __init__(self, texts: list[str]) -> None:
        self.data = [FakeEmbedding(index, text) for index, text in enumerate(texts)]


class FakeEmbeddingsResource:
    def create(self, *, input, **kwargs):
        texts = [input] if isinstance(input, str) else list(input)
        return FakeEmbeddingResponse(texts)


class FakeOpenAI:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsResource()


class VectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.collection = get_collection(Path(self.temporary_directory.name))
        self.openai_client = FakeOpenAI()
        self.chunks = [
            {
                "id": "document-1-chunk-0",
                "document_id": "document-1",
                "assessment_id": "assessment-1",
                "chunk_index": 0,
                "content": "Support specialists search several systems.",
            },
            {
                "id": "document-1-chunk-1",
                "document_id": "document-1",
                "assessment_id": "assessment-1",
                "chunk_index": 1,
                "content": "Billing questions use response templates.",
            },
        ]

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_index_document_chunks(self) -> None:
        indexed_count = index_document_chunks(
            self.chunks,
            filename="workflow.md",
            collection=self.collection,
            openai_client=self.openai_client,
        )

        self.assertEqual(indexed_count, 2)
        self.assertEqual(
            count_indexed_document_chunks("document-1", self.collection),
            2,
        )

    def test_search_is_filtered_to_assessment(self) -> None:
        index_document_chunks(
            self.chunks,
            filename="workflow.md",
            collection=self.collection,
            openai_client=self.openai_client,
        )
        other_assessment_chunk = [
            {
                "id": "document-2-chunk-0",
                "document_id": "document-2",
                "assessment_id": "assessment-2",
                "chunk_index": 0,
                "content": "Support content from another assessment.",
            }
        ]
        index_document_chunks(
            other_assessment_chunk,
            filename="other.md",
            collection=self.collection,
            openai_client=self.openai_client,
        )

        results = search_assessment(
            "support delays",
            "assessment-1",
            collection=self.collection,
            openai_client=self.openai_client,
        )

        self.assertTrue(results)
        self.assertTrue(
            all(
                result["metadata"]["assessment_id"] == "assessment-1"
                for result in results
            )
        )


if __name__ == "__main__":
    unittest.main()
