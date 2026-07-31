"""Assessment metadata persistence."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from uuid import uuid4

from src.config import DATABASE_PATH


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
