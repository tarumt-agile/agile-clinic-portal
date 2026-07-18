import os
from pathlib import Path

from dotenv import load_dotenv

# src/agile_ci_demo/core/config.py -> repo root is 4 levels up
BASE_DIR = Path(__file__).resolve().parents[3]

# Loads variables from a local .env file (if present) into the environment. Real
# environment variables always take precedence and are never overwritten.
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application settings, sourced from environment variables with sane defaults."""

    app_name: str = "Agile Clinic Portal"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./clinic.db")
    templates_dir: Path = BASE_DIR / "templates"
    static_dir: Path = BASE_DIR / "static"

    # SMTP is optional. When unset, welcome emails are only recorded in the in-memory
    # outbox (see core/email.py) instead of actually being sent.
    smtp_host: str | None = os.getenv("SMTP_HOST")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME")
    smtp_password: str | None = os.getenv("SMTP_PASSWORD")
    smtp_from: str | None = os.getenv("SMTP_FROM")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() != "false"


settings = Settings()
