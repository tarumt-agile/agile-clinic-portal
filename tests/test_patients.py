from __future__ import annotations

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
    people = [
        ("Jane Tan", "900520-10-1234"),
        ("John Lee", "880311-14-5678"),
        ("Ah Kow", "950101-08-9012"),
    ]
    for name, ic in people:
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


# --- 2. Required field / validation tests ------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["full_name", "date_of_birth", "gender", "phone_number", "ic_or_passport"],
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


def test_register_duplicate_ic_returns_409(client: TestClient) -> None:
    """
    Scenario: Reject duplicate IC/passport registration
      Given a patient with a given IC/passport is already registered
      When I POST another patient with the same IC/passport
      Then I receive 409 Conflict
    """
    payload = valid_patient_payload()
    r1 = client.post("/api/patients", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/patients", json=valid_patient_payload(full_name="Different Name"))
    assert r2.status_code == 409


def test_register_page_renders(client: TestClient) -> None:
    """The HTML registration form page loads successfully."""
    r = client.get("/patients/register")
    assert r.status_code == 200
    assert "Register New Patient" in r.text


# --- 3. BDD-style tests with pytest-bdd --------------------------------------
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
