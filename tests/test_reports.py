from __future__ import annotations

import datetime as dt
from collections.abc import Generator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from pytest_bdd import given, scenarios, then, when
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.security import hash_password
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff

ADMIN_EMAIL = "reports.admin@example.com"
ADMIN_PASSWORD = "ReportsPass123!"


def week_start(reference_date: dt.date | None = None) -> dt.date:
    current_date = reference_date or dt.date.today()
    return current_date - dt.timedelta(days=current_date.weekday())


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine)

    with testing_session_local() as db:
        admin = Staff(
            staff_id="S90001",
            full_name="Amina Rahman",
            email=ADMIN_EMAIL,
            role="admin",
            password_hash=hash_password(ADMIN_PASSWORD),
            must_change_password=False,
            is_active=True,
        )
        nurse = Staff(
            staff_id="S90002",
            full_name="Nora Ibrahim",
            email="reports.nurse@example.com",
            role="nurse",
            password_hash=hash_password(ADMIN_PASSWORD),
            must_change_password=False,
            is_active=True,
        )
        doctor = Staff(
            staff_id="S90003",
            full_name="Dr. Alan Chua",
            email="reports.doctor@example.com",
            role="doctor",
            password_hash=hash_password(ADMIN_PASSWORD),
            must_change_password=False,
            is_active=True,
        )
        patient = Patient(
            patient_id="P90001",
            full_name="Jane Tan",
            date_of_birth=dt.date(1990, 5, 20),
            gender="female",
            phone_number="012-3456789",
            email="jane.tan@example.com",
            ic_or_passport="900520-10-1234",
            address="1 Jalan Testing, Kuala Lumpur",
        )
        db.add_all([admin, nurse, doctor, patient])
        db.flush()

        monday = week_start()
        appointments = [
            Appointment(
                reference_number="A90001",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=monday,
                start_time=dt.time(9, 0),
                end_time=dt.time(9, 30),
                reason="Annual review",
                status="scheduled",
            ),
            Appointment(
                reference_number="A90002",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=monday,
                start_time=dt.time(10, 0),
                end_time=dt.time(10, 30),
                reason="Follow-up",
                status="cancelled",
                cancellation_reason="Patient unavailable",
            ),
            Appointment(
                reference_number="A90003",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=monday + dt.timedelta(days=1),
                start_time=dt.time(11, 0),
                end_time=dt.time(11, 30),
                reason="Consultation",
                status="scheduled",
            ),
            Appointment(
                reference_number="A90004",
                patient_id=patient.id,
                doctor_id=doctor.id,
                appointment_date=monday - dt.timedelta(days=1),
                start_time=dt.time(12, 0),
                end_time=dt.time(12, 30),
                reason="Outside report range",
                status="scheduled",
            ),
        ]
        db.add_all(appointments)
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        test_client.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def login(
    client: TestClient,
    email: str = ADMIN_EMAIL,
) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.json()


def custom_range_params() -> dict[str, str]:
    monday = week_start()
    return {
        "from": monday.isoformat(),
        "to": (monday + dt.timedelta(days=2)).isoformat(),
    }


def test_admin_reports_dashboard_uses_current_week(
    client: TestClient,
) -> None:
    login(client)
    monday = week_start()

    response = client.get("/reports")

    assert response.status_code == 200
    assert 'id="reports-dashboard-root"' in response.text
    assert f'data-default-from="{monday.isoformat()}"' in response.text
    assert (f'data-default-to="' f'{(monday + dt.timedelta(days=6)).isoformat()}"') in response.text
    assert "/static/css/reports-dashboard.css" in response.text
    assert "/static/js/reports-dashboard.js" in response.text


def test_reports_dashboard_requires_admin(
    client: TestClient,
) -> None:
    login(client, "reports.nurse@example.com")

    response = client.get(
        "/reports",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_default_report_returns_every_day_in_current_week(
    client: TestClient,
) -> None:
    login(client)
    monday = week_start()

    response = client.get("/api/reports/appointments/daily")

    assert response.status_code == 200
    body = response.json()
    assert body["from_date"] == monday.isoformat()
    assert body["to_date"] == (monday + dt.timedelta(days=6)).isoformat()
    assert len(body["daily_totals"]) == 7
    assert body["daily_totals"][0] == {
        "date": monday.isoformat(),
        "total": 2,
    }
    assert body["daily_totals"][1]["total"] == 1
    assert body["daily_totals"][2]["total"] == 0
    assert body["total_appointments"] == 3


def test_custom_range_is_inclusive_and_fills_zero_days(
    client: TestClient,
) -> None:
    login(client)

    response = client.get(
        "/api/reports/appointments/daily",
        params=custom_range_params(),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["daily_totals"]) == 3
    assert [item["total"] for item in body["daily_totals"]] == [2, 1, 0]
    assert body["selected_range_label"].endswith(
        (week_start() + dt.timedelta(days=2)).strftime("%d %b %Y")
    )


@pytest.mark.parametrize(
    "params, expected_detail",
    [
        (
            {"from": "2026-07-10"},
            "Both 'from' and 'to' dates are required",
        ),
        (
            {
                "from": "2026-07-10",
                "to": "2026-07-01",
            },
            "must be on or before",
        ),
    ],
)
def test_invalid_report_ranges_return_422(
    client: TestClient,
    params: dict[str, str],
    expected_detail: str,
) -> None:
    login(client)

    response = client.get(
        "/api/reports/appointments/daily",
        params=params,
    )

    assert response.status_code == 422
    assert expected_detail in response.json()["detail"]


def test_report_api_requires_admin(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/reports/appointments/daily",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_pdf_export_download_contains_report_context(
    client: TestClient,
) -> None:
    login(client)
    params = custom_range_params()

    response = client.get(
        "/api/reports/appointments/daily/export.pdf",
        params=params,
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment;" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")

    reader = PdfReader(BytesIO(response.content))
    extracted_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert settings.clinic_name in extracted_text
    assert "Daily Appointment Activity Report" in extracted_text
    assert week_start().strftime("%d %b %Y") in extracted_text
    assert (week_start() + dt.timedelta(days=2)).strftime("%d %b %Y") in extracted_text


def test_reports_javascript_refreshes_and_downloads_pdf() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "static" / "js" / "reports-dashboard.js").read_text(encoding="utf-8")

    assert "selectedRangeParams()" in script
    assert "from: fromInput.value" in script
    assert "to: toInput.value" in script
    assert "/api/reports/appointments/daily?" in script
    assert "/api/reports/appointments/daily/export.pdf?" in script
    assert 'input.addEventListener("change"' in script
    assert "response.blob()" in script
    assert "downloadLink.click()" in script


scenarios("features/reports.feature")


class ReportScenarioContext:
    response = None


@pytest.fixture
def report_context() -> ReportScenarioContext:
    return ReportScenarioContext()


@given("an administrator is signed in for reporting")
def administrator_is_signed_in(
    client: TestClient,
) -> None:
    login(client)


@when("I request the default appointment activity report")
def request_default_report(
    client: TestClient,
    report_context: ReportScenarioContext,
) -> None:
    report_context.response = client.get("/api/reports/appointments/daily")


@then("the report contains every day in the current week")
def report_contains_current_week(
    report_context: ReportScenarioContext,
) -> None:
    assert report_context.response.status_code == 200
    assert len(report_context.response.json()["daily_totals"]) == 7


@when("I request appointment activity for a custom date range")
def request_custom_report(
    client: TestClient,
    report_context: ReportScenarioContext,
) -> None:
    report_context.response = client.get(
        "/api/reports/appointments/daily",
        params=custom_range_params(),
    )


@then("the report uses the selected custom date range")
def report_uses_custom_range(
    report_context: ReportScenarioContext,
) -> None:
    assert report_context.response.status_code == 200
    body = report_context.response.json()
    assert body["from_date"] == custom_range_params()["from"]
    assert body["to_date"] == custom_range_params()["to"]


@when("I export appointment activity for a custom date range")
def export_custom_report(
    client: TestClient,
    report_context: ReportScenarioContext,
) -> None:
    report_context.response = client.get(
        "/api/reports/appointments/daily/export.pdf",
        params=custom_range_params(),
    )


@then("a downloadable PDF report is returned")
def downloadable_pdf_is_returned(
    report_context: ReportScenarioContext,
) -> None:
    assert report_context.response.status_code == 200
    assert report_context.response.content.startswith(b"%PDF")
    assert "attachment;" in report_context.response.headers["content-disposition"]
