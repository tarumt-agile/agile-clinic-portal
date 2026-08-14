from __future__ import annotations

import datetime as dt
import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.appointments import models as _appointments_models  # noqa: F401
from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox
from agile_ci_demo.patients.service import get_patient_by_patient_id
from agile_ci_demo.staff import models as _staff_models  # noqa: F401
from agile_ci_demo.staff.schemas import StaffCreate
from agile_ci_demo.staff.service import create_staff, get_staff_by_staff_id

# --- Isolated in-memory DB per test -----------------------------------------


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI test client backed by a fresh in-memory SQLite DB for every test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    clear_outbox()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        clear_outbox()


def _create_staff_direct(client: TestClient, payload: dict[str, object]) -> str:
    """Create a staff account directly through the service layer, bypassing
    the API (POST /api/staff now requires an admin session) - this is pure
    test setup, not the thing under test. Returns the new account's public
    staff_id."""
    db = next(app.dependency_overrides[get_db]())
    try:
        return str(create_staff(db, StaffCreate(**payload)).staff_id)
    finally:
        db.close()


def _create_staff_and_login(
    client: TestClient, email: str = "alice.wong@example.com", role: str = "nurse"
) -> None:
    payload: dict[str, object] = {"full_name": "Alice Wong", "email": email, "role": role}
    if role == "doctor":
        payload.update(
            {
                "license_number": "MMC-70001",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    _create_staff_direct(client, payload)

    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    client.post("/api/auth/login", json={"email": email, "password": match.group(1)})


def _register_patient(client: TestClient, **overrides: object) -> str:
    payload: dict[str, object] = {
        "full_name": "Jane Tan",
        "date_of_birth": "1990-05-20",
        "gender": "female",
        "phone_number": "012-3456789",
        "email": "jane.tan@example.com",
        "ic_or_passport": "900520-10-1234",
        "address": "1 Jalan Testing, Kuala Lumpur",
    }
    payload.update(overrides)
    r = client.post("/api/patients", json=payload)
    assert r.status_code == 201, r.json()
    return str(r.json()["patient_id"])


def _register_doctor(client: TestClient, **overrides: object) -> str:
    payload: dict[str, object] = {
        "full_name": "Dr. Chandran Raj",
        "email": "chandran.raj@example.com",
        "role": "doctor",
        "license_number": "MMC-70002",
        "specialty": "General Medicine",
        "status": "active",
    }
    payload.update(overrides)
    return _create_staff_direct(client, payload)


def _seed_todays_appointment(patient_id: str, doctor_staff_id: str) -> None:
    """Insert a "today, scheduled" appointment directly, bypassing the booking
    API's now()-based slot validation - the exact clock time when tests run
    shouldn't determine whether "today" is bookable."""
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        doctor = get_staff_by_staff_id(db, doctor_staff_id)
        patient = get_patient_by_patient_id(db, patient_id)
        db.add(
            Appointment(
                reference_number="A90001",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=dt.date.today(),
                start_time=dt.time(9, 0),
                end_time=dt.time(9, 30),
                reason="Routine check-up",
                status="scheduled",
            )
        )
        db.commit()
    finally:
        next(db_generator, None)


# --- Admin dashboard page -----------------------------------------------------


def test_admin_dashboard_page_loads(client: TestClient) -> None:
    _create_staff_and_login(client, role="admin")

    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "Dashboard" in r.text
    assert 'id="stat-total-patients"' in r.text
    assert 'id="stat-total-staff"' in r.text
    assert 'id="stat-active-doctors"' in r.text
    assert 'id="stat-appointments-today"' in r.text
    assert 'href="/staff"' in r.text
    assert 'href="/patients"' in r.text
    assert 'href="/reports"' in r.text
    assert 'href="/pharmacy"' in r.text


def test_admin_dashboard_page_rejects_non_admin_role(client: TestClient) -> None:
    _create_staff_and_login(client, role="nurse")

    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"


def test_admin_dashboard_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"


# --- Admin dashboard stats API -------------------------------------------------


def test_get_admin_dashboard_stats_returns_counts(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_staff_id = _register_doctor(client)
    _seed_todays_appointment(patient_id, doctor_staff_id)

    _create_staff_and_login(client, role="admin")

    r = client.get("/api/dashboard/admin-stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_patients"] == 1
    assert body["total_staff"] == 2  # the doctor + the admin
    assert body["active_doctors"] == 1
    assert body["appointments_today"] == 1


def test_get_admin_dashboard_stats_requires_admin(client: TestClient) -> None:
    _create_staff_and_login(client, role="receptionist")

    r = client.get("/api/dashboard/admin-stats", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"
