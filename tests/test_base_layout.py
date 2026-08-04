from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
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


def create_staff_and_login(client: TestClient, role: str = "receptionist") -> None:
    payload: dict[str, object] = {
        "full_name": "Nora Ibrahim",
        "email": f"{role}@example.com",
        "role": role,
    }
    if role == "doctor":
        payload.update(
            {
                "license_number": "MMC-90001",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    create_response = client.post("/api/staff", json=payload)
    assert create_response.status_code == 201, create_response.json()

    welcome_email = next(
        message for message in reversed(get_outbox()) if message.to == payload["email"]
    )
    match = re.search(r"temporary password is: (\S+)", welcome_email.body)
    assert match is not None

    login_response = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": match.group(1)},
    )
    assert login_response.status_code == 200, login_response.json()


def create_patient_and_login(client: TestClient) -> None:
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "email": "jane.tan@example.com",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    login_response = client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )
    assert login_response.status_code == 200, login_response.json()


@pytest.mark.parametrize("role", ["receptionist", "nurse"])
def test_receptionist_and_nurse_see_front_desk_sidebar_links(
    client: TestClient, role: str
) -> None:
    create_staff_and_login(client, role)

    response = client.get("/patients")

    assert response.status_code == 200
    assert '<a class="sidebar-link active" href="/patients">Patients</a>' in response.text
    assert (
        '<a class="sidebar-link" href="/patients/register">Register Patient</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/create">Book Appointment</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/doctor-schedule">Doctor Schedule</a>'
        in response.text
    )
    assert 'href="/staff"' not in response.text
    assert 'href="/appointments/consultations"' not in response.text

    if role == "nurse":
        assert 'href="/pharmacy"' not in response.text


def test_admin_sees_pharmacy_staff_and_reports_sidebar_links(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert '<a class="sidebar-link" href="/pharmacy">Pharmacy</a>' in response.text
    assert '<a class="sidebar-link" href="/staff">Staff</a>' in response.text
    assert '<a class="sidebar-link" href="/reports">Reports</a>' in response.text


def test_doctor_sees_schedule_and_consultation_sidebar_links(client: TestClient) -> None:
    create_staff_and_login(client, "doctor")

    response = client.get("/appointments/schedule")

    assert response.status_code == 200
    assert (
        '<a class="sidebar-link active" href="/appointments/schedule">My Schedule</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/consultations">Start Consultation</a>'
        in response.text
    )
    assert 'href="/patients"' not in response.text


def test_patient_sees_only_patient_sidebar_links(client: TestClient) -> None:
    create_patient_and_login(client)

    response = client.get("/patients/dashboard")

    assert response.status_code == 200
    assert (
        '<a class="sidebar-link active" href="/patients/dashboard">My Dashboard</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/book">Book My Appointment</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/mine">My Appointments</a>'
        in response.text
    )
    assert 'href="/staff"' not in response.text


def test_app_shell_wraps_authenticated_pages(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert 'id="app-sidebar"' in response.text
    assert 'class="app-shell"' in response.text


def test_login_page_renders_auth_shell_with_no_sidebar(client: TestClient) -> None:
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert 'class="auth-shell"' in response.text
    assert 'auth-card-wrap' in response.text
    assert 'id="app-sidebar"' not in response.text


def test_login_page_still_has_staff_and_patient_tabs(client: TestClient) -> None:
    """Regression check for the split-panel redesign: the tab toggle and both
    login forms must keep their exact ids - static/js/auth-login.js wires up
    to these ids and is not touched by this redesign."""
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert 'id="staff-tab-btn"' in response.text
    assert 'id="patient-tab-btn"' in response.text
    assert 'id="staff-login-form"' in response.text
    assert 'id="patient-login-form"' in response.text
    assert 'id="staff-submit-btn"' in response.text
    assert 'id="patient-submit-btn"' in response.text
    assert 'href="/auth/forgot-password"' in response.text
    assert 'login-split' in response.text


def test_forgot_password_page_keeps_single_card_layout(client: TestClient) -> None:
    """forgot_password.html is explicitly out of scope for the split-panel
    redesign, so it must render the plain single-class auth-card-wrap."""
    response = client.get("/auth/forgot-password")

    assert response.status_code == 200
    assert 'class="auth-card-wrap"' in response.text


def test_logout_link_requires_confirmation(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert 'id="logout-confirm-modal"' in response.text
    assert 'id="confirm-logout-btn"' in response.text


def test_doctor_schedule_page_has_stat_cards_and_view_toggle(client: TestClient) -> None:
    create_staff_and_login(client, "doctor")

    response = client.get("/appointments/schedule")

    assert response.status_code == 200
    assert 'id="stat-total"' in response.text
    assert 'id="stat-today"' in response.text
    assert 'id="stat-future"' in response.text
    assert 'id="stat-completed"' in response.text
    assert 'id="view-list-btn"' in response.text
    assert 'id="view-calendar-btn"' in response.text
    assert 'id="schedule-calendar"' in response.text


def test_receptionist_doctor_schedule_page_has_view_toggle(client: TestClient) -> None:
    create_staff_and_login(client, "receptionist")

    response = client.get("/appointments/doctor-schedule")

    assert response.status_code == 200
    assert 'id="view-list-btn"' in response.text
    assert 'id="view-calendar-btn"' in response.text
    assert 'id="schedule-calendar"' in response.text


@pytest.mark.parametrize("role", ["receptionist", "nurse", "doctor", "admin"])
def test_staff_sidebar_has_my_profile_link(client: TestClient, role: str) -> None:
    create_staff_and_login(client, role)

    response = client.get("/staff/profile")

    assert response.status_code == 200
    assert 'class="topbar-user topbar-user-link"' in response.text
    assert 'href="/staff/profile"' in response.text
    assert "Nora Ibrahim" in response.text


def test_patient_sidebar_has_no_my_profile_link(client: TestClient) -> None:
    create_patient_and_login(client)

    response = client.get("/patients/dashboard")

    assert response.status_code == 200
    assert 'href="/staff/profile"' not in response.text
    assert 'class="topbar-user"' in response.text
    assert 'class="topbar-user topbar-user-link"' not in response.text
    assert "Jane Tan" in response.text
