"""Document storage and, later, text extraction."""

from pathlib import Path
from uuid import uuid4

from docx import Document
from pypdf import PdfReader

from src.config import DATABASE_PATH, PROCESSED_PATH, UPLOADS_PATH
from src.database import (
    DatabasePath,
    create_document,
    save_document_extraction,
)


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


def extract_text(file_path: Path, file_type: str) -> str:
    """Extract readable text from one supported document."""
    normalized_type = file_type.lower().lstrip(".")

    if normalized_type in {"txt", "md"}:
        text = Path(file_path).read_text(encoding="utf-8-sig")
    elif normalized_type == "pdf":
        reader = PdfReader(str(file_path))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif normalized_type == "docx":
        document = Document(str(file_path))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    else:
        raise ValueError(f"Unsupported file type: {file_type}.")

    clean_text = text.strip()
    if not clean_text:
        raise ValueError("No readable text was found in the document.")

    return clean_text


def extract_and_save_document(
    document_id: str,
    assessment_id: str,
    stored_path: str,
    file_type: str,
    processed_path: Path = PROCESSED_PATH,
    database_path: DatabasePath = DATABASE_PATH,
) -> str:
    """Extract document text, save it, and return the processed text path."""
    text = extract_text(Path(stored_path), file_type)
    output_directory = Path(processed_path) / assessment_id
    output_directory.mkdir(parents=True, exist_ok=True)
    text_path = output_directory / f"{document_id}.txt"
    text_path.write_text(text, encoding="utf-8")

    save_document_extraction(
        document_id=document_id,
        text_path=str(text_path),
        character_count=len(text),
        database_path=database_path,
    )

    return str(text_path)


def read_extracted_text(text_path: str) -> str:
    """Load previously extracted document text for preview."""
    return Path(text_path).read_text(encoding="utf-8")
