"""Tests for assessment readiness rules."""

import tempfile
import unittest
from pathlib import Path

from src.assessment_runner import check_assessment_readiness, start_assessment_run
from src.database import (
    create_assessment,
    create_document,
    get_assessment_run,
    initialize_database,
    list_document_chunks,
    replace_document_chunks,
)
from src.models import RunStatus
from src.vector_store import get_collection


class AssessmentReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "test.db"
        self.collection = get_collection(self.root / "chroma")
        initialize_database(self.database_path)
        self.assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_empty_assessment_is_not_ready(self) -> None:
        readiness = check_assessment_readiness(
            self.assessment_id,
            self.database_path,
            self.collection,
        )

        self.assertFalse(readiness.ready)
        self.assertEqual(readiness.document_count, 0)
        self.assertIn("Upload at least one document.", readiness.reasons)

        with self.assertRaisesRegex(ValueError, "Assessment is not ready"):
            start_assessment_run(
                self.assessment_id,
                "test-model",
                "v1",
                self.database_path,
                self.collection,
            )

    def test_all_current_chunks_must_be_indexed(self) -> None:
        create_document(
            document_id="document-1",
            assessment_id=self.assessment_id,
            filename="workflow.md",
            stored_path="/tmp/workflow.md",
            file_type="md",
            size_bytes=42,
            database_path=self.database_path,
        )
        replace_document_chunks(
            document_id="document-1",
            assessment_id=self.assessment_id,
            chunks=["First support chunk.", "Second support chunk."],
            database_path=self.database_path,
        )
        chunks = list_document_chunks("document-1", self.database_path)
        self.collection.upsert(
            ids=[str(chunk["id"]) for chunk in chunks],
            embeddings=[[1.0, 0.0], [0.9, 0.1]],
            documents=[str(chunk["content"]) for chunk in chunks],
            metadatas=[
                {
                    "assessment_id": self.assessment_id,
                    "document_id": "document-1",
                }
                for _ in chunks
            ],
        )

        readiness = check_assessment_readiness(
            self.assessment_id,
            self.database_path,
            self.collection,
        )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.chunk_count, 2)
        self.assertEqual(readiness.indexed_chunk_count, 2)

        run_id = start_assessment_run(
            self.assessment_id,
            "test-model",
            "v1",
            self.database_path,
            self.collection,
        )
        run = get_assessment_run(run_id, self.database_path)

        self.assertEqual(run["status"], RunStatus.RUNNING.value)
        self.assertIsNotNone(run["started_at"])


if __name__ == "__main__":
    unittest.main()
