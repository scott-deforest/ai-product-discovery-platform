"""Tests for persistent human review decisions."""

import tempfile
import unittest
from pathlib import Path

from src.database import (
    create_assessment,
    create_assessment_run,
    create_document,
    initialize_database,
    list_latest_opportunity_reviews,
    list_opportunity_review_history,
    replace_document_chunks,
    save_assessment_result,
    save_opportunity_review,
    transition_assessment_run,
)
from src.models import AssessmentResult, ReviewDecision, RunStatus
from src.reporting import rank_opportunities


class OpportunityReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        initialize_database(self.database_path)
        self.run_id = self._create_completed_report()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _create_completed_report(self) -> str:
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
        save_assessment_result(
            run_id,
            result,
            rank_opportunities(result.opportunities),
            self.database_path,
        )
        return run_id

    def test_decision_and_note_are_persisted(self) -> None:
        saved = save_opportunity_review(
            self.run_id,
            1,
            ReviewDecision.ADVANCE,
            " Validate retrieval time and answer quality in a bounded pilot. ",
            self.database_path,
        )

        latest = list_latest_opportunity_reviews(
            self.run_id,
            self.database_path,
        )

        self.assertEqual(saved.revision, 1)
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0].decision, ReviewDecision.ADVANCE)
        self.assertEqual(
            latest[0].note,
            "Validate retrieval time and answer quality in a bounded pilot.",
        )

    def test_changed_decision_preserves_revision_history(self) -> None:
        save_opportunity_review(
            self.run_id,
            1,
            ReviewDecision.ADVANCE,
            "The evidence supports a pilot.",
            self.database_path,
        )
        updated = save_opportunity_review(
            self.run_id,
            1,
            ReviewDecision.NEEDS_EVIDENCE,
            "Confirm the current research-time baseline first.",
            self.database_path,
        )

        history = list_opportunity_review_history(
            self.run_id,
            1,
            self.database_path,
        )
        latest = list_latest_opportunity_reviews(
            self.run_id,
            self.database_path,
        )

        self.assertEqual(updated.revision, 2)
        self.assertEqual([review.revision for review in history], [2, 1])
        self.assertEqual(latest[0].decision, ReviewDecision.NEEDS_EVIDENCE)

    def test_decision_requires_an_explanatory_note(self) -> None:
        with self.assertRaisesRegex(ValueError, "note explaining"):
            save_opportunity_review(
                self.run_id,
                1,
                ReviewDecision.REJECT,
                "   ",
                self.database_path,
            )

    def test_decision_rejects_an_unknown_opportunity(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not exist"):
            save_opportunity_review(
                self.run_id,
                99,
                ReviewDecision.DEFER,
                "This rank is not present.",
                self.database_path,
            )


if __name__ == "__main__":
    unittest.main()
