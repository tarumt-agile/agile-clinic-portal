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


def _create_staff_and_get_temp_password(
    client: TestClient, email: str = "alice.wong@example.com", role: str = "nurse"
) -> str:
    """Create a staff account via the API and pull the temp password out of the welcome email."""
    payload: dict[str, object] = {"full_name": "Alice Wong", "email": email, "role": role}
    if role == "doctor":
        payload.update(
            {"license_number": "MMC-12345", "specialty": "General Medicine", "status": "active"}
        )
    r = client.post("/api/staff", json=payload)
    assert r.status_code == 201

    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    return match.group(1)


# --- 1. Login tests ---------------------------------------------------------


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/auth/login")
    assert r.status_code == 200


def test_login_success(client: TestClient) -> None:
    """
    Scenario: Log in with a valid temp password
      Given a staff account was just created
      When I POST /api/auth/login with the emailed temp password
      Then I receive 200 and the staff's details
    """
    temp_password = _create_staff_and_get_temp_password(client)

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["staff_id"] == "S00001"
    assert body["must_change_password"] is True


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    _create_staff_and_get_temp_password(client)

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": "wrong-password"}
    )
    assert r.status_code == 401


def test_login_unknown_email_returns_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert r.status_code == 401


# --- 2. Block login for deactivated accounts --------------------------------


def test_login_blocked_for_deactivated_account(client: TestClient) -> None:
    """
    Scenario: Deactivated staff cannot log in
      Given a staff account has been deactivated
      When they attempt to log in with correct credentials
      Then I receive 403 Forbidden
    """
    temp_password = _create_staff_and_get_temp_password(client)
    client.patch("/api/staff/S00001/status", json={"is_active": False})

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    assert r.status_code == 403


def test_login_allowed_after_reactivation(client: TestClient) -> None:
    """A staff account that was deactivated and then reactivated can log in again."""
    temp_password = _create_staff_and_get_temp_password(client)
    client.patch("/api/staff/S00001/status", json={"is_active": False})
    client.patch("/api/staff/S00001/status", json={"is_active": True})

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    assert r.status_code == 200


def test_login_wrong_password_on_deactivated_account_still_returns_401(
    client: TestClient,
) -> None:
    """An incorrect password must report as invalid credentials even for a deactivated
    account, so the deactivated status of an account is never leaked to a guesser."""
    _create_staff_and_get_temp_password(client)
    client.patch("/api/staff/S00001/status", json={"is_active": False})

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": "wrong-password"}
    )
    assert r.status_code == 401


# --- 3. Session login/logout -------------------------------------------------


def test_login_sets_a_session(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client)
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.get("/staff/create")
    assert r.status_code == 200


def test_logout_clears_the_session(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="admin")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    client.post("/api/auth/logout")

    r = client.get("/staff", follow_redirects=False)
    assert r.status_code == 303
