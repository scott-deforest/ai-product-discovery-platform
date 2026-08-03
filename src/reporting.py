"""Deterministic scoring and ranking for assessment results."""

from src.models import OpportunityResult, RankedOpportunity


SCORE_WEIGHTS = {
    "business_value": 0.35,
    "feasibility": 0.25,
    "evidence_strength": 0.25,
    "risk_readiness": 0.15,
}

SCORE_BANDS = (
    (1.5, "Weak candidate", "The evidence does not currently support prioritizing it."),
    (2.5, "Limited potential", "Important value, feasibility, evidence, or risk gaps remain."),
    (3.5, "Worth exploring", "It merits further discovery before a pilot decision."),
    (4.5, "Strong pilot candidate", "It is a good candidate for a bounded, measured pilot."),
    (5.01, "High-priority validation candidate", "Validate assumptions and safeguards promptly."),
)


def composite_score(opportunity: OpportunityResult) -> float:
    """Apply the published four-part rubric on the original 1–5 scale."""
    score = sum(
        getattr(opportunity, dimension).score * weight
        for dimension, weight in SCORE_WEIGHTS.items()
    )
    return round(score, 2)


def score_interpretation(score: float) -> tuple[str, str]:
    """Translate a 1–5 composite score into non-directive decision guidance."""
    if score < 1.0 or score > 5.0:
        raise ValueError("Composite score must be between 1 and 5.")
    for upper_bound, label, guidance in SCORE_BANDS:
        if score < upper_bound:
            return label, guidance
    raise AssertionError("Score bands do not cover the valid score range.")


def rank_opportunities(
    opportunities: list[OpportunityResult],
) -> list[RankedOpportunity]:
    """Rank opportunities consistently, including deterministic tie-breaking."""
    if not opportunities:
        raise ValueError("At least one opportunity is required for ranking.")

    scored = [
        (composite_score(opportunity), opportunity)
        for opportunity in opportunities
    ]
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1].evidence_strength.score,
            -item[1].business_value.score,
            item[1].title.casefold(),
        )
    )
    return [
        RankedOpportunity(
            **opportunity.model_dump(),
            rank=rank,
            composite_score=score,
        )
        for rank, (score, opportunity) in enumerate(scored, start=1)
    ]
