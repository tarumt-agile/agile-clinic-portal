from __future__ import annotations

import datetime as dt
import itertools
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
from agile_ci_demo.auth import models as _auth_models  # noqa: F401
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


_next_license_number = itertools.count(10000)


def _create_staff_and_get_temp_password(
    client: TestClient, email: str = "alice.wong@example.com", role: str = "nurse"
) -> str:
    """Create a staff account via the API and pull the temp password out of the welcome email."""
    payload: dict[str, object] = {"full_name": "Alice Wong", "email": email, "role": role}
    if role == "doctor":
        # Each doctor needs a unique license_number (the field is unique in the
        # DB) - a counter keeps every call collision-free even within the same
        # test, e.g. when a test registers two doctors to log in as each in turn.
        payload.update(
            {
                "license_number": f"MMC-{next(_next_license_number)}",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    r = client.post("/api/staff", json=payload)
    assert r.status_code == 201

    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    return match.group(1)


def _login_as_admin(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(
        client, email="admin@example.com", role="admin"
    )
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": temp_password})


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
    _login_as_admin(client)
    client.patch("/api/staff/S00001/status", json={"is_active": False})

    r = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    assert r.status_code == 403


def test_login_allowed_after_reactivation(client: TestClient) -> None:
    """A staff account that was deactivated and then reactivated can log in again."""
    temp_password = _create_staff_and_get_temp_password(client)
    _login_as_admin(client)
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
    _login_as_admin(client)
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


def test_delete_session_clears_the_session(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="admin")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.delete("/api/auth/session")
    assert r.status_code == 200

    r = client.get("/staff", follow_redirects=False)
    assert r.status_code == 303


# --- 4. Patient login ---------------------------------------------------------


def test_patient_login_success(client: TestClient) -> None:
    """
    Scenario: A patient logs in with their IC number and phone number
      Given a patient is registered
      When I POST /api/auth/patient-login with their IC number and phone number
      Then I receive 200 and the patient's details
    """
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "email": "jane.tan@example.com",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )
    assert r.status_code == 200
    assert r.json()["patient_id"] == created["patient_id"]


def test_patient_login_succeeds_with_differently_formatted_phone(client: TestClient) -> None:
    """Registration leaves the phone number freeform while the login page's
    auto-dash always reformats it into a fixed grouping as you type - a login
    with the same digits but different dash placement must still succeed."""
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-345-6789",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": created["ic_or_passport"], "phone_number": "012-3456789"},
    )
    assert r.status_code == 200
    assert r.json()["patient_id"] == created["patient_id"]


def test_patient_login_wrong_ic_returns_401(client: TestClient) -> None:
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": "000000-00-0000", "phone_number": created["phone_number"]},
    )
    assert r.status_code == 401


def test_patient_login_wrong_phone_returns_401(client: TestClient) -> None:
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": created["ic_or_passport"], "phone_number": "000-0000000"},
    )
    assert r.status_code == 401


def test_patient_login_unknown_ic_returns_401(client: TestClient) -> None:
    r = client.post(
        "/api/auth/patient-login",
        json={"ic_or_passport": "000000-00-0000", "phone_number": "012-3456789"},
    )
    assert r.status_code == 401


# --- 5. Logging into a second identity resets the first one ------------------


def test_patient_login_after_staff_login_clears_the_staff_session(client: TestClient) -> None:
    """
    Scenario: A staff member logs in, then logs into a patient account too (without
    logging out first)
      Given a doctor is logged in
      When the same session logs in as a patient too, without logging out
      Then the doctor's own protected page no longer accepts the session
    """
    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "email": "jane.tan@example.com",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()
    client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )

    r = client.get("/appointments/schedule", follow_redirects=False)
    assert r.status_code == 303


def test_staff_login_after_patient_login_clears_the_patient_session(client: TestClient) -> None:
    """
    Scenario: A patient logs in, then a staff member logs in too on the same
    session (without logging out first)
      Given a patient is logged in
      When the same session logs in as staff too, without logging out
      Then the patient's own protected page no longer accepts the session
    """
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "email": "jane.tan@example.com",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()
    client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    r = client.get("/patients/dashboard", follow_redirects=False)
    assert r.status_code == 303


# --- 6. Forgot password ------------------------------------------------------


def test_forgot_password_returns_generic_message_for_known_email(client: TestClient) -> None:
    _create_staff_and_get_temp_password(client)

    r = client.post("/api/auth/forgot-password", json={"email": "alice.wong@example.com"})
    assert r.status_code == 200
    assert "sent a reset link" in r.json()["message"]
    assert len(get_outbox()) == 2  # welcome email + reset email


def test_forgot_password_returns_same_generic_message_for_unknown_email(
    client: TestClient,
) -> None:
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "sent a reset link" in r.json()["message"]
    assert len(get_outbox()) == 0


def test_forgot_password_page_renders(client: TestClient) -> None:
    r = client.get("/auth/forgot-password")
    assert r.status_code == 200


def test_forgot_password_logs_email_send_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A delivery failure must stay invisible to the caller (same generic
    response), but should be logged server-side instead of silently vanishing."""
    from agile_ci_demo.auth import service as auth_service

    _create_staff_and_get_temp_password(client)

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("SMTP quota exceeded")

    monkeypatch.setattr(auth_service, "send_email", _raise)

    with caplog.at_level("ERROR"):
        r = client.post("/api/auth/forgot-password", json={"email": "alice.wong@example.com"})

    assert r.status_code == 200
    assert "sent a reset link" in r.json()["message"]
    assert any("Password reset email failed to send" in record.message for record in caplog.records)


# --- 7. Reset password --------------------------------------------------------


def _request_reset_token(client: TestClient, email: str = "alice.wong@example.com") -> str:
    client.post("/api/auth/forgot-password", json={"email": email})
    body = get_outbox()[-1].body
    match = re.search(r"token=(\S+)", body)
    assert match is not None
    return match.group(1)


def test_reset_password_succeeds_with_a_valid_token(client: TestClient) -> None:
    _create_staff_and_get_temp_password(client)
    token = _request_reset_token(client)

    r = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    assert r.status_code == 200

    r = client.post(
        "/api/auth/login",
        json={"email": "alice.wong@example.com", "password": "new-password-123"},
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False


def test_reset_password_rejects_an_unknown_token(client: TestClient) -> None:
    r = client.post(
        "/api/auth/reset-password",
        json={
            "token": "not-a-real-token",
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    assert r.status_code == 400


def test_reset_password_rejects_an_already_used_token(client: TestClient) -> None:
    _create_staff_and_get_temp_password(client)
    token = _request_reset_token(client)

    client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    r = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "another-password-456",
            "confirm_password": "another-password-456",
        },
    )
    assert r.status_code == 400


def test_reset_password_rejects_an_expired_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from agile_ci_demo.auth import service as auth_service

    _create_staff_and_get_temp_password(client)
    monkeypatch.setattr(auth_service, "_RESET_TOKEN_TTL", dt.timedelta(seconds=-1))
    token = _request_reset_token(client)

    r = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "new-password-123",
            "confirm_password": "new-password-123",
        },
    )
    assert r.status_code == 400


def test_reset_password_rejects_mismatched_passwords(client: TestClient) -> None:
    _create_staff_and_get_temp_password(client)
    token = _request_reset_token(client)

    r = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "new-password-123",
            "confirm_password": "totally-different",
        },
    )
    assert r.status_code == 422


def test_reset_password_page_renders(client: TestClient) -> None:
    r = client.get("/auth/reset-password?token=whatever")
    assert r.status_code == 200


# --- 8. Self-service change password -----------------------------------------


def test_change_password_success(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="nurse")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.post(
        "/api/auth/change-password",
        json={
            "current_password": temp_password,
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123",
        },
    )
    assert r.status_code == 200

    stale = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    assert stale.status_code == 401

    fresh = client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": "NewPassword123"}
    )
    assert fresh.status_code == 200


def test_change_password_wrong_current_password_returns_400(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="nurse")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "wrong-password",
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123",
        },
    )
    assert r.status_code == 400


def test_change_password_mismatched_confirm_returns_422(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="nurse")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.post(
        "/api/auth/change-password",
        json={
            "current_password": temp_password,
            "new_password": "NewPassword123",
            "confirm_password": "SomethingElse123",
        },
    )
    assert r.status_code == 422


def test_change_password_requires_login(client: TestClient) -> None:
    r = client.post(
        "/api/auth/change-password",
        json={
            "current_password": "whatever",
            "new_password": "NewPassword123",
            "confirm_password": "NewPassword123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
