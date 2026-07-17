from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox
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
    clear_outbox()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        clear_outbox()


def valid_staff_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Alice Wong",
        "email": "alice.wong@example.com",
        "role": "nurse",
    }
    payload.update(overrides)
    return payload


# --- 1. Create staff account ---------------------------------------------------


def test_create_staff_success(client: TestClient) -> None:
    """
    Scenario: Create a staff account
      Given the create-account form has all required fields filled in
      When I POST /api/staff
      Then I receive 201, a generated staff_id, and the account is active
    """
    r = client.post("/api/staff", json=valid_staff_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["staff_id"] == "S00001"
    assert body["full_name"] == "Alice Wong"
    assert body["role"] == "nurse"
    assert body["is_active"] is True
    assert body["must_change_password"] is True


def test_create_staff_generates_sequential_ids(client: TestClient) -> None:
    people = [
        {
            "full_name": "Alice Wong",
            "email": "alice@example.com",
            "role": "nurse",
        },
        {
            "full_name": "Bob Lee",
            "email": "bob@example.com",
            "role": "doctor",
            "license_number": "MMC-12345",
            "specialty": "Cardiology",
            "status": "active",
        },
        {
            "full_name": "Cara Tan",
            "email": "cara@example.com",
            "role": "admin",
        },
    ]
    ids = []
    for payload in people:
        response = client.post("/api/staff", json=payload)

        assert response.status_code == 201, response.json()
        ids.append(response.json()["staff_id"])

    assert ids == ["S00001", "S00002", "S00003"]

   


@pytest.mark.parametrize("role", ["admin", "doctor", "nurse"])
def test_create_staff_allows_multiple_roles(client: TestClient,role: str) -> None:
    payload = valid_staff_payload(email=f"{role}@example.com",role=role,)

    if role == "doctor":payload.update(
            {"license_number": "MMC-12345","specialty": "General Medicine","status": "active",}
    )
    response = client.post("/api/staff", json=payload)
    assert response.status_code == 201, response.json()
    assert response.json()["role"] == role


def test_create_staff_invalid_role_returns_422(client: TestClient) -> None:
    r = client.post("/api/staff", json=valid_staff_payload(role="superuser"))
    assert r.status_code == 422


# --- 1a. Specialty validation --------------------------------------------------


def test_create_doctor_with_specialty_succeeds(client: TestClient,) -> None:
    response = client.post("/api/staff", json=valid_staff_payload(full_name="Dr. Alice Wong",role="doctor",license_number="MMC-12345",specialty="Cardiology",status="active",),)
    assert response.status_code == 201, response.json()
    assert response.json()["specialty"] == "Cardiology"


def test_create_doctor_without_specialty_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "full_name": "Dr. Alice Wong",
        "email": "alice.doctor@example.com",
        "role": "doctor",
        "license_number": "MMC-12345",
        "status": "active",
    }
    response = client.post("/api/staff", json=payload)
    assert response.status_code == 422

def test_create_doctor_without_license_returns_422(
    client: TestClient,
) -> None:
    payload = {
        "full_name": "Dr. Alice Wong",
        "email": "alice.doctor@example.com",
        "role": "doctor",
        "specialty": "Cardiology",
        "status": "active",
    }

    response = client.post("/api/staff", json=payload)

    assert response.status_code == 422

def test_create_non_doctor_with_specialty_returns_422(client: TestClient) -> None:
    """A specialty only makes sense for doctors - rejecting it elsewhere prevents
    nonsensical data like a nurse with a "cardiology" specialty."""
    r = client.post(
        "/api/staff",
        json=valid_staff_payload(role="nurse", specialty="cardiology"),
    )
    assert r.status_code == 422


def test_create_staff_invalid_specialty_returns_422(client: TestClient) -> None:
    r = client.post(
        "/api/staff",
        json=valid_staff_payload(role="doctor", specialty="not-a-real-specialty"),
    )
    assert r.status_code == 422


def test_create_non_doctor_without_specialty_omits_it(client: TestClient) -> None:
    r = client.post("/api/staff", json=valid_staff_payload(role="nurse"))
    assert r.status_code == 201
    assert r.json()["specialty"] is None


@pytest.mark.parametrize("missing_field", ["full_name", "email", "role"])
def test_create_staff_missing_required_field_returns_422(
    client: TestClient, missing_field: str
) -> None:
    payload = valid_staff_payload()
    del payload[missing_field]

    r = client.post("/api/staff", json=payload)
    assert r.status_code == 422
    locs = [err["loc"][-1] for err in r.json()["detail"]]
    assert missing_field in locs


def test_create_staff_blank_full_name_returns_422(client: TestClient) -> None:
    r = client.post("/api/staff", json=valid_staff_payload(full_name="  "))
    assert r.status_code == 422


def test_create_staff_invalid_email_returns_422(client: TestClient) -> None:
    r = client.post("/api/staff", json=valid_staff_payload(email="not-an-email"))
    assert r.status_code == 422


def test_create_staff_duplicate_email_returns_409(client: TestClient) -> None:
    """
    Scenario: Reject duplicate email registration
      Given a staff account with a given email is already registered
      When I POST another staff account with the same email
      Then I receive 409 Conflict
    """
    payload = valid_staff_payload()
    r1 = client.post("/api/staff", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/staff", json=valid_staff_payload(full_name="Different Name"))
    assert r2.status_code == 409


def test_create_staff_sends_welcome_email_with_temp_password(client: TestClient) -> None:
    """
    Scenario: Welcome email with temp password
      When a staff account is created
      Then a welcome email is sent to the new staff member containing a temporary password
    """
    r = client.post("/api/staff", json=valid_staff_payload())
    assert r.status_code == 201

    outbox = get_outbox()
    assert len(outbox) == 1
    assert outbox[0].to == "alice.wong@example.com"
    assert "temporary password" in outbox[0].body.lower()


def test_create_staff_page_renders(client: TestClient) -> None:
    r = client.get("/staff/create")
    assert r.status_code == 200
    assert "Create Staff Account" in r.text


def test_staff_list_page_renders(client: TestClient) -> None:
    r = client.get("/staff")
    assert r.status_code == 200
    assert "Staff" in r.text


def test_list_staff_returns_created_accounts(client: TestClient) -> None:
    client.post("/api/staff", json=valid_staff_payload())
    client.post(
        "/api/staff", json=valid_staff_payload(full_name="Bob Lee", email="bob@example.com")
    )

    r = client.get("/api/staff")
    assert r.status_code == 200
    assert len(r.json()) == 2


# --- 2. Deactivate staff account -------------------------------------------------


def test_deactivate_staff_success(client: TestClient) -> None:
    """
    Scenario: Deactivate a staff account
      Given a staff account exists and is active
      When I PATCH /api/staff/{staff_id}/status with is_active=false
      Then the account is marked inactive
    """
    created = client.post("/api/staff", json=valid_staff_payload()).json()

    r = client.patch(f"/api/staff/{created['staff_id']}/status", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_reactivate_staff_success(client: TestClient) -> None:
    """The status toggle also supports reactivating a previously deactivated account."""
    created = client.post("/api/staff", json=valid_staff_payload()).json()
    client.patch(f"/api/staff/{created['staff_id']}/status", json={"is_active": False})

    r = client.patch(f"/api/staff/{created['staff_id']}/status", json={"is_active": True})
    assert r.status_code == 200
    assert r.json()["is_active"] is True


def test_deactivate_unknown_staff_returns_404(client: TestClient) -> None:
    r = client.patch("/api/staff/S99999/status", json={"is_active": False})
    assert r.status_code == 404
