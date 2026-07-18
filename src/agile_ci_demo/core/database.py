from collections.abc import Generator

from sqlalchemy import (
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Session,
    sessionmaker,
)

from agile_ci_demo.core.config import settings


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def migrate_sqlite_prescriptions() -> None:
    """Add the diagnosis link to an older SQLite database."""

    if not settings.database_url.startswith(
        "sqlite"
    ):
        return

    inspector = inspect(engine)

    if "prescriptions" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(
            "prescriptions"
        )
    }

    with engine.begin() as connection:
        if "diagnosis_id" not in existing_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE prescriptions
                    ADD COLUMN diagnosis_id INTEGER
                    REFERENCES diagnoses(id)
                    """
                )
            )

        # Assign older prescriptions to the first diagnosis
        # belonging to their consultation.
        connection.execute(
            text(
                """
                UPDATE prescriptions
                SET diagnosis_id = (
                    SELECT diagnoses.id
                    FROM diagnoses
                    WHERE
                        diagnoses.consultation_note_id
                        =
                        prescriptions.consultation_note_id
                    ORDER BY diagnoses.id ASC
                    LIMIT 1
                )
                WHERE diagnosis_id IS NULL
                """
            )
        )


def init_db() -> None:
    """Create tables and apply small SQLite migrations."""

    from agile_ci_demo.appointments import (
        models as _appointments_models,
    )
    from agile_ci_demo.patients import (
        models as _patients_models,
    )
    from agile_ci_demo.prescription import (
        models as _prescription_models,
    )
    from agile_ci_demo.records import (
        models as _records_models,
    )
    from agile_ci_demo.staff import (
        models as _staff_models,
    )

    Base.metadata.create_all(bind=engine)

    migrate_sqlite_prescriptions()


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """Provide one database session per request."""

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()