"""Tests for assessment persistence."""

import tempfile
import unittest
from pathlib import Path

from src.database import create_assessment, initialize_database, list_assessments


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


if __name__ == "__main__":
    unittest.main()
