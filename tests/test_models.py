"""Tests for structured Sprint 2 assessment models."""

import unittest

from pydantic import ValidationError

from src.models import AssessmentResult, OpportunityResult, ScoreDetail


def opportunity_data() -> dict[str, object]:
    """Return a minimal valid opportunity payload."""
    score = {"score": 4, "rationale": "Supported by workflow evidence."}
    return {
        "title": "Knowledge retrieval assistant",
        "summary": "Help specialists locate relevant support knowledge.",
        "problem": "Specialists repeatedly search several systems.",
        "proposed_capability": "Evidence-grounded semantic search.",
        "primary_users": ["Support specialists"],
        "workflow_placement": "Initial research",
        "expected_value": "Reduce research time and response delays.",
        "data_requirements": ["Knowledge base", "Resolved tickets"],
        "risks": ["Outdated source material"],
        "safeguards": ["Show citations", "Require human review"],
        "success_metrics": ["Median research time"],
        "missing_information": ["Current research-time baseline"],
        "business_value": score,
        "feasibility": score,
        "evidence_strength": score,
        "risk_readiness": score,
        "citation_ids": ["E1"],
    }


class AssessmentModelTests(unittest.TestCase):
    def test_score_must_be_between_one_and_five(self) -> None:
        with self.assertRaises(ValidationError):
            ScoreDetail(score=6, rationale="Too high")

    def test_opportunity_requires_a_citation(self) -> None:
        payload = opportunity_data()
        payload["citation_ids"] = []

        with self.assertRaises(ValidationError):
            OpportunityResult.model_validate(payload)

    def test_opportunity_must_reference_known_evidence(self) -> None:
        payload = opportunity_data()
        payload["citation_ids"] = ["UNKNOWN"]

        with self.assertRaisesRegex(ValidationError, "unknown citation"):
            AssessmentResult.model_validate(
                {
                    "executive_summary": "Support analysis.",
                    "evidence": [
                        {
                            "citation_id": "E1",
                            "document_id": "document-1",
                            "chunk_id": "document-1-chunk-0",
                            "filename": "workflow.md",
                            "chunk_index": 0,
                            "excerpt": "Specialists search several systems.",
                        }
                    ],
                    "opportunities": [payload],
                }
            )


if __name__ == "__main__":
    unittest.main()
