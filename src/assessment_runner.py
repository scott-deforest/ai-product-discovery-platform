"""Assessment readiness checks and workflow orchestration."""

from src.config import DATABASE_PATH
from src.database import (
    DatabasePath,
    count_assessment_chunks,
    create_assessment_run,
    get_assessment,
    list_documents,
    transition_assessment_run,
)
from src.models import AssessmentReadiness, RunStatus
from src.vector_store import count_indexed_assessment_chunks


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
        reasons.append("Upload at least one document.")
    if chunk_count == 0:
        reasons.append("Extract and chunk at least one document.")
    if indexed_chunk_count == 0:
        reasons.append("Index document chunks before running an assessment.")
    elif indexed_chunk_count != chunk_count:
        reasons.append("Re-index all current document chunks.")

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
