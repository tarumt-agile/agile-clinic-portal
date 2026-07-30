from __future__ import annotations

import re
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox
from agile_ci_demo.patients import models as _patients_models  # noqa: F401
from agile_ci_demo.pharmacy.service import seed_default_medications
from agile_ci_demo.prescriptions import models as _prescription_models  # noqa: F401
from agile_ci_demo.consultations import models as _consultation_models  # noqa: F401
from agile_ci_demo.staff import models as _staff_models  # noqa: F401


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a fresh in-memory database for every test."""

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
        seed_default_medications(db)

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
        clear_outbox()


@dataclass(frozen=True)
class PreparedConsultation:
    patient_id: str
    doctor_id: str
    doctor_email: str
    doctor_password: str
    record_id: str
    diagnosis_id: int
    medication_id: str


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


def valid_record_payload(
    patient_id: str,
    doctor_id: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "notes": "Patient presented with fever and cough for three days.",
        "diagnoses": [
            {
                "icd10_code": "J00",
                "description": "Acute nasopharyngitis (common cold)",
            }
        ],
    }
    payload.update(overrides)
    return payload


def valid_prescription_payload(
    record_id: str,
    diagnosis_id: int,
    medication_id: str,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "consultation_record_id": record_id,
        "diagnosis_id": diagnosis_id,
        "medication_id": medication_id,
        "dosage": "1 capsule",
        "frequency": "Three times daily",
        "duration": "7 days",
    }
    payload.update(overrides)
    return payload


def valid_instruction_update(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "dosage": "2 capsules",
        "frequency": "Twice daily",
        "duration": "10 days",
        "change_reason": "Instructions corrected after review.",
    }
    payload.update(overrides)
    return payload


def register_patient(client: TestClient, **overrides: object) -> str:
    response = client.post(
        "/api/patients",
        json=valid_patient_payload(**overrides),
    )
    assert response.status_code == 201, response.json()
    return str(response.json()["patient_id"])


def register_doctor(
    client: TestClient,
    **overrides: object,
) -> tuple[str, str, str]:
    payload = valid_doctor_payload(**overrides)
    email = str(payload["email"])

    clear_outbox()
    response = client.post("/api/staff", json=payload)
    assert response.status_code == 201, response.json()

    welcome_email = next(
        message
        for message in reversed(get_outbox())
        if message.to == email
    )
    match = re.search(r"temporary password is: (\S+)", welcome_email.body)
    assert match is not None

    return str(response.json()["staff_id"]), email, match.group(1)


def login_doctor(
    client: TestClient,
    email: str,
    password: str,
) -> None:
    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 200, response.json()


def create_consultation(
    client: TestClient,
    patient_id: str,
    doctor_id: str,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/consultations",
        json=valid_record_payload(
            patient_id,
            doctor_id,
            **overrides,
        ),
    )
    assert response.status_code == 201, response.json()
    return response.json()


def find_medication_id(
    client: TestClient,
    keyword: str,
    standard_dosage: str,
) -> str:
    response = client.get(
        "/api/prescriptions/medications",
        params={"q": keyword},
    )
    assert response.status_code == 200, response.json()

    item = next(
        medication
        for medication in response.json()
        if medication["standard_dosage"]
        == standard_dosage
    )
    return str(item["medication_id"])


def prepare_consultation(client: TestClient) -> PreparedConsultation:
    patient_id = register_patient(client)
    doctor_id, email, password = register_doctor(client)
    record = create_consultation(client, patient_id, doctor_id)
    diagnoses = record["diagnoses"]
    assert isinstance(diagnoses, list)
    diagnosis_id = int(diagnoses[0]["id"])

    login_doctor(client, email, password)
    medication_id = find_medication_id(
        client,
        "Amoxicillin",
        "500 mg",
    )

    return PreparedConsultation(
        patient_id=patient_id,
        doctor_id=doctor_id,
        doctor_email=email,
        doctor_password=password,
        record_id=str(record["record_id"]),
        diagnosis_id=diagnosis_id,
        medication_id=medication_id,
    )


def create_prescription(
    client: TestClient,
    prepared: PreparedConsultation,
    **overrides: object,
) -> dict[str, object]:
    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(
            prepared.record_id,
            prepared.diagnosis_id,
            prepared.medication_id,
            **overrides,
        ),
    )
    assert response.status_code == 201, response.json()
    return response.json()


# Medication search


def test_medication_search_endpoint_returns_required_fields(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)

    response = client.get(
        "/api/prescriptions/medications",
        params={"q": "ibuprofen"},
    )

    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    assert set(items[0]) == {
        "medication_id",
        "name",
        "form",
        "standard_dosage",
        "prescription_value",
    }
    assert items[0]["name"] == "Ibuprofen"
    assert prepared.doctor_id


def test_medication_search_returns_empty_list_for_no_match(
    client: TestClient,
) -> None:
    prepare_consultation(client)

    response = client.get(
        "/api/prescriptions/medications",
        params={"q": "not-a-real-catalogue-item"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_medication_search_requires_doctor_session(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/prescriptions/medications",
        params={"q": "amoxicillin"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_options_endpoint_remains_backward_compatible(
    client: TestClient,
) -> None:
    response = client.get("/api/prescriptions/options")

    assert response.status_code == 200
    body = response.json()
    assert {"value", "label"} <= set(body["medications"][0])
    assert body["dosages"]
    assert body["frequencies"]
    assert body["durations"]


# Prescription creation and history


def test_doctor_can_create_prescription(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    assert str(prescription["prescription_id"]).startswith("RX")
    assert prescription["consultation_record_id"] == prepared.record_id
    assert prescription["diagnosis_id"] == prepared.diagnosis_id
    assert prescription["patient_id"] == prepared.patient_id
    assert prescription["prescribing_doctor_id"] == prepared.doctor_id
    assert prescription["medication_id"] == prepared.medication_id
    assert prescription["medication_name"] == "Amoxicillin"
    assert prescription["medication_form"] == "Capsule"
    assert prescription["medication_standard_dosage"] == "500 mg"
    assert prescription["medication"] == "Amoxicillin 500 mg Capsule"
    assert prescription["dosage"] == "1 capsule"
    assert prescription["frequency"] == "Three times daily"
    assert prescription["duration"] == "7 days"
    assert prescription["status"] == "active"
    assert prescription["can_edit"] is True


@pytest.mark.parametrize(
    "missing_field",
    [
        "consultation_record_id",
        "diagnosis_id",
        "medication_id",
        "dosage",
        "frequency",
        "duration",
    ],
)
def test_create_prescription_requires_all_fields(
    client: TestClient,
    missing_field: str,
) -> None:
    prepared = prepare_consultation(client)
    payload = valid_prescription_payload(
        prepared.record_id,
        prepared.diagnosis_id,
        prepared.medication_id,
    )
    del payload[missing_field]

    response = client.post("/api/prescriptions", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field_name",
    ["medication_id", "dosage", "frequency", "duration"],
)
def test_create_prescription_rejects_blank_text(
    client: TestClient,
    field_name: str,
) -> None:
    prepared = prepare_consultation(client)
    payload = valid_prescription_payload(
        prepared.record_id,
        prepared.diagnosis_id,
        prepared.medication_id,
    )
    payload[field_name] = "   "

    response = client.post("/api/prescriptions", json=payload)
    assert response.status_code == 422


def test_create_prescription_rejects_diagnosis_from_other_consultation(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    other_patient_id = register_patient(
        client,
        full_name="Mary Lee",
        email="mary.lee@example.com",
        phone_number="013-9876543",
        ic_or_passport="920315-08-5678",
        date_of_birth="1992-03-15",
    )
    other_record = create_consultation(
        client,
        other_patient_id,
        prepared.doctor_id,
    )
    other_diagnosis_id = int(other_record["diagnoses"][0]["id"])

    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(
            prepared.record_id,
            other_diagnosis_id,
            prepared.medication_id,
        ),
    )

    assert response.status_code == 404


def test_patient_history_is_newest_first_and_patient_scoped(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    paracetamol_id = find_medication_id(
        client,
        "Paracetamol",
        "500 mg",
    )
    cetirizine_id = find_medication_id(
        client,
        "Cetirizine",
        "10 mg",
    )
    first = create_prescription(
        client,
        prepared,
        medication_id=paracetamol_id,
    )
    second = create_prescription(
        client,
        prepared,
        medication_id=cetirizine_id,
    )

    response = client.get(
        f"/api/prescriptions/patient/{prepared.patient_id}"
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["prescription_id"] for item in items] == [
        second["prescription_id"],
        first["prescription_id"],
    ]
    assert all(item["patient_id"] == prepared.patient_id for item in items)


def test_prescription_rejects_unknown_medication(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)

    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(
            prepared.record_id,
            prepared.diagnosis_id,
            "M99999",
        ),
    )

    assert response.status_code == 404


def test_unknown_patient_history_returns_404(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    assert prepared.patient_id

    response = client.get("/api/prescriptions/patient/P99999")
    assert response.status_code == 404


# Instruction revision


def test_prescribing_doctor_can_update_instructions(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=valid_instruction_update(),
    )

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["dosage"] == "2 capsules"
    assert body["frequency"] == "Twice daily"
    assert body["duration"] == "10 days"
    assert len(body["history"]) == 1

    revision = body["history"][0]
    assert revision["previous_dosage"] == "1 capsule"
    assert revision["new_dosage"] == "2 capsules"
    assert revision["previous_frequency"] == "Three times daily"
    assert revision["new_frequency"] == "Twice daily"
    assert revision["change_reason"] == "Instructions corrected after review."
    assert revision["changed_by_doctor_name"] == "Dr. Alan Chua"


def test_update_requires_reason_and_all_instruction_fields(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json={"dosage": "2 capsules"},
    )

    assert response.status_code == 422


def test_update_rejects_when_nothing_changed(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=valid_instruction_update(
            dosage="1 capsule",
            frequency="Three times daily",
            duration="7 days",
        ),
    )

    assert response.status_code == 409


def test_non_prescribing_doctor_cannot_update_or_print(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    _, other_email, other_password = register_doctor(
        client,
        full_name="Dr. Betty Lim",
        email="betty.lim@example.com",
        license_number="MMC-67890",
    )
    login_doctor(client, other_email, other_password)

    update_response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=valid_instruction_update(),
    )
    print_response = client.get(
        f"/prescriptions/{prescription['prescription_id']}"
    )

    assert update_response.status_code == 403
    assert print_response.status_code == 403


def test_other_doctor_cannot_edit_patient_history_item(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    create_prescription(client, prepared)

    _, other_email, other_password = register_doctor(
        client,
        full_name="Dr. Betty Lim",
        email="betty.lim@example.com",
        license_number="MMC-67890",
    )
    login_doctor(client, other_email, other_password)

    response = client.get(
        f"/api/prescriptions/patient/{prepared.patient_id}"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["can_edit"] is False


# Printable prescription


def test_prescription_detail_api_contains_print_fields(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    response = client.get(
        f"/api/prescriptions/{prescription['prescription_id']}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["patient_name"] == "Jane Tan"
    assert body["medication"] == "Amoxicillin 500 mg Capsule"
    assert body["dosage"] == "1 capsule"
    assert body["frequency"] == "Three times daily"
    assert body["duration"] == "7 days"
    assert body["prescribing_doctor_name"] == "Dr. Alan Chua"


def test_prescribing_doctor_can_open_print_page(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    prescription = create_prescription(client, prepared)

    response = client.get(
        f"/prescriptions/{prescription['prescription_id']}"
    )

    assert response.status_code == 200
    assert 'id="print-prescription-button"' in response.text
    assert 'id="prescription-sheet"' in response.text
    assert 'id="print-patient-name"' in response.text
    assert 'id="print-medication"' in response.text
    assert 'id="print-dosage"' in response.text
    assert 'id="print-frequency"' in response.text
    assert 'id="print-duration"' in response.text
    assert 'id="print-doctor-name"' in response.text
    assert settings.clinic_name in response.text
    assert "Telephone:" in response.text
    assert "/static/css/prescription-print.css" in response.text
    assert "/static/js/prescription-print.js" in response.text


def test_print_page_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/prescriptions/RX00001",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/auth/login"


def test_unknown_prescription_print_page_returns_404(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)
    assert prepared.doctor_id

    response = client.get("/prescriptions/RX99999")
    assert response.status_code == 404


def test_consultation_page_has_medication_autocomplete(
    client: TestClient,
) -> None:
    prepared = prepare_consultation(client)

    response = client.get(f"/consultations/{prepared.record_id}")

    assert response.status_code == 200
    assert 'type="search"' in response.text
    assert 'id="prescription-medication"' in response.text
    assert 'id="prescription-medication-suggestions"' in response.text


def test_autocomplete_script_caches_search_results_client_side() -> None:
    script_path = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "js"
        / "consultation-detail.js"
    )
    script = script_path.read_text(encoding="utf-8")

    assert "medicationSearchCache = new Map()" in script
    assert "medicationSearchCache.has(cacheKey)" in script
    assert "medicationSearchCache.set(" in script
    assert '"/api/prescriptions/medications?"' in script
    assert "medicationIdInput.value" in script
    assert "medication_id:" in script


def test_existing_prescription_cards_link_to_print_page() -> None:
    project_root = Path(__file__).resolve().parents[1]
    record_script = (
        project_root / "static" / "js" / "consultation-detail.js"
    ).read_text(encoding="utf-8")
    history_script = (
        project_root / "static" / "js" / "patient-prescription-history.js"
    ).read_text(encoding="utf-8")

    assert "View / Print" in record_script
    assert "View / Print" in history_script
    assert 'href="/prescriptions/${' in record_script
    assert 'href="/prescriptions/${' in history_script


def test_print_styles_define_print_media_and_a4_page() -> None:
    stylesheet_path = (
        Path(__file__).resolve().parents[1]
        / "static"
        / "css"
        / "prescription-print.css"
    )
    stylesheet = stylesheet_path.read_text(encoding="utf-8")

    assert "@media print" in stylesheet
    assert "size: A4" in stylesheet
    assert ".print-actions" in stylesheet
