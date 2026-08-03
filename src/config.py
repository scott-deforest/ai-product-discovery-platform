"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "db" / "product_discovery.db"
UPLOADS_PATH = PROJECT_ROOT / "data" / "uploads"
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed"
CHROMA_PATH = PROJECT_ROOT / ".chroma"


def analysis_model() -> str:
    """Return the configured OpenAI model for opportunity analysis."""
    load_dotenv()
    return os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-5.6-sol")
