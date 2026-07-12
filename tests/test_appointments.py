from __future__ import annotations

import datetime as dt
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given as bdd_given, parsers, scenarios, then as bdd_then, when as bdd_when
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.appointments import models as _appointments_models  # noqa: F401
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.patients import models as _patients_models  # noqa: F401
from agile_ci_demo.staff import models as _staff_models  # noqa: F401

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
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def valid_patient_payload(**overrides: object) -> dict[str, object]:
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
    return payload


def valid_staff_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Dr. Alan Chua",
        "email": "alan.chua@example.com",
        "role": "doctor",
    }
    payload.update(overrides)
    return payload


def _register_patient(client: TestClient, **overrides: object) -> str:
    body = client.post("/api/patients", json=valid_patient_payload(**overrides)).json()
    return str(body["patient_id"])


def _register_doctor(client: TestClient, **overrides: object) -> str:
    body = client.post("/api/staff", json=valid_staff_payload(**overrides)).json()
    return str(body["staff_id"])


TOMORROW = (dt.date.today() + dt.timedelta(days=1)).isoformat()


def valid_appointment_payload(
    patient_id: str, doctor_id: str, **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": TOMORROW,
        "start_time": "10:00",
        "reason": "Fever and cough",
    }
    payload.update(overrides)
    return payload


# --- 1. Acceptance tests (docstring Given/When/Then) -------------------------


def test_book_appointment_success(client: TestClient) -> None:
    """
    Scenario: Book a new appointment
      Given a registered patient and an active doctor
      When I POST /api/appointments with a valid slot
      Then I receive 201 and a generated reference number
    """
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post("/api/appointments", json=valid_appointment_payload(patient_id, doctor_id))
    assert r.status_code == 201
    body = r.json()
    assert body["reference_number"].startswith("A")
    assert body["patient_id"] == patient_id
    assert body["patient_name"] == "Jane Tan"
    assert body["doctor_id"] == doctor_id
    assert body["doctor_name"] == "Dr. Alan Chua"
    assert body["start_time"] == "10:00:00"
    assert body["end_time"] == "10:30:00"
    assert body["status"] == "scheduled"


def test_book_appointment_then_fetch_by_reference(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    created = client.post(
        "/api/appointments", json=valid_appointment_payload(patient_id, doctor_id)
    ).json()

    r = client.get(f"/api/appointments/{created['reference_number']}")
    assert r.status_code == 200
    assert r.json()["reference_number"] == created["reference_number"]


def test_get_unknown_appointment_returns_404(client: TestClient) -> None:
    r = client.get("/api/appointments/A99999")
    assert r.status_code == 404


def test_create_appointment_page_renders(client: TestClient) -> None:
    """The HTML appointment booking form page loads successfully."""
    r = client.get("/appointments/create")
    assert r.status_code == 200
    assert "Book Appointment" in r.text


# --- 2. Required field / validation tests -------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["patient_id", "doctor_id", "appointment_date", "start_time", "reason"],
)
def test_book_missing_required_field_returns_422(client: TestClient, missing_field: str) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    payload = valid_appointment_payload(patient_id, doctor_id)
    del payload[missing_field]

    r = client.post("/api/appointments", json=payload)
    assert r.status_code == 422


def test_book_unknown_patient_returns_404(client: TestClient) -> None:
    doctor_id = _register_doctor(client)
    r = client.post("/api/appointments", json=valid_appointment_payload("P99999", doctor_id))
    assert r.status_code == 404


def test_book_unknown_doctor_returns_404(client: TestClient) -> None:
    patient_id = _register_patient(client)
    r = client.post("/api/appointments", json=valid_appointment_payload(patient_id, "S99999"))
    assert r.status_code == 404


def test_book_with_non_doctor_staff_returns_404(client: TestClient) -> None:
    """A staff member who isn't a doctor (e.g. a nurse) cannot be booked as one."""
    patient_id = _register_patient(client)
    nurse_id = _register_doctor(
        client, full_name="Nurse Amy", email="amy@example.com", role="nurse"
    )

    r = client.post("/api/appointments", json=valid_appointment_payload(patient_id, nurse_id))
    assert r.status_code == 404


# --- 3. Slot availability tests -----------------------------------------------


def test_book_before_working_hours_returns_422(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, start_time="08:30"),
    )
    assert r.status_code == 422


def test_book_after_working_hours_returns_422(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, start_time="16:45"),
    )
    assert r.status_code == 422


def test_book_off_grid_time_returns_422(client: TestClient) -> None:
    """Start times must align to the 30-minute slot grid."""
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, start_time="10:15"),
    )
    assert r.status_code == 422


def test_book_past_date_returns_422(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, appointment_date=yesterday),
    )
    assert r.status_code == 422


# --- 4. Double-booking tests ---------------------------------------------------


def test_double_booking_same_doctor_same_slot_returns_409(client: TestClient) -> None:
    """
    Scenario: Prevent double-booking a doctor's slot
      Given a doctor already has an appointment at a given date/time
      When another patient is booked at the same doctor, date, and time
      Then I receive 409 Conflict
    """
    doctor_id = _register_doctor(client)
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")

    r1 = client.post("/api/appointments", json=valid_appointment_payload(patient_a, doctor_id))
    assert r1.status_code == 201

    r2 = client.post("/api/appointments", json=valid_appointment_payload(patient_b, doctor_id))
    assert r2.status_code == 409


def test_different_doctor_same_slot_succeeds(client: TestClient) -> None:
    """Two different doctors can be booked for the same date/time - only the same
    doctor's own schedule can conflict."""
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")
    doctor_a = _register_doctor(client, full_name="Dr. Alan Chua", email="alan@example.com")
    doctor_b = _register_doctor(client, full_name="Dr. Betty Lim", email="betty@example.com")

    r1 = client.post("/api/appointments", json=valid_appointment_payload(patient_a, doctor_a))
    assert r1.status_code == 201

    r2 = client.post("/api/appointments", json=valid_appointment_payload(patient_b, doctor_b))
    assert r2.status_code == 201


def test_same_doctor_different_slot_succeeds(client: TestClient) -> None:
    doctor_id = _register_doctor(client)
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")

    r1 = client.post("/api/appointments", json=valid_appointment_payload(patient_a, doctor_id))
    assert r1.status_code == 201

    r2 = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_b, doctor_id, start_time="10:30"),
    )
    assert r2.status_code == 201


# --- 5. Doctor's daily schedule tests -------------------------------------------


def test_get_schedule_returns_current_doctors_appointments(client: TestClient) -> None:
    """
    Scenario: View my appointment list for a given day
      Given I am the (only, and therefore "current") doctor with two appointments
        booked out of order
      When I GET /api/appointments/schedule for that date
      Then I receive both appointments ordered by start time ascending
    """
    doctor_id = _register_doctor(client)
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")

    client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_a, doctor_id, start_time="11:00"),
    )
    client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_b, doctor_id, start_time="09:00"),
    )

    r = client.get("/api/appointments/schedule", params={"date": TOMORROW})
    assert r.status_code == 200
    body = r.json()
    assert body["doctor_id"] == doctor_id
    assert body["schedule_date"] == TOMORROW
    assert [a["start_time"] for a in body["appointments"]] == ["09:00:00", "11:00:00"]
    assert [a["patient_name"] for a in body["appointments"]] == ["John Lee", "Jane Tan"]


def test_get_schedule_excludes_other_doctors_appointments(client: TestClient) -> None:
    """The schedule for the current (first) doctor must not include another doctor's
    appointments, even on the same date and time."""
    first_doctor = _register_doctor(client, full_name="Dr. Alan Chua", email="alan@example.com")
    other_doctor = _register_doctor(client, full_name="Dr. Betty Lim", email="betty@example.com")
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")

    client.post("/api/appointments", json=valid_appointment_payload(patient_a, first_doctor))
    client.post("/api/appointments", json=valid_appointment_payload(patient_b, other_doctor))

    r = client.get("/api/appointments/schedule", params={"date": TOMORROW})
    assert r.status_code == 200
    body = r.json()
    assert body["doctor_id"] == first_doctor
    assert len(body["appointments"]) == 1
    assert body["appointments"][0]["patient_name"] == "Jane Tan"


def test_get_schedule_defaults_to_today_with_no_appointments(client: TestClient) -> None:
    """With no date param, the schedule defaults to today's date."""
    _register_doctor(client)

    r = client.get("/api/appointments/schedule")
    assert r.status_code == 200
    body = r.json()
    assert body["schedule_date"] == dt.date.today().isoformat()
    assert body["appointments"] == []


def test_get_schedule_past_date_returns_422(client: TestClient) -> None:
    _register_doctor(client)
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()

    r = client.get("/api/appointments/schedule", params={"date": yesterday})
    assert r.status_code == 422


def test_get_schedule_no_doctor_returns_404(client: TestClient) -> None:
    """If no doctor account exists at all, there is no "current doctor" to show."""
    r = client.get("/api/appointments/schedule", params={"date": TOMORROW})
    assert r.status_code == 404


def test_schedule_page_renders(client: TestClient) -> None:
    """The HTML doctor schedule page loads successfully."""
    r = client.get("/appointments/schedule")
    assert r.status_code == 200
    assert "My Schedule" in r.text


# --- 6. BDD-style tests with pytest-bdd --------------------------------------
# Feature file: tests/features/appointments.feature

scenarios("features/appointments.feature")


class Context:
    def __init__(self) -> None:
        self.last_response = None  # type: ignore[assignment]
        self.patient_id: str = ""
        self.doctor_id: str = ""


@pytest.fixture
def context() -> Context:
    return Context()


@bdd_given("the clinic portal API is running", target_fixture="api_is_running")
def api_is_running(client: TestClient) -> dict:
    return {"client": client}


@bdd_given("a registered patient and an active doctor")
def a_patient_and_doctor_exist(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.patient_id = _register_patient(client)
    context.doctor_id = _register_doctor(client)


@bdd_when("I book an appointment for that patient and doctor at a valid slot")
def book_valid_appointment_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.post(
        "/api/appointments",
        json=valid_appointment_payload(context.patient_id, context.doctor_id),
    )


@bdd_when("that doctor already has an appointment at the same date and time")
def doctor_already_booked_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    client.post(
        "/api/appointments",
        json=valid_appointment_payload(context.patient_id, context.doctor_id),
    )


@bdd_when("I try to book another appointment with that doctor at the same date and time")
def book_conflicting_appointment_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    other_patient = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")
    context.last_response = client.post(
        "/api/appointments",
        json=valid_appointment_payload(other_patient, context.doctor_id),
    )


@bdd_given("that doctor has an appointment booked for tomorrow")
def doctor_has_tomorrow_appointment_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    client.post(
        "/api/appointments",
        json=valid_appointment_payload(context.patient_id, context.doctor_id),
    )


@bdd_when("I view that doctor's schedule for tomorrow")
def view_schedule_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.get("/api/appointments/schedule", params={"date": TOMORROW})


@bdd_then("the schedule includes that appointment")
def schedule_includes_appointment_step(context: Context) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == 200
    names = [a["patient_name"] for a in context.last_response.json()["appointments"]]
    assert "Jane Tan" in names


@bdd_then("the appointment is booked with a generated reference number")
def appointment_is_booked_step(context: Context) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == 201
    body = context.last_response.json()
    assert body["reference_number"].startswith("A")


@bdd_then(parsers.parse("I receive a {status_code:d} response"))
def i_receive_status_code_step(context: Context, status_code: int) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == status_code
