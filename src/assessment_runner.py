"""Assessment readiness checks and workflow orchestration."""

import logging
from typing import Callable, Optional

from src.config import DATABASE_PATH
from src.database import (
    DatabasePath,
    count_assessment_chunks,
    create_assessment_run,
    get_assessment,
    list_documents,
    transition_assessment_run,
)
from src.models import (
    AssessmentDimension,
    AssessmentReadiness,
    EvidenceItem,
    EvidencePack,
    RunStatus,
)
from src.vector_store import count_indexed_assessment_chunks, search_assessment


LOGGER = logging.getLogger(__name__)

EVIDENCE_QUERIES = {
    AssessmentDimension.WORKFLOW_PAIN_POINTS: (
        "What repetitive work, delays, handoff problems, inconsistent decisions, "
        "information-search problems, or visibility gaps occur in this workflow?"
    ),
    AssessmentDimension.DATA_TECHNICAL_READINESS: (
        "What data, systems, integrations, data-quality issues, technical "
        "constraints, or measurable signals are available for an AI solution?"
    ),
    AssessmentDimension.BUSINESS_VALUE: (
        "What business outcomes, users, volumes, costs, delays, quality problems, "
        "or success measures indicate where AI could create value?"
    ),
    AssessmentDimension.RISK_HUMAN_OVERSIGHT: (
        "What privacy, security, compliance, accuracy, human-review, escalation, "
        "or explainability requirements constrain AI use?"
    ),
}


def check_assessment_readiness(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
    collection=None,
) -> AssessmentReadiness:
    """Explain whether an assessment is ready for evidence-grounded analysis."""
    if get_assessment(assessment_id, database_path) is None:
        raise ValueError(f"Assessment not found: {assessment_id}.")

    document_count = len(list_documents(assessment_id, database_path))
    chunk_count = count_assessment_chunks(assessment_id, database_path)
    indexed_chunk_count = count_indexed_assessment_chunks(
        assessment_id,
        collection,
    )
    reasons = []

    if document_count == 0:
        reasons.append(
            "This assessment needs at least one document before it can run."
        )
    elif chunk_count == 0:
        reasons.append(
            "Finish preparing the uploaded documents by extracting their text "
            "and creating searchable sections."
        )
    elif indexed_chunk_count == 0:
        reasons.append(
            'Finish preparing the documents by selecting "Index chunks."'
        )
    elif indexed_chunk_count != chunk_count:
        reasons.append(
            "A document changed after it was prepared. Select "
            '"Re-index chunks" before running the assessment.'
        )

    LOGGER.info(
        "assessment_readiness assessment_id=%s documents=%d chunks=%d "
        "indexed_chunks=%d ready=%s",
        assessment_id,
        document_count,
        chunk_count,
        indexed_chunk_count,
        not reasons,
    )

    return AssessmentReadiness(
        assessment_id=assessment_id,
        ready=not reasons,
        document_count=document_count,
        chunk_count=chunk_count,
        indexed_chunk_count=indexed_chunk_count,
        reasons=reasons,
    )


def start_assessment_run(
    assessment_id: str,
    model: str,
    prompt_version: str,
    database_path: DatabasePath = DATABASE_PATH,
    collection=None,
) -> str:
    """Start a persisted run only when all current chunks are indexed."""
    readiness = check_assessment_readiness(
        assessment_id,
        database_path,
        collection,
    )
    if not readiness.ready:
        reason_text = " ".join(readiness.reasons)
        raise ValueError(f"Assessment is not ready. {reason_text}")

    run_id = create_assessment_run(
        assessment_id=assessment_id,
        model=model,
        prompt_version=prompt_version,
        database_path=database_path,
    )
    transition_assessment_run(
        run_id,
        RunStatus.RUNNING,
        database_path=database_path,
    )
    return run_id


def build_evidence_pack(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
    collection=None,
    openai_client=None,
    results_per_dimension: int = 2,
    search_fn: Optional[Callable[..., list[dict[str, object]]]] = None,
) -> EvidencePack:
    """Retrieve and deduplicate source chunks across assessment dimensions."""
    if results_per_dimension <= 0:
        raise ValueError("Results per dimension must be greater than zero.")

    readiness = check_assessment_readiness(
        assessment_id,
        database_path,
        collection,
    )
    if not readiness.ready:
        reason_text = " ".join(readiness.reasons)
        raise ValueError(f"Assessment is not ready. {reason_text}")

    active_search = search_fn or search_assessment
    evidence_by_chunk: dict[str, dict[str, object]] = {}

    for dimension, query in EVIDENCE_QUERIES.items():
        results = active_search(
            query=query,
            assessment_id=assessment_id,
            limit=results_per_dimension,
            collection=collection,
            openai_client=openai_client,
        )
        LOGGER.info(
            "evidence_query assessment_id=%s dimension=%s results=%d",
            assessment_id,
            dimension.value,
            len(results),
        )

        for result in results:
            chunk_id = str(result["chunk_id"])
            metadata = dict(result["metadata"])
            similarity = float(result["similarity"])

            if chunk_id in evidence_by_chunk:
                existing = evidence_by_chunk[chunk_id]
                dimensions = existing["dimensions"]
                if dimension not in dimensions:
                    dimensions.append(dimension)
                existing["similarity"] = max(
                    float(existing["similarity"]),
                    similarity,
                )
                continue

            evidence_by_chunk[chunk_id] = {
                "chunk_id": chunk_id,
                "document_id": str(metadata["document_id"]),
                "filename": str(metadata["filename"]),
                "chunk_index": int(metadata["chunk_index"]),
                "content": str(result["content"]),
                "dimensions": [dimension],
                "similarity": similarity,
            }

    if not evidence_by_chunk:
        raise ValueError("No source evidence could be retrieved for this assessment.")

    items = [
        EvidenceItem(
            citation_id=f"E{index}",
            **evidence_data,
        )
        for index, evidence_data in enumerate(
            evidence_by_chunk.values(),
            start=1,
        )
    ]
    LOGGER.info(
        "evidence_pack_built assessment_id=%s unique_chunks=%d",
        assessment_id,
        len(items),
    )
    return EvidencePack(assessment_id=assessment_id, items=items)
