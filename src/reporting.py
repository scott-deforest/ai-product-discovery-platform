"""Deterministic scoring and ranking for assessment results."""

from src.models import OpportunityResult, RankedOpportunity


SCORE_WEIGHTS = {
    "business_value": 0.35,
    "feasibility": 0.25,
    "evidence_strength": 0.25,
    "risk_readiness": 0.15,
}


def composite_score(opportunity: OpportunityResult) -> float:
    """Apply the published four-part rubric on the original 1–5 scale."""
    score = sum(
        getattr(opportunity, dimension).score * weight
        for dimension, weight in SCORE_WEIGHTS.items()
    )
    return round(score, 2)


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
