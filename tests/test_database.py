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
    list_opportunity_evidence,
    list_run_opportunities,
    list_documents,
    load_completed_assessment,
    replace_document_chunks,
    save_assessment_result,
    transition_assessment_run,
)
from src.models import AssessmentResult, RunStatus
from src.reporting import rank_opportunities


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

    def test_ranked_assessment_result_is_saved_atomically(self) -> None:
        assessment_id = create_assessment(
            "Customer Support Workflow",
            database_path=self.database_path,
        )
        create_document(
            "document-1",
            assessment_id,
            "workflow.md",
            "/tmp/workflow.md",
            "md",
            42,
            self.database_path,
        )
        replace_document_chunks(
            "document-1",
            assessment_id,
            ["Specialists repeatedly search several systems."],
            self.database_path,
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
        score = {"score": 4, "rationale": "Supported by evidence."}
        result = AssessmentResult.model_validate(
            {
                "executive_summary": "A focused opportunity is available.",
                "evidence": [
                    {
                        "citation_id": "E1",
                        "document_id": "document-1",
                        "chunk_id": "document-1-chunk-0",
                        "filename": "workflow.md",
                        "chunk_index": 0,
                        "excerpt": "Specialists repeatedly search several systems.",
                    }
                ],
                "opportunities": [
                    {
                        "title": "Knowledge retrieval assistant",
                        "summary": "Help specialists find approved knowledge.",
                        "problem": "Specialists search several systems.",
                        "proposed_capability": "Cited semantic retrieval.",
                        "primary_users": ["Support specialists"],
                        "workflow_placement": "Issue research",
                        "expected_value": "Reduce repeated searches.",
                        "data_requirements": ["Approved knowledge"],
                        "risks": ["Outdated sources"],
                        "safeguards": ["Human review"],
                        "success_metrics": ["Median research time"],
                        "missing_information": ["Current baseline"],
                        "business_value": score,
                        "feasibility": score,
                        "evidence_strength": score,
                        "risk_readiness": score,
                        "citation_ids": ["E1"],
                    }
                ],
            }
        )

        ranked = rank_opportunities(result.opportunities)
        save_assessment_result(run_id, result, ranked, self.database_path)

        saved_run = get_assessment_run(run_id, self.database_path)
        saved_opportunities = list_run_opportunities(run_id, self.database_path)
        saved_evidence = list_opportunity_evidence(
            str(saved_opportunities[0]["id"]),
            self.database_path,
        )
        self.assertEqual(saved_run["status"], RunStatus.COMPLETED.value)
        self.assertEqual(
            saved_run["executive_summary"],
            "A focused opportunity is available.",
        )
        self.assertEqual(saved_opportunities[0]["rank"], 1)
        self.assertEqual(saved_opportunities[0]["composite_score"], 4.0)
        self.assertEqual(
            saved_opportunities[0]["primary_users"],
            ["Support specialists"],
        )
        self.assertEqual(saved_evidence[0]["citation_id"], "E1")

        reloaded_report = load_completed_assessment(run_id, self.database_path)
        self.assertEqual(reloaded_report.run_id, run_id)
        self.assertEqual(len(reloaded_report.opportunities), 1)
        self.assertEqual(
            reloaded_report.opportunities[0].title,
            "Knowledge retrieval assistant",
        )
        self.assertEqual(reloaded_report.opportunities[0].citation_ids, ["E1"])
        self.assertEqual(reloaded_report.evidence[0].chunk_id, "document-1-chunk-0")


if __name__ == "__main__":
    unittest.main()
