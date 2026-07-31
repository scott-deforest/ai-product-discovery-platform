"""Tests for uploaded document storage."""

import tempfile
import unittest
from pathlib import Path

from src.database import create_assessment, initialize_database, list_documents
from src.ingestion import save_uploaded_document


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


if __name__ == "__main__":
    unittest.main()
