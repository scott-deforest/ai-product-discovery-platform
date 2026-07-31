"""Tests for deterministic document chunking."""

import tempfile
import unittest
from pathlib import Path

from src.chunking import chunk_text
from src.database import (
    create_assessment,
    create_document,
    initialize_database,
    list_document_chunks,
    replace_document_chunks,
)


class ChunkTextTests(unittest.TestCase):
    def test_chunks_have_expected_overlap(self) -> None:
        text = " ".join(f"word-{index}" for index in range(10))

        chunks = chunk_text(text, chunk_size=5, overlap=2)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[0].split(), [f"word-{i}" for i in range(5)])
        self.assertEqual(chunks[1].split(), [f"word-{i}" for i in range(3, 8)])
        self.assertEqual(chunks[2].split(), [f"word-{i}" for i in range(6, 10)])

    def test_original_whitespace_is_preserved(self) -> None:
        text = "# Heading\n\nFirst paragraph.\n\nSecond paragraph."

        chunks = chunk_text(text, chunk_size=20, overlap=2)

        self.assertEqual(chunks, [text])

    def test_invalid_overlap_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Overlap"):
            chunk_text("sample text", chunk_size=10, overlap=10)


class ChunkDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        initialize_database(self.database_path)
        self.assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        self.document_id = "document-123"
        create_document(
            document_id=self.document_id,
            assessment_id=self.assessment_id,
            filename="workflow.md",
            stored_path="/tmp/workflow.md",
            file_type="md",
            size_bytes=42,
            database_path=self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_replace_and_list_chunks(self) -> None:
        replace_document_chunks(
            document_id=self.document_id,
            assessment_id=self.assessment_id,
            chunks=["first chunk", "second chunk"],
            database_path=self.database_path,
        )

        chunks = list_document_chunks(self.document_id, self.database_path)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["id"], "document-123-chunk-0")
        self.assertEqual(chunks[1]["chunk_index"], 1)
        self.assertEqual(chunks[1]["word_count"], 2)


if __name__ == "__main__":
    unittest.main()
