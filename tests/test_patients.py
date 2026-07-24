from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given as bdd_given, parsers, scenarios, then as bdd_then, when as bdd_when
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.patients import models as _patients_models  # noqa: F401

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
    for name in ("Jane Tan", "John Lee", "Ah Kow"):
        r = client.post("/api/patients", json=valid_patient_payload(full_name=name))
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
        json=valid_patient_payload(full_name="John Lee", ic_or_passport="880311-14-5678"),
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


def test_register_generates_ic_from_date_of_birth(client: TestClient) -> None:
    """
    Scenario: IC number is generated automatically, not client-supplied
      Given a patient is registered with date_of_birth "1990-05-20"
      Then the generated ic_or_passport starts with "900520-0" and is
        formatted YYMMDD-0X-XXXX
    """
    r = client.post("/api/patients", json=valid_patient_payload(date_of_birth="1990-05-20"))
    assert r.status_code == 201
    ic = r.json()["ic_or_passport"]
    assert re.fullmatch(r"900520-0[1-9]-\d{4}", ic)


def test_register_generates_unique_ic_for_same_date_of_birth(client: TestClient) -> None:
    """Two patients sharing a date_of_birth must still get distinct IC numbers."""
    r1 = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", date_of_birth="1990-05-20"),
    )
    r2 = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="John Lee", date_of_birth="1990-05-20"),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["ic_or_passport"] != r2.json()["ic_or_passport"]


def _login_as_receptionist(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="receptionist@example.com", role="receptionist"
    )
    client.post(
        "/api/auth/login", json={"email": "receptionist@example.com", "password": temp_password}
    )


def test_register_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/register", follow_redirects=False)
    assert r.status_code == 303


def test_register_page_loads_when_logged_in_as_receptionist(client: TestClient) -> None:
    _login_as_receptionist(client)
    r = client.get("/patients/register")
    assert r.status_code == 200


def test_register_page_renders(client: TestClient) -> None:
    """The HTML registration form page loads successfully."""
    _login_as_receptionist(client)

    r = client.get("/patients/register")
    assert r.status_code == 200
    assert "Register New Patient" in r.text


# --- 3. Search / list tests ---------------------------------------------------


def _register_sample_patients(client: TestClient) -> list[str]:
    ids = []
    for name in ("Jane Tan", "John Lee", "Ah Kow", "Janet Wong"):
        r = client.post("/api/patients", json=valid_patient_payload(full_name=name))
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


# --- 4. Update patient tests ---------------------------------------------------


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


# --- 5. BDD-style tests with pytest-bdd --------------------------------------
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
