from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from agile_ci_demo.core.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def init_db() -> None:
    """Create all tables for models that have been imported.

    Each domain module's models must be imported here so they register
    themselves on ``Base.metadata`` before ``create_all`` runs.
    """
    from agile_ci_demo.appointments import models as _appointments_models  # noqa: F401
    from agile_ci_demo.patients import models as _patients_models  # noqa: F401
    from agile_ci_demo.records import models as _records_models  # noqa: F401
    from agile_ci_demo.staff import models as _staff_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
