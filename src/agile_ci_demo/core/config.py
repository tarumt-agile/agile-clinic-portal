import os
from pathlib import Path

# src/agile_ci_demo/core/config.py -> repo root is 4 levels up
BASE_DIR = Path(__file__).resolve().parents[3]


class Settings:
    """Application settings, sourced from environment variables with sane defaults."""

    app_name: str = "Agile Clinic Portal"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./clinic.db")
    templates_dir: Path = BASE_DIR / "templates"
    static_dir: Path = BASE_DIR / "static"


settings = Settings()
