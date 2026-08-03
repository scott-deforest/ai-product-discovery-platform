"""Validated domain models for evidence-grounded assessments."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(str, Enum):
    """Persisted lifecycle states for an assessment run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


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

    model_config = ConfigDict(str_strip_whitespace=True)

    score: int = Field(ge=1, le=5)
    rationale: str = Field(min_length=1)


class EvidenceCitation(BaseModel):
    """Stable evidence that maps a model claim back to a source chunk."""

    model_config = ConfigDict(str_strip_whitespace=True)

    citation_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    excerpt: str = Field(min_length=1)


class OpportunityResult(BaseModel):
    """A structured, reviewable AI opportunity recommendation."""

    model_config = ConfigDict(str_strip_whitespace=True)

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


class AssessmentResult(BaseModel):
    """Complete structured output expected from the Sprint 2 analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

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
