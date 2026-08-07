"""Tests for Sprint 3 assessment-quality evaluation."""

import unittest

from src.evaluation import (
    compare_evaluations,
    evaluate_report_structure,
    score_human_evaluation,
)
from src.models import AssessmentResult, HumanEvaluation


def assessment_result(**opportunity_overrides) -> AssessmentResult:
    """Create a compact valid report for deterministic quality checks."""
    score = {"score": 4, "rationale": "The source material supports this score."}
    opportunity = {
        "title": "Knowledge retrieval assistant",
        "summary": "Help specialists find approved knowledge.",
        "problem": "Research is repeated across several systems.",
        "proposed_capability": "Evidence-grounded semantic retrieval.",
        "primary_users": ["Support specialists"],
        "workflow_placement": "Initial research",
        "expected_value": "Reduce research time.",
        "data_requirements": ["Approved knowledge articles"],
        "risks": ["Outdated content"],
        "safeguards": ["Display sources and require human review"],
        "success_metrics": ["Median research time"],
        "missing_information": ["Current research-time baseline"],
        "business_value": score,
        "feasibility": score,
        "evidence_strength": score,
        "risk_readiness": score,
        "citation_ids": ["E1"],
    }
    opportunity.update(opportunity_overrides)
    return AssessmentResult(
        executive_summary="The workflow contains a bounded retrieval opportunity.",
        evidence=[
            {
                "citation_id": "E1",
                "document_id": "document-1",
                "chunk_id": "document-1-chunk-0",
                "filename": "workflow.md",
                "chunk_index": 0,
                "excerpt": "Specialists repeatedly search several systems.",
            }
        ],
        opportunities=[opportunity],
    )


def human_evaluation(
    pipeline_version: str,
    scores: tuple[int, int, int, int, int],
    case_id: str = "customer-support",
) -> HumanEvaluation:
    """Create a review using the five published criteria."""
    rating_names = (
        "evidence_grounding",
        "specificity",
        "actionability",
        "risk_awareness",
        "decision_usefulness",
    )
    ratings = {
        name: {"score": score, "rationale": f"Reviewer assigned {score}."}
        for name, score in zip(rating_names, scores)
    }
    return HumanEvaluation(
        case_id=case_id,
        pipeline_version=pipeline_version,
        reviewer="Test reviewer",
        **ratings,
    )


class AutomatedEvaluationTests(unittest.TestCase):
    def test_complete_report_passes_every_automatic_check(self) -> None:
        evaluation = evaluate_report_structure(assessment_result())

        self.assertTrue(evaluation.passed)
        self.assertTrue(all(check.passed for check in evaluation.checks))

    def test_missing_safeguard_returns_plain_language_guidance(self) -> None:
        evaluation = evaluate_report_structure(
            assessment_result(safeguards=[]),
        )

        safeguard_check = next(
            check
            for check in evaluation.checks
            if check.check_id == "safeguards_identified"
        )
        self.assertFalse(evaluation.passed)
        self.assertFalse(safeguard_check.passed)
        self.assertIn("practical safeguard", safeguard_check.guidance)


class HumanEvaluationTests(unittest.TestCase):
    def test_five_criteria_are_equally_weighted(self) -> None:
        evaluation = human_evaluation("sprint-2", (5, 4, 3, 2, 1))

        score = score_human_evaluation(evaluation)

        self.assertEqual(score.overall_score, 3.0)
        self.assertEqual(score.criterion_scores["specificity"], 4)

    def test_comparison_reports_overall_and_criterion_changes(self) -> None:
        baseline = human_evaluation("sprint-2", (3, 3, 3, 4, 3))
        candidate = human_evaluation("sprint-3-specialists", (4, 4, 3, 5, 4))

        comparison = compare_evaluations(baseline, candidate)

        self.assertEqual(comparison.baseline_score, 3.2)
        self.assertEqual(comparison.candidate_score, 4.0)
        self.assertEqual(comparison.score_delta, 0.8)
        self.assertEqual(comparison.criterion_deltas["actionability"], 0)

    def test_comparison_rejects_different_benchmark_cases(self) -> None:
        baseline = human_evaluation("sprint-2", (3, 3, 3, 3, 3))
        candidate = human_evaluation(
            "sprint-3-specialists",
            (4, 4, 4, 4, 4),
            case_id="invoice-processing",
        )

        with self.assertRaisesRegex(ValueError, "same benchmark case"):
            compare_evaluations(baseline, candidate)


if __name__ == "__main__":
    unittest.main()
