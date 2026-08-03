"""Assessment, document, and analysis-run persistence."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4

from src.config import DATABASE_PATH
from src.models import RunStatus


DatabasePath = Union[str, Path]


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
                   started_at, completed_at, error_message, created_at
            FROM assessment_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    return dict(row) if row else None


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
