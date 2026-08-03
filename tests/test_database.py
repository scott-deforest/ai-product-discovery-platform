"""Tests for assessment persistence."""

import tempfile
import unittest
from pathlib import Path

from src.database import (
    create_assessment,
    create_assessment_run,
    create_document,
    get_assessment_run,
    initialize_database,
    list_assessments,
    list_documents,
    transition_assessment_run,
)
from src.models import RunStatus


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

    def test_assessment_run_lifecycle_is_persisted(self) -> None:
        assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        run_id = create_assessment_run(
            assessment_id=assessment_id,
            model="test-model",
            prompt_version="opportunity-analysis-v1",
            database_path=self.database_path,
        )

        pending_run = get_assessment_run(run_id, self.database_path)
        self.assertEqual(pending_run["status"], RunStatus.PENDING.value)
        self.assertIsNone(pending_run["started_at"])

        transition_assessment_run(
            run_id,
            RunStatus.RUNNING,
            database_path=self.database_path,
        )
        running_run = get_assessment_run(run_id, self.database_path)
        self.assertEqual(running_run["status"], RunStatus.RUNNING.value)
        self.assertIsNotNone(running_run["started_at"])

        transition_assessment_run(
            run_id,
            RunStatus.COMPLETED,
            database_path=self.database_path,
        )
        completed_run = get_assessment_run(run_id, self.database_path)
        self.assertEqual(completed_run["status"], RunStatus.COMPLETED.value)
        self.assertIsNotNone(completed_run["completed_at"])

    def test_completed_run_cannot_transition_again(self) -> None:
        assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        run_id = create_assessment_run(
            assessment_id,
            "test-model",
            "v1",
            self.database_path,
        )
        transition_assessment_run(
            run_id,
            RunStatus.RUNNING,
            database_path=self.database_path,
        )
        transition_assessment_run(
            run_id,
            RunStatus.COMPLETED,
            database_path=self.database_path,
        )

        with self.assertRaisesRegex(ValueError, "Cannot transition"):
            transition_assessment_run(
                run_id,
                RunStatus.FAILED,
                error_message="Too late",
                database_path=self.database_path,
            )

    def test_failed_run_requires_error_message(self) -> None:
        assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        run_id = create_assessment_run(
            assessment_id,
            "test-model",
            "v1",
            self.database_path,
        )

        with self.assertRaisesRegex(ValueError, "requires an error message"):
            transition_assessment_run(
                run_id,
                RunStatus.FAILED,
                database_path=self.database_path,
            )


if __name__ == "__main__":
    unittest.main()
