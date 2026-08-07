"""Evaluation tools for comparing assessment-pipeline quality."""

from typing import Union

from src.models import (
    AssessmentResult,
    AutomatedEvaluation,
    AutomatedEvaluationCheck,
    CompletedAssessment,
    EvaluationComparison,
    EvaluationScore,
    HumanEvaluation,
)


EVALUATION_CRITERIA = (
    "evidence_grounding",
    "specificity",
    "actionability",
    "risk_awareness",
    "decision_usefulness",
)


def evaluate_report_structure(
    result: Union[AssessmentResult, CompletedAssessment],
) -> AutomatedEvaluation:
    """Check objective report requirements without pretending to judge quality."""
    opportunities = result.opportunities
    titles = [opportunity.title.casefold() for opportunity in opportunities]
    used_citations = {
        citation_id
        for opportunity in opportunities
        for citation_id in opportunity.citation_ids
    }

    checks = [
        _check(
            "opportunity_count",
            "The report contains one to three focused opportunities.",
            1 <= len(opportunities) <= 3,
            "Keep the assessment focused on no more than three opportunities.",
        ),
        _check(
            "distinct_opportunities",
            "Each opportunity is distinct.",
            len(titles) == len(set(titles)),
            "Remove or combine opportunities with duplicate titles.",
        ),
        _check(
            "evidence_used",
            "The report uses source evidence.",
            bool(used_citations),
            "Connect every recommendation to evidence from the uploaded documents.",
        ),
        _check(
            "risks_identified",
            "Every opportunity identifies at least one risk.",
            all(opportunity.risks for opportunity in opportunities),
            "Identify what could make each opportunity harmful or unsuccessful.",
        ),
        _check(
            "safeguards_identified",
            "Every opportunity identifies at least one safeguard.",
            all(opportunity.safeguards for opportunity in opportunities),
            "Add a practical safeguard for every opportunity.",
        ),
        _check(
            "success_measures_identified",
            "Every opportunity includes a measurable success signal.",
            all(opportunity.success_metrics for opportunity in opportunities),
            "Define how a pilot would demonstrate measurable value.",
        ),
        _check(
            "uncertainty_identified",
            "Every opportunity states what still needs to be learned.",
            all(opportunity.missing_information for opportunity in opportunities),
            "State the missing information that should be validated before investment.",
        ),
    ]
    return AutomatedEvaluation(
        passed=all(check.passed for check in checks),
        checks=checks,
    )


def score_human_evaluation(evaluation: HumanEvaluation) -> EvaluationScore:
    """Average the five equally weighted reviewer scores on the original scale."""
    criterion_scores = {
        criterion: getattr(evaluation, criterion).score
        for criterion in EVALUATION_CRITERIA
    }
    overall_score = round(
        sum(criterion_scores.values()) / len(criterion_scores),
        2,
    )
    return EvaluationScore(
        case_id=evaluation.case_id,
        pipeline_version=evaluation.pipeline_version,
        overall_score=overall_score,
        criterion_scores=criterion_scores,
    )


def compare_evaluations(
    baseline: HumanEvaluation,
    candidate: HumanEvaluation,
) -> EvaluationComparison:
    """Compare two reviews only when they describe the same benchmark case."""
    if baseline.case_id != candidate.case_id:
        raise ValueError("Evaluations must use the same benchmark case.")
    if baseline.pipeline_version == candidate.pipeline_version:
        raise ValueError("Evaluations must use different pipeline versions.")

    baseline_score = score_human_evaluation(baseline)
    candidate_score = score_human_evaluation(candidate)
    return EvaluationComparison(
        case_id=baseline.case_id,
        baseline_pipeline=baseline.pipeline_version,
        candidate_pipeline=candidate.pipeline_version,
        baseline_score=baseline_score.overall_score,
        candidate_score=candidate_score.overall_score,
        score_delta=round(
            candidate_score.overall_score - baseline_score.overall_score,
            2,
        ),
        criterion_deltas={
            criterion: (
                candidate_score.criterion_scores[criterion]
                - baseline_score.criterion_scores[criterion]
            )
            for criterion in EVALUATION_CRITERIA
        },
    )


def _check(
    check_id: str,
    label: str,
    passed: bool,
    guidance: str,
) -> AutomatedEvaluationCheck:
    return AutomatedEvaluationCheck(
        check_id=check_id,
        label=label,
        passed=passed,
        guidance=guidance,
    )
