from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.patients import models as _patients_models  # noqa: F401
from agile_ci_demo.prescription import models as _prescription_models  # noqa: F401
from agile_ci_demo.records import models as _records_models  # noqa: F401
from agile_ci_demo.staff import models as _staff_models  # noqa: F401
from agile_ci_demo.staff.service import get_staff_by_staff_id


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

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
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
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "consultation_record_id": record_id,
        "diagnosis_id": diagnosis_id,
        "medication": "Amoxicillin 500 mg Capsule",
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


def register_doctor(client: TestClient, **overrides: object) -> str:
    response = client.post(
        "/api/staff",
        json=valid_doctor_payload(**overrides),
    )
    assert response.status_code == 201, response.json()
    return str(response.json()["staff_id"])


def create_consultation(
    client: TestClient,
    patient_id: str,
    doctor_id: str,
    **overrides: object,
) -> str:
    response = client.post(
        "/api/records",
        json=valid_record_payload(patient_id, doctor_id, **overrides),
    )
    assert response.status_code == 201, response.json()
    return str(response.json()["record_id"])


def get_diagnosis_ids(client: TestClient, record_id: str) -> list[int]:
    response = client.get(f"/api/records/{record_id}")
    assert response.status_code == 200, response.json()
    return [int(item["id"]) for item in response.json()["diagnoses"]]


def prepare_consultation(client: TestClient) -> tuple[str, str, str, int]:
    patient_id = register_patient(client)
    doctor_id = register_doctor(client)
    record_id = create_consultation(client, patient_id, doctor_id)
    diagnosis_id = get_diagnosis_ids(client, record_id)[0]
    return patient_id, doctor_id, record_id, diagnosis_id


def create_prescription(
    client: TestClient,
    record_id: str,
    diagnosis_id: int | None = None,
    **overrides: object,
) -> dict[str, object]:
    if diagnosis_id is None:
        diagnosis_id = get_diagnosis_ids(client, record_id)[0]

    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(
            record_id,
            diagnosis_id,
            **overrides,
        ),
    )
    assert response.status_code == 201, response.json()
    return response.json()


# STORY 1: CREATE PRESCRIPTION


def test_create_prescription_success(client: TestClient) -> None:
    patient_id, doctor_id, record_id, diagnosis_id = prepare_consultation(client)

    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(record_id, diagnosis_id),
    )

    assert response.status_code == 201, response.json()
    body = response.json()

    assert body["prescription_id"].startswith("RX")
    assert body["consultation_record_id"] == record_id
    assert body["diagnosis_id"] == diagnosis_id
    assert body["diagnosis_code"] == "J00"
    assert body["diagnosis_description"] == "Acute nasopharyngitis (common cold)"
    assert body["patient_id"] == patient_id
    assert body["prescribing_doctor_id"] == doctor_id
    assert body["medication"] == "Amoxicillin 500 mg Capsule"
    assert body["dosage"] == "1 capsule"
    assert body["frequency"] == "Three times daily"
    assert body["duration"] == "7 days"
    assert body["status"] == "active"
    assert body["can_edit"] is True


@pytest.mark.parametrize(
    "missing_field",
    [
        "consultation_record_id",
        "diagnosis_id",
        "medication",
        "dosage",
        "frequency",
        "duration",
    ],
)
def test_create_prescription_requires_all_fields(
    client: TestClient,
    missing_field: str,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    payload = valid_prescription_payload(record_id, diagnosis_id)
    del payload[missing_field]

    response = client.post("/api/prescriptions", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "field_name",
    ["medication", "dosage", "frequency", "duration"],
)
def test_create_prescription_rejects_blank_fields(
    client: TestClient,
    field_name: str,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    payload = valid_prescription_payload(record_id, diagnosis_id)
    payload[field_name] = "   "

    response = client.post("/api/prescriptions", json=payload)
    assert response.status_code == 422


def test_prescription_links_to_consultation_and_diagnosis(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    created = create_prescription(client, record_id, diagnosis_id)

    response = client.get(
        f"/api/prescriptions/consultation/{record_id}"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["prescription_id"] == created["prescription_id"]
    assert body["items"][0]["consultation_record_id"] == record_id
    assert body["items"][0]["diagnosis_id"] == diagnosis_id


def test_multiple_prescriptions_can_link_to_one_diagnosis(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)

    create_prescription(client, record_id, diagnosis_id)
    create_prescription(
        client,
        record_id,
        diagnosis_id,
        medication="Paracetamol 500 mg Tablet",
        dosage="2 tablets",
        frequency="Every 6 hours",
        duration="3 days",
    )

    response = client.get(
        f"/api/prescriptions/consultation/{record_id}"
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert all(item["diagnosis_id"] == diagnosis_id for item in items)


def test_prescriptions_can_link_to_different_diagnoses(
    client: TestClient,
) -> None:
    patient_id = register_patient(client)
    doctor_id = register_doctor(client)
    record_id = create_consultation(
        client,
        patient_id,
        doctor_id,
        diagnoses=[
            {
                "icd10_code": "J00",
                "description": "Acute nasopharyngitis (common cold)",
            },
            {
                "icd10_code": "R50.9",
                "description": "Fever, unspecified",
            },
        ],
    )
    diagnosis_ids = get_diagnosis_ids(client, record_id)

    create_prescription(client, record_id, diagnosis_ids[0])
    create_prescription(
        client,
        record_id,
        diagnosis_ids[1],
        medication="Paracetamol 500 mg Tablet",
    )

    response = client.get(
        f"/api/prescriptions/consultation/{record_id}"
    )
    assert response.status_code == 200
    assert {item["diagnosis_id"] for item in response.json()["items"]} == set(
        diagnosis_ids
    )


def test_create_prescription_for_unknown_record_returns_404(
    client: TestClient,
) -> None:
    register_doctor(client)
    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload("R99999", diagnosis_id=1),
    )
    assert response.status_code == 404


def test_create_prescription_rejects_diagnosis_from_other_consultation(
    client: TestClient,
) -> None:
    patient_id = register_patient(client)
    doctor_id = register_doctor(client)
    first_record = create_consultation(client, patient_id, doctor_id)
    second_record = create_consultation(client, patient_id, doctor_id)
    other_diagnosis_id = get_diagnosis_ids(client, second_record)[0]

    response = client.post(
        "/api/prescriptions",
        json=valid_prescription_payload(first_record, other_diagnosis_id),
    )
    assert response.status_code == 404


def test_prescription_options_endpoint_returns_choices(
    client: TestClient,
) -> None:
    response = client.get("/api/prescriptions/options")
    assert response.status_code == 200
    body = response.json()
    assert body["medications"]
    assert body["dosages"]
    assert body["frequencies"]
    assert body["durations"]
    assert {"value", "label"}.issubset(body["medications"][0])


# STORY 2: VIEW PRESCRIPTION HISTORY


def test_patient_prescription_history_displays_details(
    client: TestClient,
) -> None:
    patient_id, _, record_id, diagnosis_id = prepare_consultation(client)
    create_prescription(client, record_id, diagnosis_id)

    response = client.get(f"/api/prescriptions/patient/{patient_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1

    prescription = body["items"][0]
    assert prescription["diagnosis_code"] == "J00"
    assert prescription["diagnosis_description"] == "Acute nasopharyngitis (common cold)"
    assert prescription["medication"] == "Amoxicillin 500 mg Capsule"
    assert prescription["dosage"] == "1 capsule"
    assert prescription["frequency"] == "Three times daily"
    assert prescription["duration"] == "7 days"
    assert prescription["status"] == "active"
    assert prescription["issued_at"] is not None
    assert prescription["updated_at"] is not None


def test_patient_prescription_history_is_sorted_newest_first(
    client: TestClient,
) -> None:
    patient_id, _, record_id, diagnosis_id = prepare_consultation(client)

    first = create_prescription(
        client,
        record_id,
        diagnosis_id,
        medication="Paracetamol 500 mg Tablet",
    )
    second = create_prescription(
        client,
        record_id,
        diagnosis_id,
        medication="Cetirizine 10 mg Tablet",
    )

    response = client.get(f"/api/prescriptions/patient/{patient_id}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["prescription_id"] for item in items] == [
        second["prescription_id"],
        first["prescription_id"],
    ]


def test_patient_history_excludes_other_patients(client: TestClient) -> None:
    patient_a = register_patient(client)
    patient_b = register_patient(
        client,
        full_name="Mary Lee",
        email="mary.lee@example.com",
        phone_number="013-9876543",
        ic_or_passport="920315-08-5678",
    )
    doctor_id = register_doctor(client)
    record_a = create_consultation(client, patient_a, doctor_id)
    record_b = create_consultation(client, patient_b, doctor_id)

    create_prescription(client, record_a)
    create_prescription(
        client,
        record_b,
        medication="Cetirizine 10 mg Tablet",
    )

    response = client.get(f"/api/prescriptions/patient/{patient_a}")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["patient_id"] == patient_a
    assert items[0]["medication"] == "Amoxicillin 500 mg Capsule"


def test_unknown_patient_prescription_history_returns_404(
    client: TestClient,
) -> None:
    response = client.get("/api/prescriptions/patient/P99999")
    assert response.status_code == 404


# STORY 3: UPDATE PRESCRIPTION INSTRUCTIONS


def test_prescribing_doctor_can_update_instructions(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)

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
    assert revision["previous_duration"] == "7 days"
    assert revision["new_duration"] == "10 days"
    assert revision["change_reason"] == "Instructions corrected after review."


def test_update_instructions_requires_change_reason(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)
    payload = valid_instruction_update()
    del payload["change_reason"]

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=payload,
    )
    assert response.status_code == 422


def test_update_instructions_rejects_blank_reason(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=valid_instruction_update(change_reason="   "),
    )
    assert response.status_code == 422


def test_update_instructions_rejects_no_change(client: TestClient) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json={
            "dosage": "1 capsule",
            "frequency": "Three times daily",
            "duration": "7 days",
            "change_reason": "Attempted correction.",
        },
    )
    assert response.status_code == 409


def test_unknown_prescription_update_returns_404(client: TestClient) -> None:
    register_doctor(client)
    response = client.patch(
        "/api/prescriptions/RX99999/instructions",
        json=valid_instruction_update(),
    )
    assert response.status_code == 404


def test_non_prescribing_doctor_cannot_update_instructions(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, prescribing_doctor_id, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)

    other_doctor_id = register_doctor(
        client,
        full_name="Dr. Betty Lim",
        email="betty.lim@example.com",
        license_number="MMC-67890",
    )
    assert other_doctor_id != prescribing_doctor_id

    def use_other_doctor(db: Session):
        return get_staff_by_staff_id(db, other_doctor_id)

    monkeypatch.setattr(
        "agile_ci_demo.prescription.service.get_current_doctor",
        use_other_doctor,
    )
    monkeypatch.setattr(
        "agile_ci_demo.prescription.router.get_current_doctor",
        use_other_doctor,
    )

    response = client.patch(
        f"/api/prescriptions/{prescription['prescription_id']}/instructions",
        json=valid_instruction_update(),
    )
    assert response.status_code == 403


def test_edit_permission_is_false_for_other_doctor(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patient_id, _, record_id, diagnosis_id = prepare_consultation(client)
    create_prescription(client, record_id, diagnosis_id)

    other_doctor_id = register_doctor(
        client,
        full_name="Dr. Betty Lim",
        email="betty.lim@example.com",
        license_number="MMC-67890",
    )

    def use_other_doctor(db: Session):
        return get_staff_by_staff_id(db, other_doctor_id)

    monkeypatch.setattr(
        "agile_ci_demo.prescription.router.get_current_doctor",
        use_other_doctor,
    )

    response = client.get(f"/api/prescriptions/patient/{patient_id}")
    assert response.status_code == 200
    assert response.json()["items"][0]["can_edit"] is False


def test_multiple_instruction_changes_save_all_versions(
    client: TestClient,
) -> None:
    _, _, record_id, diagnosis_id = prepare_consultation(client)
    prescription = create_prescription(client, record_id, diagnosis_id)
    prescription_id = str(prescription["prescription_id"])

    first_update = client.patch(
        f"/api/prescriptions/{prescription_id}/instructions",
        json=valid_instruction_update(),
    )
    assert first_update.status_code == 200, first_update.json()

    second_update = client.patch(
        f"/api/prescriptions/{prescription_id}/instructions",
        json={
            "dosage": "1 capsule",
            "frequency": "At night",
            "duration": "14 days",
            "change_reason": "Adjusted after patient feedback.",
        },
    )
    assert second_update.status_code == 200, second_update.json()

    body = second_update.json()
    assert body["dosage"] == "1 capsule"
    assert body["frequency"] == "At night"
    assert body["duration"] == "14 days"
    assert len(body["history"]) == 2


# FRONTEND PAGE TESTS


def test_consultation_page_contains_prescription_modal(
    client: TestClient,
) -> None:
    _, _, record_id, _ = prepare_consultation(client)
    response = client.get(f"/records/{record_id}")

    assert response.status_code == 200
    assert 'id="diagnosis-list"' in response.text
    assert 'id="add-prescription-modal"' in response.text
    assert 'id="add-prescription-form"' in response.text
    assert 'id="prescription-medication"' in response.text
    assert 'id="prescription-dosage"' in response.text
    assert 'id="prescription-frequency"' in response.text
    assert 'id="prescription-duration"' in response.text


def test_patient_page_contains_prescriptions_tab(client: TestClient) -> None:
    patient_id = register_patient(client)
    response = client.get(f"/patients/{patient_id}")

    assert response.status_code == 200
    assert 'id="prescriptions-tab-btn"' in response.text
    assert 'id="prescriptions-list"' in response.text
    assert 'id="edit-prescription-modal"' in response.text
    assert 'id="edit-prescription-dosage"' in response.text
    assert 'id="edit-prescription-frequency"' in response.text
    assert 'id="edit-prescription-duration"' in response.text
    assert 'id="edit-prescription-reason"' in response.text