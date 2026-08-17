from __future__ import annotations

import itertools
import re
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agile_ci_demo.app import app
from agile_ci_demo.core.database import Base, get_db
from agile_ci_demo.core.email import clear_outbox, get_outbox
from agile_ci_demo.staff import models as _staff_models
from agile_ci_demo.staff.schemas import StaffCreate
from agile_ci_demo.staff.service import create_staff

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


_next_license_number = itertools.count(20000)


def _create_staff_and_login(client: TestClient, email: str, role: str) -> dict:
    """Create a staff account of the given role and log in, returning the login response body."""
    payload: dict[str, object] = {"full_name": "Test Staff", "email": email, "role": role}
    if role == "doctor":
        payload.update(
            {
                "license_number": f"MMC-{next(_next_license_number)}",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    # Staff creation directly through the service layer, bypassing the API
    # (POST /api/staff now requires an admin session) - this is pure test
    # setup, not the thing under test.
    db = next(app.dependency_overrides[get_db]())
    try:
        create_staff(db, StaffCreate(**payload))
    finally:
        db.close()

    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    temp_password = match.group(1)

    r = client.post("/api/auth/login", json={"email": email, "password": temp_password})
    assert r.status_code == 200
    return r.json()


@pytest.mark.parametrize(
    "role,expected_redirect",
    [
        ("admin", "/dashboard"),
        ("doctor", "/appointments/schedule"),
        ("nurse", "/patients"),
        ("receptionist", "/patients"),
    ],
)
def test_login_redirect_url_matches_role(
    client: TestClient, role: str, expected_redirect: str
) -> None:
    body = _create_staff_and_login(client, email=f"{role}@example.com", role=role)
    assert body["redirect_url"] == expected_redirect


def test_login_response_includes_a_session_token(client: TestClient) -> None:
    body = _create_staff_and_login(client, email="admin2@example.com", role="admin")
    assert isinstance(body["session_token"], str)
    assert len(body["session_token"]) > 0


def test_login_page_clears_stale_staff_session_and_renders_login(client: TestClient) -> None:
    """A session left behind after the underlying account is deactivated must be
    cleared and shown the login form, not sent into a redirect loop back to the
    dashboard it no longer has access to."""
    _create_staff_and_login(client, email="doctor@example.com", role="doctor")

    db = next(app.dependency_overrides[get_db]())
    try:
        staff = db.execute(
            select(_staff_models.Staff).where(_staff_models.Staff.email == "doctor@example.com")
        ).scalar_one()
        staff.is_active = False
        db.commit()
    finally:
        db.close()

    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 200
    assert "Log In" in response.text

    r = client.get("/appointments/schedule", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"
