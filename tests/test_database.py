"""Tests for assessment persistence."""

import tempfile
import unittest
from pathlib import Path

from src.database import (
    create_assessment,
    create_document,
    initialize_database,
    list_assessments,
    list_documents,
)


class AssessmentDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        initialize_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_create_and_list_assessment(self) -> None:
        assessment_id = create_assessment(
            " Customer Support Workflow ",
            " Evaluate support operations. ",
            self.database_path,
        )

        assessments = list_assessments(self.database_path)

        self.assertEqual(len(assessments), 1)
        self.assertEqual(assessments[0]["id"], assessment_id)
        self.assertEqual(assessments[0]["name"], "Customer Support Workflow")
        self.assertEqual(
            assessments[0]["description"], "Evaluate support operations."
        )
        self.assertEqual(assessments[0]["status"], "draft")

    def test_name_is_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "Assessment name is required"):
            create_assessment("   ", database_path=self.database_path)

    def test_document_belongs_to_assessment(self) -> None:
        assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        create_document(
            document_id="document-123",
            assessment_id=assessment_id,
            filename="workflow.md",
            stored_path="/tmp/workflow.md",
            file_type="md",
            size_bytes=42,
            database_path=self.database_path,
        )

        documents = list_documents(assessment_id, self.database_path)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["filename"], "workflow.md")
        self.assertEqual(documents[0]["assessment_id"], assessment_id)


if __name__ == "__main__":
    unittest.main()
