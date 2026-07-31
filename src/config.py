"""Application configuration."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "db" / "product_discovery.db"
UPLOADS_PATH = PROJECT_ROOT / "data" / "uploads"
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed"
