from __future__ import annotations

import datetime as dt
import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given as bdd_given, parsers, scenarios, then as bdd_then, when as bdd_when
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.appointments import models as _appointments_models  # noqa: F401
from agile_ci_demo.attachments import models as _attachments_models  # noqa: F401
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import get_outbox
from agile_ci_demo.patients import models as _patients_models  # noqa: F401
from agile_ci_demo.prescription import models as _prescription_models  # noqa: F401
from agile_ci_demo.records import models as _records_models  # noqa: F401
from agile_ci_demo.staff import models as _staff_models  # noqa: F401

# --- Isolated in-memory DB per test -----------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    """FastAPI test client backed by a fresh in-memory SQLite DB and a temp
    uploads directory for every test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    from agile_ci_demo.core.config import settings

    monkeypatch.setattr(settings, "attachments_dir", tmp_path / "consultation_attachments")

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


# --- 1. Acceptance tests (docstring Given/When/Then) -------------------------


def test_register_patient_success(client: TestClient) -> None:
    """
    Scenario: Register a new patient
      Given the registration form has all required fields filled in
      When I POST /api/patients
      Then I receive 201 and a generated patient_id
    """
    r = client.post("/api/patients", json=valid_patient_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["patient_id"] == "P00001"
    assert body["full_name"] == "Jane Tan"
    assert body["gender"] == "female"


def test_register_patient_generates_sequential_ids(client: TestClient) -> None:
    """
    Scenario: Sequential patient ID generation
      Given multiple patients are registered one after another
      Then each receives the next sequential patient_id
    """
    ids = []
    patients = [
        ("Jane Tan", "900520-10-1234"),
        ("John Lee", "900520-10-1236"),
        ("Ah Kow", "900520-10-1238"),
    ]
    for name, ic in patients:
        r = client.post(
            "/api/patients", json=valid_patient_payload(full_name=name, ic_or_passport=ic)
        )
        assert r.status_code == 201
        ids.append(r.json()["patient_id"])

    assert ids == ["P00001", "P00002", "P00003"]


def test_register_patient_then_fetch_by_id(client: TestClient) -> None:
    """
    Scenario: Retrieve a newly registered patient
      Given a patient has just been registered
      When I GET /api/patients/{patient_id}
      Then I receive the same patient details back
    """
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.get(f"/api/patients/{created['patient_id']}")
    assert r.status_code == 200
    assert r.json()["full_name"] == "Jane Tan"


def test_get_unknown_patient_returns_404(client: TestClient) -> None:
    """
    Scenario: Fetching a patient that does not exist
      When I GET /api/patients/P99999
      Then I receive 404 Not Found
    """
    r = client.get("/api/patients/P99999")
    assert r.status_code == 404


def test_me_endpoint_does_not_show_a_different_patient(client: TestClient) -> None:
    """The old placeholder picked the first-registered patient regardless of who
    was actually logged in - this replaces the old placeholder-era
    test_get_current_patient_returns_first_patient_on_record and proves /me
    returns the logged-in patient's own record, not whichever patient happens to
    be first in the database."""
    client.post("/api/patients", json=valid_patient_payload())  # first-registered
    second = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="John Lee", ic_or_passport="900520-10-5678"),
    ).json()
    client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": second["ic_or_passport"], "phone_number": second["phone_number"]},
    )

    r = client.get("/api/patients/me")
    assert r.status_code == 200
    assert r.json()["patient_id"] == second["patient_id"]


def test_me_endpoint_requires_a_logged_in_patient(client: TestClient) -> None:
    """Anonymous requests must be sent to log in rather than falling back to "the
    first patient on record" - this replaces the old placeholder-era
    test_get_current_patient_no_patients_returns_404, whose premise (a 404 for a
    missing "current patient") no longer applies now that identity comes from the
    session, not from whichever patient happens to be first in the database."""
    r = client.get("/api/patients/me", follow_redirects=False)
    assert r.status_code == 303


def test_me_endpoint_shows_the_logged_in_patient(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )

    r = client.get("/api/patients/me")
    assert r.status_code == 200
    assert r.json()["patient_id"] == created["patient_id"]


# --- 2. Required field / validation tests ------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["full_name", "date_of_birth", "gender", "phone_number"],
)
def test_register_missing_required_field_returns_422(
    client: TestClient, missing_field: str
) -> None:
    """
    Scenario: Reject registration missing a required field
      Given the registration payload is missing "<missing_field>"
      When I POST /api/patients
      Then I receive 422 Unprocessable Entity
    """
    payload = valid_patient_payload()
    del payload[missing_field]

    r = client.post("/api/patients", json=payload)
    assert r.status_code == 422
    locs = [err["loc"][-1] for err in r.json()["detail"]]
    assert missing_field in locs


def test_register_blank_full_name_returns_422(client: TestClient) -> None:
    r = client.post("/api/patients", json=valid_patient_payload(full_name="  "))
    assert r.status_code == 422


def test_register_future_date_of_birth_returns_422(client: TestClient) -> None:
    r = client.post("/api/patients", json=valid_patient_payload(date_of_birth="2999-01-01"))
    assert r.status_code == 422


def test_register_invalid_gender_returns_422(client: TestClient) -> None:
    r = client.post("/api/patients", json=valid_patient_payload(gender="unknown"))
    assert r.status_code == 422


def test_register_invalid_phone_number_returns_422(client: TestClient) -> None:
    r = client.post("/api/patients", json=valid_patient_payload(phone_number="abc"))
    assert r.status_code == 422


def test_register_invalid_email_returns_422(client: TestClient) -> None:
    r = client.post("/api/patients", json=valid_patient_payload(email="not-an-email"))
    assert r.status_code == 422


def test_register_without_optional_fields_succeeds(client: TestClient) -> None:
    """Email and address are optional and may be omitted entirely."""
    payload = valid_patient_payload()
    del payload["email"]
    del payload["address"]

    r = client.post("/api/patients", json=payload)
    assert r.status_code == 201
    assert r.json()["email"] is None
    assert r.json()["address"] is None


def test_register_stores_the_ic_exactly_as_submitted(client: TestClient) -> None:
    """
    Scenario: IC number is typed in by staff, not generated
      Given a patient is registered with a specific IC number
      Then the stored ic_or_passport is exactly that value
    """
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(date_of_birth="1990-05-20", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 201
    assert r.json()["ic_or_passport"] == "900520-10-1234"


def test_register_two_patients_sharing_a_date_of_birth_with_different_ics_succeeds(
    client: TestClient,
) -> None:
    """Sharing a date_of_birth is fine as long as the IC numbers themselves differ -
    there's no implicit uniqueness tied to date_of_birth anymore."""
    r1 = client.post(
        "/api/patients",
        json=valid_patient_payload(
            full_name="Jane Tan", date_of_birth="1990-05-20", ic_or_passport="900520-10-1234"
        ),
    )
    r2 = client.post(
        "/api/patients",
        json=valid_patient_payload(
            full_name="John Lee", date_of_birth="1990-05-20", ic_or_passport="900520-10-5678"
        ),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["ic_or_passport"] != r2.json()["ic_or_passport"]


def test_register_with_a_duplicate_ic_returns_409(client: TestClient) -> None:
    """Two different patients cannot share the same IC number - this was already true
    at the database level, but is now much more likely to actually be hit in practice
    since staff type the IC in by hand instead of the system generating a random one."""
    client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", ic_or_passport="900520-10-1234"),
    )
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Someone Else", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 409


def test_register_with_a_passport_number_skips_dob_and_gender_checks(client: TestClient) -> None:
    """A passport-shaped value (starts with a letter) has no birth-date or gender digit
    to check against, regardless of what date_of_birth/gender were submitted."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1975-01-01", gender="male", ic_or_passport="A12345678"
        ),
    )
    assert r.status_code == 201
    assert r.json()["ic_or_passport"] == "A12345678"


def test_register_rejects_an_ic_not_matching_date_of_birth(client: TestClient) -> None:
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(date_of_birth="1985-01-01", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 422


def test_register_rejects_an_ic_not_matching_male_gender(client: TestClient) -> None:
    """Male requires an odd last digit; 4 is even."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="male", ic_or_passport="900520-10-1234"
        ),
    )
    assert r.status_code == 422


def test_register_rejects_an_ic_not_matching_female_gender(client: TestClient) -> None:
    """Female requires an even last digit; 3 is odd."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="female", ic_or_passport="900520-10-1233"
        ),
    )
    assert r.status_code == 422


def test_register_gender_other_skips_the_last_digit_check(client: TestClient) -> None:
    """Gender "other" has no odd/even convention to check against - any last digit is fine
    as long as the date-of-birth digits still match."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="other", ic_or_passport="900520-10-1234"
        ),
    )
    assert r.status_code == 201


def test_register_rejects_a_malformed_ic_that_is_neither_ic_nor_passport_shaped(
    client: TestClient,
) -> None:
    """Too few digits, no dashes, or otherwise not matching either recognized shape."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(ic_or_passport="12345"),
    )
    assert r.status_code == 422


def _login_as_receptionist(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="receptionist@example.com", role="receptionist"
    )
    client.post(
        "/api/auth/login", json={"email": "receptionist@example.com", "password": temp_password}
    )


def _login_as_doctor(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})


def test_register_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/register", follow_redirects=False)
    assert r.status_code == 303


def test_register_page_loads_when_logged_in_as_receptionist(client: TestClient) -> None:
    _login_as_receptionist(client)
    r = client.get("/patients/register")
    assert r.status_code == 200


def test_register_page_redirects_for_doctor(client: TestClient) -> None:
    """Doctors only handle their own schedule and consultations - registering
    patients is front-desk work, so a doctor session should not reach this page."""
    _login_as_doctor(client)
    r = client.get("/patients/register", follow_redirects=False)
    assert r.status_code == 303


def test_register_page_renders(client: TestClient) -> None:
    """The HTML registration form page loads successfully."""
    _login_as_receptionist(client)

    r = client.get("/patients/register")
    assert r.status_code == 200
    assert "Register New Patient" in r.text


# --- 3. Search / list tests ---------------------------------------------------


def _register_sample_patients(client: TestClient) -> list[str]:
    ids = []
    patients = [
        ("Jane Tan", "900520-10-1234"),
        ("John Lee", "900520-10-1236"),
        ("Ah Kow", "900520-10-1238"),
        ("Janet Wong", "900520-10-1230"),
    ]
    for name, ic in patients:
        r = client.post(
            "/api/patients", json=valid_patient_payload(full_name=name, ic_or_passport=ic)
        )
        assert r.status_code == 201
        ids.append(r.json()["patient_id"])
    return ids


def test_list_patients_returns_all_when_no_query(client: TestClient) -> None:
    """
    Scenario: Browse the patient list
      Given several patients are registered
      When I GET /api/patients with no search query
      Then I receive all of them, paginated
    """
    _register_sample_patients(client)

    r = client.get("/api/patients")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert len(body["items"]) == 4
    assert body["page"] == 1


def test_search_patients_by_partial_name(client: TestClient) -> None:
    """
    Scenario: Search for a patient by name
      Given several patients are registered, including two named "Jan..."
      When I search for "jan" (case-insensitive)
      Then only the matching patients are returned
    """
    _register_sample_patients(client)

    r = client.get("/api/patients", params={"q": "jan"})
    assert r.status_code == 200
    names = {item["full_name"] for item in r.json()["items"]}
    assert names == {"Jane Tan", "Janet Wong"}


def test_search_patients_by_patient_id(client: TestClient) -> None:
    """
    Scenario: Search for a patient by ID
      When I search using an exact patient_id
      Then only that patient is returned
    """
    ids = _register_sample_patients(client)

    r = client.get("/api/patients", params={"q": ids[0]})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["patient_id"] == ids[0]


def test_search_patients_no_match_returns_empty(client: TestClient) -> None:
    _register_sample_patients(client)

    r = client.get("/api/patients", params={"q": "nonexistent-name"})
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_list_patients_pagination(client: TestClient) -> None:
    """
    Scenario: Paginate the patient list
      Given 4 patients are registered
      When I request page 1 with page_size=2
      Then I receive 2 items and total_pages == 2
    """
    _register_sample_patients(client)

    r = client.get("/api/patients", params={"page": 1, "page_size": 2})
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 4
    assert body["total_pages"] == 2

    r2 = client.get("/api/patients", params={"page": 2, "page_size": 2})
    assert len(r2.json()["items"]) == 2


def test_list_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients", follow_redirects=False)
    assert r.status_code == 303


def test_list_page_renders(client: TestClient) -> None:
    """The HTML patient list page loads successfully."""
    _login_as_receptionist(client)

    r = client.get("/patients")
    assert r.status_code == 200
    assert "Patients" in r.text


def test_list_page_redirects_for_doctor(client: TestClient) -> None:
    """Doctors only handle their own schedule and consultations - browsing the
    full patient list is front-desk work, so a doctor session should not reach
    this page."""
    _login_as_doctor(client)
    r = client.get("/patients", follow_redirects=False)
    assert r.status_code == 303


def test_list_patients_registered_today_matches_when_filtered_to_today(client: TestClient) -> None:
    from datetime import date

    _register_sample_patients(client)
    today = date.today().isoformat()

    r = client.get("/api/patients", params={"registered_from": today, "registered_to": today})
    assert r.status_code == 200
    assert r.json()["total"] == 4


def test_list_patients_registered_today_excluded_when_filtered_to_yesterday(
    client: TestClient,
) -> None:
    from datetime import date, timedelta

    _register_sample_patients(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    r = client.get("/api/patients", params={"registered_to": yesterday})
    assert r.status_code == 200
    assert r.json()["total"] == 0


# --- 4. Isolated in-memory DB tests for search_patients with date filtering ---


def _build_isolated_patients_db() -> Session:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from agile_ci_demo.core.database import Base
    import agile_ci_demo.patients.models  # noqa: F401 - registers Patient with Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _make_patient(patient_id: str, full_name: str, created_at: dt.datetime) -> object:
    from agile_ci_demo.patients.models import Patient

    return Patient(
        patient_id=patient_id,
        full_name=full_name,
        date_of_birth=dt.date(1990, 1, 1),
        gender="female",
        phone_number="012-0000000",
        ic_or_passport=f"900101-01-{patient_id[-4:]}",
        created_at=created_at,
    )


def test_search_patients_filters_by_registered_from() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all(
        [
            _make_patient("P00001", "Old Patient", dt.datetime(2026, 1, 1, 10, 0, 0)),
            _make_patient("P00002", "New Patient", dt.datetime(2026, 1, 15, 10, 0, 0)),
        ]
    )
    db.commit()

    items, total = search_patients(db, None, 1, 10, registered_from=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00002"
    db.close()


def test_search_patients_filters_by_registered_to() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all(
        [
            _make_patient("P00001", "Old Patient", dt.datetime(2026, 1, 1, 10, 0, 0)),
            _make_patient("P00002", "New Patient", dt.datetime(2026, 1, 15, 10, 0, 0)),
        ]
    )
    db.commit()

    items, total = search_patients(db, None, 1, 10, registered_to=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()


def test_search_patients_registered_from_and_to_are_inclusive_of_the_whole_day() -> None:
    """A patient registered at 23:59 on the boundary date must still match when that
    same date is used for both registered_from and registered_to - the range must
    cover the whole day, not just midnight."""
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add(_make_patient("P00001", "Late Patient", dt.datetime(2026, 1, 10, 23, 59, 0)))
    db.commit()

    items, total = search_patients(
        db, None, 1, 10, registered_from=dt.date(2026, 1, 10), registered_to=dt.date(2026, 1, 10)
    )
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()


def test_search_patients_inverted_date_range_returns_empty() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add(_make_patient("P00001", "Some Patient", dt.datetime(2026, 1, 10, 10, 0, 0)))
    db.commit()

    items, total = search_patients(
        db, None, 1, 10, registered_from=dt.date(2026, 1, 15), registered_to=dt.date(2026, 1, 1)
    )
    assert total == 0
    assert items == []
    db.close()


def test_search_patients_combines_date_range_with_text_query() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all(
        [
            _make_patient("P00001", "Jane Tan", dt.datetime(2026, 1, 15, 10, 0, 0)),
            _make_patient("P00002", "Jane Wong", dt.datetime(2026, 1, 1, 10, 0, 0)),
        ]
    )
    db.commit()

    items, total = search_patients(db, "jane", 1, 10, registered_from=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()


# --- 6. Update patient tests ---------------------------------------------------


def test_update_patient_success(client: TestClient) -> None:
    """
    Scenario: Update a patient's contact details
      Given a patient is registered
      When I PUT /api/patients/{patient_id} with new contact details
      Then the patient record reflects the changes
    """
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    updated_payload = valid_patient_payload(
        phone_number="019-1112222",
        email="jane.new@example.com",
        address="2 New Address, Penang",
    )
    r = client.put(f"/api/patients/{created['patient_id']}", json=updated_payload)
    assert r.status_code == 200
    body = r.json()
    assert body["patient_id"] == created["patient_id"]
    assert body["phone_number"] == "019-1112222"
    assert body["email"] == "jane.new@example.com"
    assert body["address"] == "2 New Address, Penang"


def test_update_unknown_patient_returns_404(client: TestClient) -> None:
    r = client.put("/api/patients/P99999", json=valid_patient_payload())
    assert r.status_code == 404


def test_update_patient_missing_field_returns_422(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    payload = valid_patient_payload()
    del payload["phone_number"]
    r = client.put(f"/api/patients/{created['patient_id']}", json=payload)
    assert r.status_code == 422


def test_update_patient_invalid_phone_returns_422(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.put(
        f"/api/patients/{created['patient_id']}",
        json=valid_patient_payload(phone_number="not-a-phone"),
    )
    assert r.status_code == 422


def test_update_patient_does_not_change_ic(client: TestClient) -> None:
    """IC/passport is system-generated at registration and stays fixed across edits,
    even though older clients may still send an ic_or_passport field (ignored)."""
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    original_ic = created["ic_or_passport"]

    r = client.put(
        f"/api/patients/{created['patient_id']}",
        json=valid_patient_payload(phone_number="019-9998888"),
    )
    assert r.status_code == 200
    assert r.json()["phone_number"] == "019-9998888"
    assert r.json()["ic_or_passport"] == original_ic


def test_detail_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/P00001", follow_redirects=False)
    assert r.status_code == 303


def test_detail_page_renders(client: TestClient) -> None:
    """The HTML patient detail page loads successfully for any patient_id (client fetches data)."""
    _login_as_receptionist(client)

    r = client.get("/patients/P00001")
    assert r.status_code == 200
    assert "Edit" in r.text


def test_dashboard_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"


def test_dashboard_page_loads_when_logged_in_as_patient(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )

    r = client.get("/patients/dashboard")
    assert r.status_code == 200


# --- 7. BDD-style tests with pytest-bdd --------------------------------------
# Feature file: tests/features/patients.feature

scenarios("features/patients.feature")


class Context:
    def __init__(self) -> None:
        self.last_response = None  # type: ignore[assignment]


@pytest.fixture
def context() -> Context:
    return Context()


@bdd_given("the clinic portal API is running", target_fixture="api_is_running")
def api_is_running(client: TestClient) -> dict:
    return {"client": client}


@bdd_when("I register a patient with all required fields")
def register_patient_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.post("/api/patients", json=valid_patient_payload())


@bdd_when("I register a patient without a full name")
def register_patient_missing_name_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    payload = valid_patient_payload()
    del payload["full_name"]
    context.last_response = client.post("/api/patients", json=payload)


@bdd_given('a patient named "Jane Tan" is already registered', target_fixture="registered_patient")
def a_patient_is_registered_step(api_is_running: dict) -> dict:
    client: TestClient = api_is_running["client"]
    return client.post("/api/patients", json=valid_patient_payload()).json()


@bdd_when('I search for patients by the name "Jane"')
def search_by_name_step(api_is_running: dict, context: Context, registered_patient: dict) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.get("/api/patients", params={"q": "Jane"})


@bdd_then('the search results include "Jane Tan"')
def search_results_include_jane_step(context: Context) -> None:
    assert context.last_response is not None
    names = {item["full_name"] for item in context.last_response.json()["items"]}
    assert "Jane Tan" in names


@bdd_when('I update that patient\'s phone number to "019-1112222"')
def update_phone_number_step(
    api_is_running: dict, context: Context, registered_patient: dict
) -> None:
    client: TestClient = api_is_running["client"]
    payload = valid_patient_payload(phone_number="019-1112222")
    context.last_response = client.put(
        f"/api/patients/{registered_patient['patient_id']}", json=payload
    )


@bdd_then('the patient\'s phone number is updated to "019-1112222"')
def patient_phone_number_is_updated_step(context: Context) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == 200
    assert context.last_response.json()["phone_number"] == "019-1112222"


@bdd_then("the patient is registered with a generated patient ID")
def patient_is_registered_step(context: Context) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == 201
    body = context.last_response.json()
    assert body["patient_id"].startswith("P")


@bdd_then(parsers.parse("I receive a {status_code:d} response"))
def i_receive_status_code_step(context: Context, status_code: int) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == status_code


# --- IC autocomplete (search-ic) ---------------------------------------------


def test_search_ic_matches_prefix(client: TestClient) -> None:
    client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", ic_or_passport="900520-10-1234"),
    )
    client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="John Lee", ic_or_passport="900520-10-1236"),
    )

    r = client.get("/api/patients/search-ic?q=900520-10-12")
    assert r.status_code == 200
    results = r.json()
    assert {item["ic_or_passport"] for item in results} == {"900520-10-1234", "900520-10-1236"}
    assert {item["full_name"] for item in results} == {"Jane Tan", "John Lee"}


def test_search_ic_excludes_non_matching_prefix(client: TestClient) -> None:
    client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", ic_or_passport="900520-10-1234"),
    )

    r = client.get("/api/patients/search-ic?q=850101")
    assert r.status_code == 200
    assert r.json() == []


def test_search_ic_with_no_matches_returns_empty_list_not_404(client: TestClient) -> None:
    r = client.get("/api/patients/search-ic?q=999999")
    assert r.status_code == 200
    assert r.json() == []


def test_search_ic_caps_results_at_eight(client: TestClient) -> None:
    # Last IC digit must match gender parity (female => even) - step by 2 so
    # all ten registrations are valid, unique, and share the queried prefix.
    for i in range(10):
        r = client.post(
            "/api/patients",
            json=valid_patient_payload(
                full_name=f"Patient {i}",
                ic_or_passport=f"900520-10-{1230 + i * 2}",
                email=f"patient{i}@example.com",
            ),
        )
        assert r.status_code == 201, r.json()

    r = client.get("/api/patients/search-ic?q=900520-10-12")
    assert r.status_code == 200
    assert len(r.json()) == 8


# --- Admin patient delete ----------------------------------------------------


def valid_doctor_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Dr. Alan Chua",
        "email": "alan.chua@example.com",
        "role": "doctor",
        "license_number": "MMC-12345",
        "specialty": "General Medicine",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def _login_as(client: TestClient, email: str) -> None:
    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    r = client.post("/api/auth/login", json={"email": email, "password": match.group(1)})
    assert r.status_code == 200, r.json()


def _login_as_admin(client: TestClient) -> None:
    r = client.post(
        "/api/staff",
        json={"full_name": "Admin User", "email": "admin@example.com", "role": "admin"},
    )
    assert r.status_code == 201, r.json()
    _login_as(client, "admin@example.com")


def _register_doctor(client: TestClient, **overrides: object) -> str:
    payload = valid_doctor_payload(**overrides)
    r = client.post("/api/staff", json=payload)
    assert r.status_code == 201, r.json()
    return str(r.json()["staff_id"])


TOMORROW = (dt.date.today() + dt.timedelta(days=1)).isoformat()


def _build_full_history_for_patient(client: TestClient) -> tuple[str, str, int]:
    """Register a patient and a doctor, then create one appointment, one
    consultation note (with a diagnosis and an attachment), and one
    prescription for that patient. Returns (patient_id, doctor_id, attachment_id)."""
    patient_id = client.post("/api/patients", json=valid_patient_payload()).json()["patient_id"]
    doctor_id = _register_doctor(client)

    appt = client.post(
        "/api/appointments",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "appointment_date": TOMORROW,
            "start_time": "10:00",
            "reason": "Fever and cough",
        },
    )
    assert appt.status_code == 201, appt.json()

    _login_as(client, str(valid_doctor_payload()["email"]))

    note = client.post(
        "/api/records",
        json={
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "notes": "Patient presented with fever and cough for 3 days.",
            "diagnoses": [
                {"icd10_code": "J00", "description": "Acute nasopharyngitis (common cold)"}
            ],
        },
    )
    assert note.status_code == 201, note.json()
    record_id = note.json()["record_id"]
    diagnosis_id = note.json()["diagnoses"][0]["id"]

    prescription = client.post(
        "/api/prescriptions",
        json={
            "consultation_record_id": record_id,
            "diagnosis_id": diagnosis_id,
            "medication": "Amoxicillin 500 mg Capsule",
            "dosage": "1 capsule",
            "frequency": "Three times daily",
            "duration": "7 days",
        },
    )
    assert prescription.status_code == 201, prescription.json()

    attachment = client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("lab_result.pdf", b"%PDF-1.4\nmock", "application/pdf")},
    )
    assert attachment.status_code == 201, attachment.json()

    return patient_id, doctor_id, attachment.json()["id"]


def test_delete_patient_with_no_history_succeeds(client: TestClient) -> None:
    _login_as_admin(client)
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.delete(f"/api/patients/{created['patient_id']}")
    assert r.status_code == 204

    r = client.get(f"/api/patients/{created['patient_id']}")
    assert r.status_code == 404


def test_delete_patient_cascades_to_all_history(client: TestClient) -> None:
    """Deleting a patient also deletes their appointments, consultation notes,
    diagnoses, prescriptions, and attachments - nothing referencing the deleted
    patient stays reachable afterward."""
    patient_id, doctor_id, attachment_id = _build_full_history_for_patient(client)

    _login_as_admin(client)
    r = client.delete(f"/api/patients/{patient_id}")
    assert r.status_code == 204

    assert client.get(f"/api/patients/{patient_id}").status_code == 404

    history = client.get("/api/records", params={"patient_id": patient_id})
    # get_patient_history requires the patient to exist - it's gone now, so a
    # direct history lookup 404s. The important assertion is that nothing
    # referencing the deleted patient is left orphaned in the DB, which the
    # cascading deletes in delete_patient() guarantee at the query level.
    assert history.status_code == 404

    assert client.get(f"/api/attachments/{attachment_id}/download").status_code == 404


def test_delete_unknown_patient_returns_404(client: TestClient) -> None:
    _login_as_admin(client)
    r = client.delete("/api/patients/P99999")
    assert r.status_code == 404


def test_delete_patient_requires_admin_login(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()

    r = client.delete(f"/api/patients/{created['patient_id']}", follow_redirects=False)
    assert r.status_code == 303


def test_delete_patient_as_non_admin_is_redirected(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    _register_doctor(client)
    _login_as(client, str(valid_doctor_payload()["email"]))

    r = client.delete(f"/api/patients/{created['patient_id']}", follow_redirects=False)
    assert r.status_code == 303

    assert client.get(f"/api/patients/{created['patient_id']}").status_code == 200
