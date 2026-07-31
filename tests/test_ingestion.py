"""Tests for uploaded document storage."""

import tempfile
import unittest
from pathlib import Path

from src.database import (
    create_assessment,
    get_document_extraction,
    initialize_database,
    list_documents,
)
from src.ingestion import (
    extract_and_save_document,
    extract_text,
    read_extracted_text,
    save_uploaded_document,
)


class DocumentStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "test.db"
        self.uploads_path = self.root / "uploads"
        initialize_database(self.database_path)
        self.assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_save_uploaded_document(self) -> None:
        content = b"# Customer Support Workflow\n\nSample content."

        document_id = save_uploaded_document(
            self.assessment_id,
            "customer_support_workflow.md",
            content,
            uploads_path=self.uploads_path,
            database_path=self.database_path,
        )

        documents = list_documents(self.assessment_id, self.database_path)
        stored_path = Path(str(documents[0]["stored_path"]))

        self.assertEqual(documents[0]["id"], document_id)
        self.assertEqual(documents[0]["size_bytes"], len(content))
        self.assertEqual(stored_path.read_bytes(), content)

    def test_reject_unsupported_file_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported file type"):
            save_uploaded_document(
                self.assessment_id,
                "malware.exe",
                b"not allowed",
                uploads_path=self.uploads_path,
                database_path=self.database_path,
            )

    def test_extract_markdown_text(self) -> None:
        markdown_path = self.root / "workflow.md"
        markdown_path.write_text("# Workflow\n\nReview each request.", encoding="utf-8")

        text = extract_text(markdown_path, "md")

        self.assertEqual(text, "# Workflow\n\nReview each request.")

    def test_extract_and_save_document(self) -> None:
        content = b"# Workflow\n\nReview each request."
        document_id = save_uploaded_document(
            self.assessment_id,
            "workflow.md",
            content,
            uploads_path=self.uploads_path,
            database_path=self.database_path,
        )
        document = list_documents(self.assessment_id, self.database_path)[0]

        text_path = extract_and_save_document(
            document_id=document_id,
            assessment_id=self.assessment_id,
            stored_path=str(document["stored_path"]),
            file_type=str(document["file_type"]),
            processed_path=self.root / "processed",
            database_path=self.database_path,
        )
        extraction = get_document_extraction(document_id, self.database_path)

        self.assertIsNotNone(extraction)
        self.assertEqual(read_extracted_text(text_path), content.decode())
        self.assertEqual(extraction["character_count"], len(content.decode()))

    def test_empty_document_is_rejected(self) -> None:
        empty_path = self.root / "empty.txt"
        empty_path.write_text("   ", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "No readable text"):
            extract_text(empty_path, "txt")


if __name__ == "__main__":
    unittest.main()
