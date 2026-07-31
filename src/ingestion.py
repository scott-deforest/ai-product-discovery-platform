"""Document storage and, later, text extraction."""

from pathlib import Path
from uuid import uuid4

from src.config import DATABASE_PATH, UPLOADS_PATH
from src.database import DatabasePath, create_document


SUPPORTED_FILE_TYPES = {"pdf", "txt", "md", "docx"}


def save_uploaded_document(
    assessment_id: str,
    filename: str,
    content: bytes,
    uploads_path: Path = UPLOADS_PATH,
    database_path: DatabasePath = DATABASE_PATH,
) -> str:
    """Store an uploaded file, record its metadata, and return its ID."""
    safe_filename = Path(filename).name.strip()
    if not safe_filename:
        raise ValueError("The uploaded file must have a name.")

    file_type = Path(safe_filename).suffix.lower().lstrip(".")
    if file_type not in SUPPORTED_FILE_TYPES:
        allowed_types = ", ".join(sorted(SUPPORTED_FILE_TYPES))
        raise ValueError(f"Unsupported file type. Choose: {allowed_types}.")

    document_id = str(uuid4())
    document_directory = Path(uploads_path) / assessment_id / document_id
    document_directory.mkdir(parents=True, exist_ok=True)
    stored_path = document_directory / safe_filename
    stored_path.write_bytes(content)

    create_document(
        document_id=document_id,
        assessment_id=assessment_id,
        filename=safe_filename,
        stored_path=str(stored_path),
        file_type=file_type,
        size_bytes=len(content),
        database_path=database_path,
    )

    return document_id
