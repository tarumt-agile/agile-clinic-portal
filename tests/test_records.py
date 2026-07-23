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
from agile_ci_demo.records import models as _records_models  # noqa: F401
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
        "license_number": "MMC-12345",
        "specialty": "General Medicine",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def _register_patient(client: TestClient, **overrides: object) -> str:
    body = client.post("/api/patients", json=valid_patient_payload(**overrides)).json()
    return str(body["patient_id"])


def _register_doctor(client: TestClient, **overrides: object) -> str:
    response = client.post(
        "/api/staff",
        json=valid_staff_payload(**overrides),
    )

    assert response.status_code == 201, response.json()

    body = response.json()
    return str(body["staff_id"])


def valid_record_payload(patient_id: str, doctor_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "notes": "Patient presented with fever and cough for 3 days.",
        "diagnoses": [{"icd10_code": "J00", "description": "Acute nasopharyngitis (common cold)"}],
    }
    payload.update(overrides)
    return payload


# --- 1. Acceptance tests (docstring Given/When/Then) -------------------------


def test_create_consultation_note_success(client: TestClient) -> None:
    """
    Scenario: Document a consultation
      Given a registered patient and an active doctor
      When I POST /api/records with notes and at least one diagnosis
      Then I receive 201 and a generated record number, and the diagnosis is stored
    """
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post("/api/records", json=valid_record_payload(patient_id, doctor_id))
    assert r.status_code == 201
    body = r.json()
    assert body["record_id"].startswith("R")
    assert body["patient_id"] == patient_id
    assert body["patient_name"] == "Jane Tan"
    assert body["doctor_id"] == doctor_id
    assert body["doctor_name"] == "Dr. Alan Chua"
    assert body["notes"] == "Patient presented with fever and cough for 3 days."
    assert body["diagnoses"] == [
        {"id": 1, "icd10_code": "J00", "description": "Acute nasopharyngitis (common cold)"}
    ]


def test_create_consultation_note_then_fetch_by_record_id(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    created = client.post("/api/records", json=valid_record_payload(patient_id, doctor_id)).json()

    r = client.get(f"/api/records/{created['record_id']}")
    assert r.status_code == 200
    assert r.json()["record_id"] == created["record_id"]


def test_get_unknown_record_returns_404(client: TestClient) -> None:
    r = client.get("/api/records/R99999")
    assert r.status_code == 404


def test_new_record_page_renders(client: TestClient) -> None:
    """The HTML consultation note form page loads successfully."""
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    r = client.get("/records/new?patient_id=P00001")
    assert r.status_code == 200
    assert "New Consultation Note" in r.text


def test_record_detail_page_renders(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    r = client.get("/records/R00001")
    assert r.status_code == 200
    assert "Consultation Note" in r.text


def test_new_record_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/records/new?patient_id=P00001", follow_redirects=False)
    assert r.status_code == 303


def test_record_detail_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/records/R00001", follow_redirects=False)
    assert r.status_code == 303


# --- 2. Required field / validation tests -------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    ["patient_id", "doctor_id", "notes", "diagnoses"],
)
def test_create_missing_required_field_returns_422(client: TestClient, missing_field: str) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    payload = valid_record_payload(patient_id, doctor_id)
    del payload[missing_field]

    r = client.post("/api/records", json=payload)
    assert r.status_code == 422


def test_create_with_no_diagnoses_returns_422(client: TestClient) -> None:
    """At least one diagnosis is required before a consultation note can be saved."""
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post("/api/records", json=valid_record_payload(patient_id, doctor_id, diagnoses=[]))
    assert r.status_code == 422


def test_create_with_blank_notes_returns_422(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post("/api/records", json=valid_record_payload(patient_id, doctor_id, notes="   "))
    assert r.status_code == 422


def test_create_unknown_patient_returns_404(client: TestClient) -> None:
    doctor_id = _register_doctor(client)
    r = client.post("/api/records", json=valid_record_payload("P99999", doctor_id))
    assert r.status_code == 404


def test_create_unknown_doctor_returns_404(client: TestClient) -> None:
    patient_id = _register_patient(client)
    r = client.post("/api/records", json=valid_record_payload(patient_id, "S99999"))
    assert r.status_code == 404


def test_create_with_non_doctor_staff_returns_404(client: TestClient) -> None:
    """A staff member who isn't a doctor (e.g. a nurse) cannot document a consultation."""
    patient_id = _register_patient(client)
    nurse_id = _register_doctor(
        client, full_name="Nurse Amy", email="amy@example.com", role="nurse"
    )

    r = client.post("/api/records", json=valid_record_payload(patient_id, nurse_id))
    assert r.status_code == 404


# --- 3. Diagnosis / ICD-10 search tests ----------------------------------------


def test_diagnosis_stores_code_and_description(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    r = client.post(
        "/api/records",
        json=valid_record_payload(
            patient_id,
            doctor_id,
            diagnoses=[
                {"icd10_code": "i10", "description": "Essential (primary) hypertension"},
                {"icd10_code": "e11", "description": "Type 2 diabetes mellitus"},
            ],
        ),
    )
    assert r.status_code == 201
    diagnoses = r.json()["diagnoses"]
    assert len(diagnoses) == 2
    # ICD-10 codes are normalised to uppercase.
    assert diagnoses[0]["icd10_code"] == "I10"
    assert diagnoses[1]["icd10_code"] == "E11"


def test_icd10_search_matches_by_description(client: TestClient) -> None:
    r = client.get("/api/records/icd10?q=hypertension")
    assert r.status_code == 200
    codes = [entry["code"] for entry in r.json()]
    assert "I10" in codes


def test_icd10_search_matches_by_code(client: TestClient) -> None:
    r = client.get("/api/records/icd10?q=j00")
    assert r.status_code == 200
    codes = [entry["code"] for entry in r.json()]
    assert "J00" in codes


def test_icd10_search_with_blank_query_returns_empty(client: TestClient) -> None:
    r = client.get("/api/records/icd10?q=")
    assert r.status_code == 200
    assert r.json() == []


# --- 4. Medical history tests --------------------------------------------------


def test_patient_history_lists_newest_first(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)

    first = client.post(
        "/api/records", json=valid_record_payload(patient_id, doctor_id, notes="First visit")
    ).json()
    second = client.post(
        "/api/records", json=valid_record_payload(patient_id, doctor_id, notes="Second visit")
    ).json()

    r = client.get(f"/api/records?patient_id={patient_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    record_ids = [item["record_id"] for item in body["items"]]
    assert record_ids == [second["record_id"], first["record_id"]]
    assert body["items"][0]["doctor_name"] == "Dr. Alan Chua"


def test_patient_history_unknown_patient_returns_404(client: TestClient) -> None:
    r = client.get("/api/records?patient_id=P99999")
    assert r.status_code == 404


def test_patient_history_search_by_diagnosis_keyword(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    client.post(
        "/api/records",
        json=valid_record_payload(
            patient_id,
            doctor_id,
            notes="Routine check-up",
            diagnoses=[{"icd10_code": "I10", "description": "Essential (primary) hypertension"}],
        ),
    )
    client.post(
        "/api/records",
        json=valid_record_payload(
            patient_id,
            doctor_id,
            notes="Follow-up visit",
            diagnoses=[{"icd10_code": "J00", "description": "Acute nasopharyngitis (common cold)"}],
        ),
    )

    r = client.get(f"/api/records?patient_id={patient_id}&q=hypertension")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["diagnoses"][0]["icd10_code"] == "I10"


def test_patient_history_search_by_notes_keyword(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    client.post(
        "/api/records", json=valid_record_payload(patient_id, doctor_id, notes="Fever and cough")
    )
    client.post(
        "/api/records", json=valid_record_payload(patient_id, doctor_id, notes="Sprained ankle")
    )

    r = client.get(f"/api/records?patient_id={patient_id}&q=ankle")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert "ankle" in body["items"][0]["notes"].lower()


def test_patient_history_search_no_match_returns_empty(client: TestClient) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    client.post("/api/records", json=valid_record_payload(patient_id, doctor_id))

    r = client.get(f"/api/records?patient_id={patient_id}&q=nonexistentkeyword")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_patient_history_scoped_to_correct_patient(client: TestClient) -> None:
    """A patient's medical history only includes their own consultation notes."""
    doctor_id = _register_doctor(client)
    patient_a = _register_patient(client, full_name="Jane Tan", ic_or_passport="900520-10-1234")
    patient_b = _register_patient(client, full_name="John Lee", ic_or_passport="880311-14-5678")

    client.post("/api/records", json=valid_record_payload(patient_a, doctor_id, notes="Visit A"))
    client.post("/api/records", json=valid_record_payload(patient_b, doctor_id, notes="Visit B"))

    r = client.get(f"/api/records?patient_id={patient_a}")
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["notes"] == "Visit A"


# --- 5. BDD-style tests with pytest-bdd --------------------------------------
# Feature file: tests/features/records.feature

scenarios("features/records.feature")


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


@bdd_when("I document a consultation with a diagnosis for that patient and doctor")
def document_consultation_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.post(
        "/api/records", json=valid_record_payload(context.patient_id, context.doctor_id)
    )


@bdd_when("I try to document a consultation with no diagnosis")
def document_consultation_without_diagnosis_step(api_is_running: dict, context: Context) -> None:
    client: TestClient = api_is_running["client"]
    context.last_response = client.post(
        "/api/records",
        json=valid_record_payload(context.patient_id, context.doctor_id, diagnoses=[]),
    )


@bdd_then("the consultation note is saved with a generated record number")
def consultation_note_is_saved_step(context: Context) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == 201
    body = context.last_response.json()
    assert body["record_id"].startswith("R")


@bdd_then(parsers.parse("I receive a {status_code:d} response"))
def i_receive_status_code_step(context: Context, status_code: int) -> None:
    assert context.last_response is not None
    assert context.last_response.status_code == status_code
