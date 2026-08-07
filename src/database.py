"""Assessment, document, analysis-run, and human-review persistence."""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4

from src.config import DATABASE_PATH
from src.models import (
    AssessmentResult,
    CompletedAssessment,
    EvidenceCitation,
    EvaluationRating,
    HumanEvaluation,
    OpportunityReview,
    RankedOpportunity,
    ReviewDecision,
    RunStatus,
    SavedHumanEvaluation,
    ScoreDetail,
)


DatabasePath = Union[str, Path]
LOGGER = logging.getLogger(__name__)


def _connect(database_path: DatabasePath) -> sqlite3.Connection:
    """Open the database and return rows that behave like dictionaries."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: DatabasePath = DATABASE_PATH) -> None:
    """Create the database directory and assessments table when needed."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL,
                FOREIGN KEY (assessment_id) REFERENCES assessments (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_extractions (
                document_id TEXT PRIMARY KEY,
                text_path TEXT NOT NULL,
                character_count INTEGER NOT NULL,
                extracted_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                word_count INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE (document_id, chunk_index),
                FOREIGN KEY (document_id) REFERENCES documents (id),
                FOREIGN KEY (assessment_id) REFERENCES assessments (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS assessment_runs (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'running', 'completed', 'failed')
                ),
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                executive_summary TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (assessment_id) REFERENCES assessments (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                rank INTEGER,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                problem TEXT NOT NULL,
                proposed_capability TEXT NOT NULL,
                primary_users_json TEXT NOT NULL,
                workflow_placement TEXT NOT NULL,
                expected_value TEXT NOT NULL,
                data_requirements_json TEXT NOT NULL,
                risks_json TEXT NOT NULL,
                safeguards_json TEXT NOT NULL,
                success_metrics_json TEXT NOT NULL,
                missing_information_json TEXT NOT NULL,
                business_value_score INTEGER NOT NULL CHECK (
                    business_value_score BETWEEN 1 AND 5
                ),
                business_value_rationale TEXT NOT NULL,
                feasibility_score INTEGER NOT NULL CHECK (
                    feasibility_score BETWEEN 1 AND 5
                ),
                feasibility_rationale TEXT NOT NULL,
                evidence_strength_score INTEGER NOT NULL CHECK (
                    evidence_strength_score BETWEEN 1 AND 5
                ),
                evidence_strength_rationale TEXT NOT NULL,
                risk_readiness_score INTEGER NOT NULL CHECK (
                    risk_readiness_score BETWEEN 1 AND 5
                ),
                risk_readiness_rationale TEXT NOT NULL,
                composite_score REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES assessment_runs (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_evidence (
                id TEXT PRIMARY KEY,
                opportunity_id TEXT NOT NULL,
                citation_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                excerpt TEXT NOT NULL,
                UNIQUE (opportunity_id, citation_id),
                FOREIGN KEY (opportunity_id) REFERENCES opportunities (id),
                FOREIGN KEY (document_id) REFERENCES documents (id),
                FOREIGN KEY (chunk_id) REFERENCES document_chunks (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS opportunity_reviews (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                opportunity_rank INTEGER NOT NULL CHECK (opportunity_rank >= 1),
                decision TEXT NOT NULL CHECK (
                    decision IN ('advance', 'needs_evidence', 'defer', 'reject')
                ),
                note TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 1),
                reviewed_at TEXT NOT NULL,
                UNIQUE (run_id, opportunity_rank, revision),
                FOREIGN KEY (run_id) REFERENCES assessment_runs (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS human_evaluations (
                id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                pipeline_version TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                evidence_grounding_score INTEGER NOT NULL CHECK (
                    evidence_grounding_score BETWEEN 1 AND 5
                ),
                evidence_grounding_rationale TEXT NOT NULL,
                specificity_score INTEGER NOT NULL CHECK (
                    specificity_score BETWEEN 1 AND 5
                ),
                specificity_rationale TEXT NOT NULL,
                actionability_score INTEGER NOT NULL CHECK (
                    actionability_score BETWEEN 1 AND 5
                ),
                actionability_rationale TEXT NOT NULL,
                risk_awareness_score INTEGER NOT NULL CHECK (
                    risk_awareness_score BETWEEN 1 AND 5
                ),
                risk_awareness_rationale TEXT NOT NULL,
                decision_usefulness_score INTEGER NOT NULL CHECK (
                    decision_usefulness_score BETWEEN 1 AND 5
                ),
                decision_usefulness_rationale TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                revision INTEGER NOT NULL CHECK (revision >= 1),
                evaluated_at TEXT NOT NULL,
                UNIQUE (run_id, revision),
                FOREIGN KEY (run_id) REFERENCES assessment_runs (id)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_assessment_runs_assessment_id
            ON assessment_runs (assessment_id, created_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_opportunities_run_id
            ON opportunities (run_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_opportunity_reviews_run_rank
            ON opportunity_reviews (run_id, opportunity_rank, revision)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_evaluations_run_revision
            ON human_evaluations (run_id, revision)
            """
        )
        run_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(assessment_runs)")
        }
        if "executive_summary" not in run_columns:
            connection.execute(
                "ALTER TABLE assessment_runs ADD COLUMN executive_summary TEXT"
            )


def create_assessment(
    name: str,
    description: str = "",
    database_path: DatabasePath = DATABASE_PATH,
) -> str:
    """Save a new assessment and return its generated ID."""
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Assessment name is required.")

    assessment_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO assessments (id, name, description, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                assessment_id,
                clean_name,
                description.strip(),
                "draft",
                created_at,
            ),
        )

    return assessment_id


def list_assessments(
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, Optional[str]]]:
    """Return all assessments, newest first."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, status, created_at
            FROM assessments
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_assessment(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Optional[dict[str, object]]:
    """Return one assessment when it exists."""
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, name, description, status, created_at
            FROM assessments
            WHERE id = ?
            """,
            (assessment_id,),
        ).fetchone()

    return dict(row) if row else None


def create_document(
    document_id: str,
    assessment_id: str,
    filename: str,
    stored_path: str,
    file_type: str,
    size_bytes: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Record an uploaded document and its owning assessment."""
    uploaded_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO documents (
                id,
                assessment_id,
                filename,
                stored_path,
                file_type,
                size_bytes,
                uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                assessment_id,
                filename,
                stored_path,
                file_type,
                size_bytes,
                uploaded_at,
            ),
        )


def list_documents(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return the documents belonging to one assessment, newest first."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, assessment_id, filename, stored_path, file_type,
                   size_bytes, uploaded_at
            FROM documents
            WHERE assessment_id = ?
            ORDER BY uploaded_at DESC
            """,
            (assessment_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_document_extraction(
    document_id: str,
    text_path: str,
    character_count: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Record where extracted document text is stored."""
    extracted_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        connection.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,),
        )
        connection.execute(
            """
            INSERT INTO document_extractions (
                document_id, text_path, character_count, extracted_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                text_path = excluded.text_path,
                character_count = excluded.character_count,
                extracted_at = excluded.extracted_at
            """,
            (document_id, text_path, character_count, extracted_at),
        )


def get_document_extraction(
    document_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Optional[dict[str, object]]:
    """Return extraction metadata for one document, when available."""
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT document_id, text_path, character_count, extracted_at
            FROM document_extractions
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()

    return dict(row) if row else None


def replace_document_chunks(
    document_id: str,
    assessment_id: str,
    chunks: list[str],
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Replace all stored chunks for one document."""
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        connection.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,),
        )
        connection.executemany(
            """
            INSERT INTO document_chunks (
                id,
                document_id,
                assessment_id,
                chunk_index,
                content,
                word_count,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"{document_id}-chunk-{index}",
                    document_id,
                    assessment_id,
                    index,
                    content,
                    len(content.split()),
                    created_at,
                )
                for index, content in enumerate(chunks)
            ],
        )


def list_document_chunks(
    document_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return a document's chunks in their original order."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, document_id, assessment_id, chunk_index, content,
                   word_count, created_at
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def count_assessment_chunks(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> int:
    """Count the current chunks stored for one assessment."""
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS chunk_count
            FROM document_chunks
            WHERE assessment_id = ?
            """,
            (assessment_id,),
        ).fetchone()

    return int(row["chunk_count"])


def create_assessment_run(
    assessment_id: str,
    model: str,
    prompt_version: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> str:
    """Create a pending analysis run and return its ID."""
    clean_model = model.strip()
    clean_prompt_version = prompt_version.strip()
    if not clean_model or not clean_prompt_version:
        raise ValueError("Model and prompt version are required.")

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO assessment_runs (
                id, assessment_id, status, model, prompt_version, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                assessment_id,
                RunStatus.PENDING.value,
                clean_model,
                clean_prompt_version,
                created_at,
            ),
        )

    return run_id


def get_assessment_run(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Optional[dict[str, object]]:
    """Return one persisted assessment run."""
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT id, assessment_id, status, model, prompt_version,
                   started_at, completed_at, error_message, executive_summary,
                   created_at
            FROM assessment_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    return dict(row) if row else None


def list_assessment_runs(
    assessment_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return an assessment's runs, newest first."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id, assessment_id, status, model, prompt_version,
                   started_at, completed_at, error_message, executive_summary,
                   created_at
            FROM assessment_runs
            WHERE assessment_id = ?
            ORDER BY created_at DESC
            """,
            (assessment_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def transition_assessment_run(
    run_id: str,
    target_status: RunStatus,
    error_message: Optional[str] = None,
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Move a run through its allowed lifecycle and persist timestamps."""
    allowed_transitions = {
        RunStatus.PENDING: {RunStatus.RUNNING, RunStatus.FAILED},
        RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED},
        RunStatus.COMPLETED: set(),
        RunStatus.FAILED: set(),
    }

    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT status, started_at, completed_at
            FROM assessment_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Assessment run not found: {run_id}.")

        current_status = RunStatus(row["status"])
        if target_status not in allowed_transitions[current_status]:
            raise ValueError(
                f"Cannot transition assessment run from "
                f"{current_status.value} to {target_status.value}."
            )

        clean_error = error_message.strip() if error_message else None
        if target_status == RunStatus.FAILED and not clean_error:
            raise ValueError("A failed assessment run requires an error message.")

        now = datetime.now(timezone.utc).isoformat()
        started_at = row["started_at"]
        completed_at = row["completed_at"]
        if target_status == RunStatus.RUNNING:
            started_at = now
        if target_status in {RunStatus.COMPLETED, RunStatus.FAILED}:
            completed_at = now

        connection.execute(
            """
            UPDATE assessment_runs
            SET status = ?, started_at = ?, completed_at = ?, error_message = ?
            WHERE id = ?
            """,
            (
                target_status.value,
                started_at,
                completed_at,
                clean_error,
                run_id,
            ),
        )


def save_assessment_result(
    run_id: str,
    result: AssessmentResult,
    ranked_opportunities: list[RankedOpportunity],
    database_path: DatabasePath = DATABASE_PATH,
) -> None:
    """Atomically save ranked opportunities, citations, and run completion."""
    if len(ranked_opportunities) != len(result.opportunities):
        raise ValueError("Every generated opportunity must be ranked before saving.")

    expected_ranks = list(range(1, len(ranked_opportunities) + 1))
    actual_ranks = [opportunity.rank for opportunity in ranked_opportunities]
    if actual_ranks != expected_ranks:
        raise ValueError("Opportunity ranks must be consecutive and start at one.")

    citations_by_id = {
        citation.citation_id: citation for citation in result.evidence
    }
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        run = connection.execute(
            "SELECT status FROM assessment_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise ValueError(f"Assessment run not found: {run_id}.")
        if RunStatus(run["status"]) != RunStatus.RUNNING:
            raise ValueError("Only a running assessment can save results.")

        existing_count = connection.execute(
            "SELECT COUNT(*) AS count FROM opportunities WHERE run_id = ?",
            (run_id,),
        ).fetchone()["count"]
        if existing_count:
            raise ValueError("This assessment run already has saved opportunities.")

        for opportunity in ranked_opportunities:
            opportunity_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO opportunities (
                    id, run_id, rank, title, summary, problem,
                    proposed_capability, primary_users_json, workflow_placement,
                    expected_value, data_requirements_json, risks_json,
                    safeguards_json, success_metrics_json,
                    missing_information_json, business_value_score,
                    business_value_rationale, feasibility_score,
                    feasibility_rationale, evidence_strength_score,
                    evidence_strength_rationale, risk_readiness_score,
                    risk_readiness_rationale, composite_score, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opportunity_id,
                    run_id,
                    opportunity.rank,
                    opportunity.title,
                    opportunity.summary,
                    opportunity.problem,
                    opportunity.proposed_capability,
                    json.dumps(opportunity.primary_users),
                    opportunity.workflow_placement,
                    opportunity.expected_value,
                    json.dumps(opportunity.data_requirements),
                    json.dumps(opportunity.risks),
                    json.dumps(opportunity.safeguards),
                    json.dumps(opportunity.success_metrics),
                    json.dumps(opportunity.missing_information),
                    opportunity.business_value.score,
                    opportunity.business_value.rationale,
                    opportunity.feasibility.score,
                    opportunity.feasibility.rationale,
                    opportunity.evidence_strength.score,
                    opportunity.evidence_strength.rationale,
                    opportunity.risk_readiness.score,
                    opportunity.risk_readiness.rationale,
                    opportunity.composite_score,
                    created_at,
                ),
            )
            for citation_id in opportunity.citation_ids:
                citation = citations_by_id[citation_id]
                connection.execute(
                    """
                    INSERT INTO opportunity_evidence (
                        id, opportunity_id, citation_id, document_id, chunk_id,
                        filename, chunk_index, excerpt
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        opportunity_id,
                        citation.citation_id,
                        citation.document_id,
                        citation.chunk_id,
                        citation.filename,
                        citation.chunk_index,
                        citation.excerpt,
                    ),
                )

        connection.execute(
            """
            UPDATE assessment_runs
            SET status = ?, completed_at = ?, error_message = NULL,
                executive_summary = ?
            WHERE id = ?
            """,
            (
                RunStatus.COMPLETED.value,
                created_at,
                result.executive_summary,
                run_id,
            ),
        )


def list_run_opportunities(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return one run's saved opportunities in ranked order."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM opportunities
            WHERE run_id = ?
            ORDER BY rank, title
            """,
            (run_id,),
        ).fetchall()

    list_fields = {
        "primary_users_json": "primary_users",
        "data_requirements_json": "data_requirements",
        "risks_json": "risks",
        "safeguards_json": "safeguards",
        "success_metrics_json": "success_metrics",
        "missing_information_json": "missing_information",
    }
    opportunities = []
    for row in rows:
        opportunity = dict(row)
        for stored_name, public_name in list_fields.items():
            opportunity[public_name] = json.loads(opportunity.pop(stored_name))
        opportunities.append(opportunity)
    return opportunities


def list_opportunity_evidence(
    opportunity_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[dict[str, object]]:
    """Return the saved source citations for one opportunity."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT citation_id, document_id, chunk_id, filename, chunk_index,
                   excerpt
            FROM opportunity_evidence
            WHERE opportunity_id = ?
            ORDER BY citation_id
            """,
            (opportunity_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_opportunity_review(
    run_id: str,
    opportunity_rank: int,
    decision: Union[ReviewDecision, str],
    note: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> OpportunityReview:
    """Append a validated human decision without overwriting prior revisions."""
    try:
        validated_decision = ReviewDecision(decision)
    except ValueError as error:
        raise ValueError("Choose a valid review decision.") from error

    clean_note = note.strip()
    if not clean_note:
        raise ValueError("Add a short note explaining your decision.")
    if opportunity_rank < 1:
        raise ValueError("Opportunity rank must be at least one.")

    review_id = str(uuid4())
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with _connect(database_path) as connection:
        run = connection.execute(
            "SELECT status FROM assessment_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise ValueError(f"Assessment run not found: {run_id}.")
        if run["status"] != RunStatus.COMPLETED.value:
            raise ValueError("Only a completed report can receive a review decision.")

        opportunity = connection.execute(
            """
            SELECT id FROM opportunities
            WHERE run_id = ? AND rank = ?
            """,
            (run_id, opportunity_rank),
        ).fetchone()
        if opportunity is None:
            raise ValueError("The selected opportunity does not exist in this report.")

        latest_revision = connection.execute(
            """
            SELECT COALESCE(MAX(revision), 0) AS revision
            FROM opportunity_reviews
            WHERE run_id = ? AND opportunity_rank = ?
            """,
            (run_id, opportunity_rank),
        ).fetchone()
        revision = int(latest_revision["revision"]) + 1
        connection.execute(
            """
            INSERT INTO opportunity_reviews (
                id, run_id, opportunity_rank, decision, note, revision, reviewed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                run_id,
                opportunity_rank,
                validated_decision.value,
                clean_note,
                revision,
                reviewed_at,
            ),
        )

    LOGGER.info(
        "opportunity_review_saved run_id=%s rank=%d decision=%s revision=%d",
        run_id,
        opportunity_rank,
        validated_decision.value,
        revision,
    )
    return OpportunityReview(
        review_id=review_id,
        run_id=run_id,
        opportunity_rank=opportunity_rank,
        decision=validated_decision,
        note=clean_note,
        revision=revision,
        reviewed_at=reviewed_at,
    )


def list_latest_opportunity_reviews(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[OpportunityReview]:
    """Return the newest human decision for each opportunity in a report."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT reviews.*
            FROM opportunity_reviews AS reviews
            JOIN (
                SELECT opportunity_rank, MAX(revision) AS latest_revision
                FROM opportunity_reviews
                WHERE run_id = ?
                GROUP BY opportunity_rank
            ) AS latest
              ON reviews.opportunity_rank = latest.opportunity_rank
             AND reviews.revision = latest.latest_revision
            WHERE reviews.run_id = ?
            ORDER BY reviews.opportunity_rank
            """,
            (run_id, run_id),
        ).fetchall()
    return [_opportunity_review_from_row(row) for row in rows]


def list_opportunity_review_history(
    run_id: str,
    opportunity_rank: int,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[OpportunityReview]:
    """Return every saved revision for one opportunity, newest first."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM opportunity_reviews
            WHERE run_id = ? AND opportunity_rank = ?
            ORDER BY revision DESC
            """,
            (run_id, opportunity_rank),
        ).fetchall()
    return [_opportunity_review_from_row(row) for row in rows]


def _opportunity_review_from_row(row: sqlite3.Row) -> OpportunityReview:
    return OpportunityReview(
        review_id=str(row["id"]),
        run_id=str(row["run_id"]),
        opportunity_rank=int(row["opportunity_rank"]),
        decision=ReviewDecision(str(row["decision"])),
        note=str(row["note"]),
        revision=int(row["revision"]),
        reviewed_at=str(row["reviewed_at"]),
    )


def save_human_evaluation(
    run_id: str,
    evaluation: HumanEvaluation,
    database_path: DatabasePath = DATABASE_PATH,
) -> SavedHumanEvaluation:
    """Append a report-level human evaluation after verifying run metadata."""
    evaluation_id = str(uuid4())
    evaluated_at = datetime.now(timezone.utc).isoformat()

    with _connect(database_path) as connection:
        run = connection.execute(
            """
            SELECT assessment_id, status, prompt_version
            FROM assessment_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
        if run is None:
            raise ValueError(f"Assessment run not found: {run_id}.")
        if run["status"] != RunStatus.COMPLETED.value:
            raise ValueError("Only a completed report can receive a human evaluation.")
        if evaluation.case_id != run["assessment_id"]:
            raise ValueError("The evaluation does not belong to this assessment.")
        if evaluation.pipeline_version != run["prompt_version"]:
            raise ValueError("The evaluation does not match this pipeline version.")

        latest_revision = connection.execute(
            """
            SELECT COALESCE(MAX(revision), 0) AS revision
            FROM human_evaluations
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        revision = int(latest_revision["revision"]) + 1
        connection.execute(
            """
            INSERT INTO human_evaluations (
                id, run_id, case_id, pipeline_version, reviewer,
                evidence_grounding_score, evidence_grounding_rationale,
                specificity_score, specificity_rationale,
                actionability_score, actionability_rationale,
                risk_awareness_score, risk_awareness_rationale,
                decision_usefulness_score, decision_usefulness_rationale,
                notes, revision, evaluated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_id,
                run_id,
                evaluation.case_id,
                evaluation.pipeline_version,
                evaluation.reviewer,
                evaluation.evidence_grounding.score,
                evaluation.evidence_grounding.rationale,
                evaluation.specificity.score,
                evaluation.specificity.rationale,
                evaluation.actionability.score,
                evaluation.actionability.rationale,
                evaluation.risk_awareness.score,
                evaluation.risk_awareness.rationale,
                evaluation.decision_usefulness.score,
                evaluation.decision_usefulness.rationale,
                evaluation.notes,
                revision,
                evaluated_at,
            ),
        )

    LOGGER.info(
        "human_evaluation_saved run_id=%s reviewer=%s revision=%d",
        run_id,
        evaluation.reviewer,
        revision,
    )
    return SavedHumanEvaluation(
        **evaluation.model_dump(),
        evaluation_id=evaluation_id,
        run_id=run_id,
        revision=revision,
        evaluated_at=evaluated_at,
    )


def get_latest_human_evaluation(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> Optional[SavedHumanEvaluation]:
    """Return the newest report-level evaluation when one has been saved."""
    with _connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT * FROM human_evaluations
            WHERE run_id = ?
            ORDER BY revision DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    return _human_evaluation_from_row(row) if row else None


def list_human_evaluation_history(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> list[SavedHumanEvaluation]:
    """Return all report-level evaluation revisions, newest first."""
    with _connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM human_evaluations
            WHERE run_id = ?
            ORDER BY revision DESC
            """,
            (run_id,),
        ).fetchall()
    return [_human_evaluation_from_row(row) for row in rows]


def _human_evaluation_from_row(row: sqlite3.Row) -> SavedHumanEvaluation:
    ratings = {
        criterion: EvaluationRating(
            score=int(row[f"{criterion}_score"]),
            rationale=str(row[f"{criterion}_rationale"]),
        )
        for criterion in (
            "evidence_grounding",
            "specificity",
            "actionability",
            "risk_awareness",
            "decision_usefulness",
        )
    }
    return SavedHumanEvaluation(
        evaluation_id=str(row["id"]),
        run_id=str(row["run_id"]),
        case_id=str(row["case_id"]),
        pipeline_version=str(row["pipeline_version"]),
        reviewer=str(row["reviewer"]),
        notes=str(row["notes"]),
        revision=int(row["revision"]),
        evaluated_at=str(row["evaluated_at"]),
        **ratings,
    )


def load_completed_assessment(
    run_id: str,
    database_path: DatabasePath = DATABASE_PATH,
) -> CompletedAssessment:
    """Rebuild a completed report entirely from persisted data."""
    run = get_assessment_run(run_id, database_path)
    if run is None:
        raise ValueError(f"Assessment run not found: {run_id}.")
    if run["status"] != RunStatus.COMPLETED.value:
        raise ValueError("Only completed assessment runs have a report.")
    if not run["executive_summary"]:
        raise ValueError("The completed assessment is missing its summary.")

    saved_opportunities = list_run_opportunities(run_id, database_path)
    if not saved_opportunities:
        raise ValueError("The completed assessment has no saved opportunities.")

    citations_by_id: dict[str, EvidenceCitation] = {}
    ranked_opportunities = []
    for saved in saved_opportunities:
        citations = list_opportunity_evidence(str(saved["id"]), database_path)
        citation_ids = []
        for citation_data in citations:
            citation = EvidenceCitation.model_validate(citation_data)
            citations_by_id[citation.citation_id] = citation
            citation_ids.append(citation.citation_id)

        ranked_opportunities.append(
            RankedOpportunity(
                rank=int(saved["rank"]),
                composite_score=float(saved["composite_score"]),
                title=str(saved["title"]),
                summary=str(saved["summary"]),
                problem=str(saved["problem"]),
                proposed_capability=str(saved["proposed_capability"]),
                primary_users=list(saved["primary_users"]),
                workflow_placement=str(saved["workflow_placement"]),
                expected_value=str(saved["expected_value"]),
                data_requirements=list(saved["data_requirements"]),
                risks=list(saved["risks"]),
                safeguards=list(saved["safeguards"]),
                success_metrics=list(saved["success_metrics"]),
                missing_information=list(saved["missing_information"]),
                business_value=ScoreDetail(
                    score=int(saved["business_value_score"]),
                    rationale=str(saved["business_value_rationale"]),
                ),
                feasibility=ScoreDetail(
                    score=int(saved["feasibility_score"]),
                    rationale=str(saved["feasibility_rationale"]),
                ),
                evidence_strength=ScoreDetail(
                    score=int(saved["evidence_strength_score"]),
                    rationale=str(saved["evidence_strength_rationale"]),
                ),
                risk_readiness=ScoreDetail(
                    score=int(saved["risk_readiness_score"]),
                    rationale=str(saved["risk_readiness_rationale"]),
                ),
                citation_ids=citation_ids,
            )
        )

    return CompletedAssessment(
        run_id=run_id,
        executive_summary=str(run["executive_summary"]),
        evidence=list(citations_by_id.values()),
        opportunities=ranked_opportunities,
    )
