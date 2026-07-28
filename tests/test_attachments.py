from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.attachments import models as _attachments_models  # noqa: F401
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import get_outbox
from agile_ci_demo.patients import models as _patients_models  # noqa: F401
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


# --- Payload / setup helpers -------------------------------------------------


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


def valid_record_payload(patient_id: str, doctor_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "notes": "Patient presented with fever and cough for 3 days.",
        "diagnoses": [{"icd10_code": "J00", "description": "Acute nasopharyngitis (common cold)"}],
    }
    payload.update(overrides)
    return payload


def _login_as_doctor(client: TestClient) -> None:
    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    r = client.post(
        "/api/auth/login",
        json={"email": str(valid_doctor_payload()["email"]), "password": match.group(1)},
    )
    assert r.status_code == 200, r.json()


def prepare_consultation(client: TestClient) -> str:
    """Register a patient, a doctor, log in as that doctor, and create a
    consultation note. Returns the note's record_id."""
    patient_id = client.post("/api/patients", json=valid_patient_payload()).json()["patient_id"]
    doctor_id = client.post("/api/staff", json=valid_doctor_payload()).json()["staff_id"]
    _login_as_doctor(client)

    r = client.post("/api/records", json=valid_record_payload(patient_id, doctor_id))
    assert r.status_code == 201, r.json()
    return str(r.json()["record_id"])


def _pdf_bytes(size: int = 100) -> bytes:
    return b"%PDF-1.4\n" + b"0" * size


# --- Upload --------------------------------------------------------------


def test_upload_attachment_success(client: TestClient) -> None:
    record_id = prepare_consultation(client)

    r = client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("lab_result.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["original_filename"] == "lab_result.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(_pdf_bytes())
    assert body["uploaded_by_name"] == "Dr. Alan Chua"


def test_upload_oversized_file_rejected(client: TestClient) -> None:
    record_id = prepare_consultation(client)

    oversized = b"0" * (5 * 1024 * 1024 + 1)
    r = client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )
    assert r.status_code == 422

    listing = client.get(f"/api/attachments?record_id={record_id}")
    assert listing.json() == []


def test_upload_wrong_type_rejected(client: TestClient) -> None:
    record_id = prepare_consultation(client)

    r = client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    assert r.status_code == 422


def test_upload_unknown_record_id_returns_404(client: TestClient) -> None:
    client.post("/api/staff", json=valid_doctor_payload())
    _login_as_doctor(client)

    r = client.post(
        "/api/attachments",
        data={"consultation_record_id": "R99999"},
        files={"file": ("lab_result.pdf", _pdf_bytes(), "application/pdf")},
    )
    assert r.status_code == 404


def test_upload_requires_login(client: TestClient) -> None:
    r = client.post(
        "/api/attachments",
        data={"consultation_record_id": "R00001"},
        files={"file": ("lab_result.pdf", _pdf_bytes(), "application/pdf")},
        follow_redirects=False,
    )
    assert r.status_code == 303


# --- List / download -------------------------------------------------------


def test_list_attachments_returns_uploaded_file(client: TestClient) -> None:
    record_id = prepare_consultation(client)
    client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("lab_result.pdf", _pdf_bytes(), "application/pdf")},
    )

    r = client.get(f"/api/attachments?record_id={record_id}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["original_filename"] == "lab_result.pdf"


def test_list_unknown_record_returns_404(client: TestClient) -> None:
    client.post("/api/staff", json=valid_doctor_payload())
    _login_as_doctor(client)

    r = client.get("/api/attachments?record_id=R99999")
    assert r.status_code == 404


def test_download_attachment_returns_file_contents(client: TestClient) -> None:
    record_id = prepare_consultation(client)
    uploaded = client.post(
        "/api/attachments",
        data={"consultation_record_id": record_id},
        files={"file": ("lab_result.pdf", _pdf_bytes(), "application/pdf")},
    ).json()

    r = client.get(f"/api/attachments/{uploaded['id']}/download")
    assert r.status_code == 200
    assert r.content == _pdf_bytes()
    assert "lab_result.pdf" in r.headers["content-disposition"]


def test_download_unknown_attachment_returns_404(client: TestClient) -> None:
    client.post("/api/staff", json=valid_doctor_payload())
    _login_as_doctor(client)

    r = client.get("/api/attachments/999/download")
    assert r.status_code == 404
