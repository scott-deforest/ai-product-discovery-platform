"""Tests for deterministic opportunity scoring and ranking."""

import unittest

from src.models import OpportunityResult
from src.reporting import composite_score, rank_opportunities


def opportunity(title: str, business: int, feasibility: int, evidence: int, risk: int):
    """Create a compact opportunity fixture with distinct component scores."""
    def score(value: int) -> dict[str, object]:
        return {"score": value, "rationale": f"Score is {value}."}

    return OpportunityResult(
        title=title,
        summary="A concise summary.",
        problem="A supported workflow problem.",
        proposed_capability="A narrow AI capability.",
        primary_users=["Specialist"],
        workflow_placement="Research",
        expected_value="Reduce avoidable effort.",
        data_requirements=["Approved source material"],
        risks=["Incorrect output"],
        safeguards=["Human review"],
        success_metrics=["Task time"],
        missing_information=["Current baseline"],
        business_value=score(business),
        feasibility=score(feasibility),
        evidence_strength=score(evidence),
        risk_readiness=score(risk),
        citation_ids=["E1"],
    )


class OpportunityRankingTests(unittest.TestCase):
    def test_composite_score_uses_published_weights(self) -> None:
        candidate = opportunity("Candidate", 5, 4, 3, 2)

        self.assertEqual(composite_score(candidate), 3.8)

    def test_opportunities_are_ranked_by_composite_score(self) -> None:
        lower = opportunity("Lower", 2, 2, 2, 2)
        higher = opportunity("Higher", 5, 4, 4, 3)

        ranked = rank_opportunities([lower, higher])

        self.assertEqual([item.title for item in ranked], ["Higher", "Lower"])
        self.assertEqual([item.rank for item in ranked], [1, 2])

    def test_ties_are_resolved_deterministically(self) -> None:
        beta = opportunity("Beta", 4, 4, 4, 4)
        alpha = opportunity("Alpha", 4, 4, 4, 4)

        ranked = rank_opportunities([beta, alpha])

        self.assertEqual([item.title for item in ranked], ["Alpha", "Beta"])


if __name__ == "__main__":
    unittest.main()
