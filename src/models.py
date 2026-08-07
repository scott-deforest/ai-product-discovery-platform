"""Validated domain models for evidence-grounded assessments."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(str, Enum):
    """Persisted lifecycle states for an assessment run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewDecision(str, Enum):
    """Human decisions available for an AI-generated opportunity."""

    ADVANCE = "advance"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFER = "defer"
    REJECT = "reject"


class AssessmentDimension(str, Enum):
    """Evidence lenses used by the opportunity-assessment workflow."""

    WORKFLOW_PAIN_POINTS = "workflow_pain_points"
    DATA_TECHNICAL_READINESS = "data_technical_readiness"
    BUSINESS_VALUE = "business_value"
    RISK_HUMAN_OVERSIGHT = "risk_human_oversight"


class AssessmentReadiness(BaseModel):
    """Explain whether an assessment has enough indexed evidence to run."""

    model_config = ConfigDict(frozen=True)

    assessment_id: str
    ready: bool
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    reasons: list[str]


class ScoreDetail(BaseModel):
    """One transparent component of the opportunity-scoring rubric."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


class EvidenceCitation(BaseModel):
    """Stable evidence that maps a model claim back to a source chunk."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    excerpt: str = Field(min_length=1)


class EvidenceItem(BaseModel):
    """One deduplicated source chunk in an inspectable evidence pack."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    citation_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    dimensions: list[AssessmentDimension] = Field(min_length=1)
    similarity: float = Field(ge=0.0, le=1.0)


class EvidencePack(BaseModel):
    """Assessment-scoped source material prepared for structured analysis."""

    model_config = ConfigDict(frozen=True)

    assessment_id: str = Field(min_length=1)
    items: list[EvidenceItem] = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_identifiers_must_be_unique(self) -> "EvidencePack":
        citation_ids = [item.citation_id for item in self.items]
        chunk_ids = [item.chunk_id for item in self.items]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("Evidence-pack citation IDs must be unique.")
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("Evidence-pack chunk IDs must be unique.")
        return self


class OpportunityResult(BaseModel):
    """A structured, reviewable AI opportunity recommendation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    proposed_capability: str = Field(min_length=1)
    primary_users: list[str] = Field(min_length=1)
    workflow_placement: str = Field(min_length=1)
    expected_value: str = Field(min_length=1)
    data_requirements: list[str]
    risks: list[str]
    safeguards: list[str]
    success_metrics: list[str]
    missing_information: list[str]
    business_value: ScoreDetail
    feasibility: ScoreDetail
    evidence_strength: ScoreDetail
    risk_readiness: ScoreDetail
    citation_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def citation_ids_must_be_unique(self) -> "OpportunityResult":
        if len(self.citation_ids) != len(set(self.citation_ids)):
            raise ValueError("Opportunity citation IDs must be unique.")
        return self


class OpportunityAnalysis(BaseModel):
    """Model-generated interpretation before trusted evidence is attached."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executive_summary: str = Field(min_length=1)
    opportunities: list[OpportunityResult] = Field(min_length=1, max_length=3)


class AssessmentResult(BaseModel):
    """Complete structured output expected from the Sprint 2 analysis."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executive_summary: str = Field(min_length=1)
    evidence: list[EvidenceCitation] = Field(min_length=1)
    opportunities: list[OpportunityResult] = Field(min_length=1)

    @model_validator(mode="after")
    def opportunities_must_reference_known_evidence(self) -> "AssessmentResult":
        citation_ids = [citation.citation_id for citation in self.evidence]
        if len(citation_ids) != len(set(citation_ids)):
            raise ValueError("Evidence citation IDs must be unique.")

        known_citation_ids = set(citation_ids)
        for opportunity in self.opportunities:
            unknown_ids = set(opportunity.citation_ids) - known_citation_ids
            if unknown_ids:
                unknown_list = ", ".join(sorted(unknown_ids))
                raise ValueError(
                    f"Opportunity references unknown citation IDs: {unknown_list}."
                )
        return self


class RankedOpportunity(OpportunityResult):
    """An opportunity with a deterministic application score and rank."""

    rank: int = Field(ge=1)
    composite_score: float = Field(ge=1.0, le=5.0)


class CompletedAssessment(BaseModel):
    """A generated assessment after scoring and persistence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    run_id: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    evidence: list[EvidenceCitation] = Field(min_length=1)
    opportunities: list[RankedOpportunity] = Field(min_length=1)


class EvaluationRating(BaseModel):
    """A human reviewer's score and explanation for one quality criterion."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


class HumanEvaluation(BaseModel):
    """A review of one pipeline result against the Sprint 3 quality rubric."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = Field(min_length=1)
    pipeline_version: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    evidence_grounding: EvaluationRating
    specificity: EvaluationRating
    actionability: EvaluationRating
    risk_awareness: EvaluationRating
    decision_usefulness: EvaluationRating
    notes: str = ""


class AutomatedEvaluationCheck(BaseModel):
    """One deterministic report-quality check with reviewer-facing guidance."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    check_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    passed: bool
    guidance: str = Field(min_length=1)


class AutomatedEvaluation(BaseModel):
    """Deterministic quality checks that do not claim to judge usefulness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    checks: list[AutomatedEvaluationCheck] = Field(min_length=1)


class EvaluationScore(BaseModel):
    """Transparent aggregate of the five human-review criteria."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    pipeline_version: str = Field(min_length=1)
    overall_score: float = Field(ge=1.0, le=5.0)
    criterion_scores: dict[str, int]


class EvaluationComparison(BaseModel):
    """Difference between two pipeline reviews of the same benchmark case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1)
    baseline_pipeline: str = Field(min_length=1)
    candidate_pipeline: str = Field(min_length=1)
    baseline_score: float = Field(ge=1.0, le=5.0)
    candidate_score: float = Field(ge=1.0, le=5.0)
    score_delta: float = Field(ge=-4.0, le=4.0)
    criterion_deltas: dict[str, int]


class OpportunityReview(BaseModel):
    """One persisted revision of a person's opportunity decision."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    review_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    opportunity_rank: int = Field(ge=1)
    decision: ReviewDecision
    note: str = Field(min_length=1)
    revision: int = Field(ge=1)
    reviewed_at: str = Field(min_length=1)
