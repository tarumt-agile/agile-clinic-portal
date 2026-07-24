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

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

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


def migrate_sqlite_database() -> None:
    """Update older SQLite tables to match the current models."""

    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    with engine.begin() as connection:
        # Add diagnosis_id to old prescriptions table.
        if "prescriptions" in table_names:
            prescription_columns = {
                column["name"] for column in inspector.get_columns("prescriptions")
            }

            if "diagnosis_id" not in prescription_columns:
                connection.execute(text("""
                        ALTER TABLE prescriptions
                        ADD COLUMN diagnosis_id INTEGER
                        REFERENCES diagnoses(id)
                        """))

            # Link old prescriptions to the first diagnosis
            # belonging to the same consultation.
            connection.execute(text("""
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
                    """))

        # Add instruction history columns to old history table.
        if "prescription_history" in table_names:
            history_columns = {
                column["name"] for column in inspector.get_columns("prescription_history")
            }

            if "previous_frequency" not in history_columns:
                connection.execute(text("""
                        ALTER TABLE prescription_history
                        ADD COLUMN previous_frequency
                        VARCHAR(120)
                        """))

            if "new_frequency" not in history_columns:
                connection.execute(text("""
                        ALTER TABLE prescription_history
                        ADD COLUMN new_frequency
                        VARCHAR(120)
                        """))

            if "previous_duration" not in history_columns:
                connection.execute(text("""
                        ALTER TABLE prescription_history
                        ADD COLUMN previous_duration
                        VARCHAR(120)
                        """))

            if "new_duration" not in history_columns:
                connection.execute(text("""
                        ALTER TABLE prescription_history
                        ADD COLUMN new_duration
                        VARCHAR(120)
                        """))

            # Give older history rows safe values.
            connection.execute(text("""
                    UPDATE prescription_history
                    SET previous_frequency = ''
                    WHERE previous_frequency IS NULL
                    """))

            connection.execute(text("""
                    UPDATE prescription_history
                    SET new_frequency = ''
                    WHERE new_frequency IS NULL
                    """))

            connection.execute(text("""
                    UPDATE prescription_history
                    SET previous_duration = ''
                    WHERE previous_duration IS NULL
                    """))

            connection.execute(text("""
                    UPDATE prescription_history
                    SET new_duration = ''
                    WHERE new_duration IS NULL
                    """))

        # Add working-hours columns to old doctor_profiles table.
        if "doctor_profiles" in table_names:
            doctor_columns = {column["name"] for column in inspector.get_columns("doctor_profiles")}

            if "start_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN start_time TIME
                        """))

            if "end_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN end_time TIME
                        """))

            if "next_start_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_start_time TIME
                        """))

            if "next_end_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_end_time TIME
                        """))

            if "next_effective_date" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_effective_date DATE
                        """))

            # Give existing doctors the clinic's old default hours.
            connection.execute(text("""
                    UPDATE doctor_profiles
                    SET start_time = '09:00:00'
                    WHERE start_time IS NULL
                    """))

            connection.execute(text("""
                    UPDATE doctor_profiles
                    SET end_time = '17:00:00'
                    WHERE end_time IS NULL
                    """))


def init_db() -> None:
    """Create all tables and update older SQLite tables."""

    from agile_ci_demo.appointments import (
        models as _appointments_models,  # noqa: F401
    )
    from agile_ci_demo.patients import (
        models as _patients_models,  # noqa: F401
    )
    from agile_ci_demo.prescription import (
        models as _prescription_models,  # noqa: F401
    )
    from agile_ci_demo.records import (
        models as _records_models,  # noqa: F401
    )
    from agile_ci_demo.staff import (
        models as _staff_models,  # noqa: F401
    )

    Base.metadata.create_all(bind=engine)

    migrate_sqlite_database()


def get_db() -> Generator[
    Session,
    None,
    None,
]:
    """Provide one database session for each request."""

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()
