# Sprint 2 Auth Stories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close out four Sprint 2 stories (receptionist login, doctor login, logout, password reset) per [2026-07-27-sprint2-auth-stories-design.md](../specs/2026-07-27-sprint2-auth-stories-design.md).

**Architecture:** Staff login/logout already work via cookie sessions (`starlette.SessionMiddleware`); this plan adds a server-computed `redirect_url` (tested in Python, replacing an untested client-side map), a literal `DELETE /auth/session` endpoint + `localStorage` token alongside the existing cookie logout, and a brand-new staff-only password reset flow backed by a single-use, time-limited DB token.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Jinja2, Bootstrap 5 (vanilla JS, no framework), pytest + `TestClient`.

## Global Constraints

- Password reset is staff-only. Patients have no password field and are out of scope.
- Receptionist's post-login landing page stays `/patients` (no new dashboard page).
- Reset tokens expire 30 minutes after creation and are single-use.
- `DELETE /api/auth/session` is added **alongside** the existing `POST /api/auth/logout` — the existing endpoint is not removed or changed (it's still exercised by `test_logout_clears_the_session`).
- `session_token` returned at login is not validated server-side; the cookie session remains the real auth mechanism. It exists solely so the frontend has a token to store/clear.
- New password must be at least 8 characters and match its confirmation field.
- All new UI (templates + JS) must visually match the existing Bootstrap 5 structure/classes used in `templates/auth/login.html` and `static/js/auth-login.js`.
- Run tests with the project's venv interpreter, not a bare `python`/`pytest` on PATH: `.venv/Scripts/python.exe -m pytest ...` (the global Python install on this machine lacks the project's dependencies).

---

### Task 1: Login response gains `redirect_url` and `session_token`

**Files:**
- Modify: `src/agile_ci_demo/auth/schemas.py`
- Modify: `src/agile_ci_demo/auth/service.py`
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `src/agile_ci_demo/core/security.py`
- Test: `tests/test_auth_redirect.py` (create)

**Interfaces:**
- Produces: `auth.service.redirect_url_for_role(role: Role) -> str`
- Produces: `core.security.generate_session_token() -> str`
- Produces: `LoginResponse` fields `redirect_url: str`, `session_token: str` (in addition to existing `staff_id`, `full_name`, `role`, `must_change_password`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_redirect.py`:

```python
from __future__ import annotations

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
    r = client.post("/api/staff", json=payload)
    assert r.status_code == 201

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
        ("admin", "/staff"),
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth_redirect.py -v`
Expected: FAIL with `KeyError: 'redirect_url'` (the field doesn't exist on the response yet).

- [ ] **Step 3: Add `generate_session_token` to `core/security.py`**

Add to `src/agile_ci_demo/core/security.py`, after `generate_temp_password`:

```python
def generate_session_token() -> str:
    """Generate a random opaque token for the frontend to hold in localStorage.

    Not validated server-side - the cookie session is the real auth mechanism.
    This exists only so logout has a token to clear, per the story's literal ask.
    """
    return secrets.token_urlsafe(32)
```

- [ ] **Step 4: Add `redirect_url_for_role` to `auth/service.py`**

Add to `src/agile_ci_demo/auth/service.py`, after the imports (add `from agile_ci_demo.core.rbac import Role` to the existing import block) and before `class InvalidCredentialsError`:

```python
_REDIRECT_BY_ROLE: dict[Role, str] = {
    Role.ADMIN: "/staff",
    Role.DOCTOR: "/appointments/schedule",
    Role.NURSE: "/patients",
    Role.RECEPTIONIST: "/patients",
}


def redirect_url_for_role(role: Role) -> str:
    """Return the landing page a staff member is sent to right after login."""
    return _REDIRECT_BY_ROLE[role]
```

- [ ] **Step 5: Add the new fields to `LoginResponse` in `auth/schemas.py`**

Modify `src/agile_ci_demo/auth/schemas.py` — change the `LoginResponse` class to:

```python
class LoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    full_name: str
    role: Role
    must_change_password: bool
    redirect_url: str
    session_token: str
```

- [ ] **Step 6: Build the response explicitly in the router (not via `model_validate`)**

`redirect_url` and `session_token` aren't attributes on the `Staff` ORM object, so `LoginResponse.model_validate(staff)` can no longer construct the full response. Modify `src/agile_ci_demo/auth/router.py`:

Add imports (extend the existing `from agile_ci_demo.auth.service import (...)` block with `redirect_url_for_role`, and add two new import lines):

```python
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import generate_session_token
```

Replace the `login` function body:

```python
@api_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        staff = authenticate_staff(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AccountInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    login_staff(request, staff)
    return LoginResponse(
        staff_id=staff.staff_id,
        full_name=staff.full_name,
        role=staff.role,
        must_change_password=staff.must_change_password,
        redirect_url=redirect_url_for_role(Role(staff.role)),
        session_token=generate_session_token(),
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth_redirect.py tests/test_auth.py -v`
Expected: PASS (all tests, including the pre-existing ones in `test_auth.py` — the new response fields are additive and don't break `body["staff_id"]`/`body["must_change_password"]` assertions already there).

- [ ] **Step 8: Commit**

```bash
git add src/agile_ci_demo/auth/schemas.py src/agile_ci_demo/auth/service.py src/agile_ci_demo/auth/router.py src/agile_ci_demo/core/security.py tests/test_auth_redirect.py
git commit -m "Compute login redirect_url server-side and return a session_token"
```

---

### Task 2: Frontend consumes `redirect_url` and stores `session_token`

**Files:**
- Modify: `static/js/auth-login.js`

**Interfaces:**
- Consumes: `LoginResponse.redirect_url: str`, `LoginResponse.session_token: str` (from Task 1)

- [ ] **Step 1: Remove the client-side redirect map and use the server's `redirect_url`**

In `static/js/auth-login.js`:

Delete the `REDIRECT_BY_ROLE` constant (lines 6-11):

```js
  const REDIRECT_BY_ROLE = {
    admin: "/staff",
    doctor: "/appointments/schedule",
    nurse: "/patients",
    receptionist: "/patients",
  };
```

In `handleStaffSubmit`, replace:

```js
      if (response.ok) {
        const body = await response.json();
        window.location.href = REDIRECT_BY_ROLE[body.role] || "/patients";
        return;
      }
```

with:

```js
      if (response.ok) {
        const body = await response.json();
        localStorage.setItem("clinicSessionToken", body.session_token);
        window.location.href = body.redirect_url;
        return;
      }
```

- [ ] **Step 2: Manually verify in the browser**

Start the dev server (`preview_start` with the project's launch config, or reuse the one already running), navigate to `/auth/login`, log in as each role (create one test account per role via `POST /api/staff` first if needed, or use an existing seeded account), and confirm each role lands on the expected page:
- admin → `/staff`
- doctor → `/appointments/schedule`
- nurse → `/patients`
- receptionist → `/patients`

Also open browser dev tools → Application → Local Storage, and confirm `clinicSessionToken` is set after a successful login.

- [ ] **Step 3: Commit**

```bash
git add static/js/auth-login.js
git commit -m "Use server-computed redirect_url and store session_token on login"
```

---

### Task 3: `DELETE /api/auth/session` endpoint

**Files:**
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `tests/test_auth.py`

**Interfaces:**
- Consumes: `auth.deps.logout(request: Request) -> None` (already imported in `router.py`)
- Produces: `DELETE /api/auth/session` — 200, clears the session (same effect as `POST /api/auth/logout`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py`, after `test_logout_clears_the_session`:

```python
def test_delete_session_clears_the_session(client: TestClient) -> None:
    temp_password = _create_staff_and_get_temp_password(client, role="admin")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )

    r = client.delete("/api/auth/session")
    assert r.status_code == 200

    r = client.get("/staff", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py::test_delete_session_clears_the_session -v`
Expected: FAIL with 405 Method Not Allowed (no `DELETE /api/auth/session` route exists yet).

- [ ] **Step 3: Add the endpoint**

In `src/agile_ci_demo/auth/router.py`, add after `logout_endpoint`:

```python
@api_router.delete("/session")
def delete_session(request: Request) -> dict:
    logout(request)
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -v`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add src/agile_ci_demo/auth/router.py tests/test_auth.py
git commit -m "Add DELETE /api/auth/session alongside the existing logout endpoint"
```

---

### Task 4: Nav logout uses `DELETE /auth/session` and clears the token

**Files:**
- Modify: `templates/base.html`

**Interfaces:**
- Consumes: `DELETE /api/auth/session` (from Task 3), `localStorage["clinicSessionToken"]` (from Task 2)

- [ ] **Step 1: Update the logout handler**

In `templates/base.html`, replace the inline script's logout handler:

```html
  <script>
    const logoutLink = document.getElementById("logout-link");
    if (logoutLink) {
      logoutLink.addEventListener("click", async (event) => {
        event.preventDefault();
        await fetch("/api/auth/logout", { method: "POST" });
        window.location.href = "/auth/login";
      });
    }
  </script>
```

with:

```html
  <script>
    const logoutLink = document.getElementById("logout-link");
    if (logoutLink) {
      logoutLink.addEventListener("click", async (event) => {
        event.preventDefault();
        await fetch("/api/auth/session", { method: "DELETE" });
        localStorage.removeItem("clinicSessionToken");
        window.location.href = "/auth/login";
      });
    }
  </script>
```

- [ ] **Step 2: Manually verify in the browser**

Log in as any staff role, confirm `clinicSessionToken` is present in Local Storage (Application tab), click "Logout" in the nav, and confirm: the request goes to `DELETE /api/auth/session` (check the Network tab), `clinicSessionToken` is removed from Local Storage, and the page redirects to `/auth/login`. Then confirm a protected page (e.g. `/staff`) redirects back to login (session is actually cleared).

- [ ] **Step 3: Commit**

```bash
git add templates/base.html
git commit -m "Switch nav logout to DELETE /auth/session and clear the stored token"
```

---

### Task 5: Password reset token model + forgot-password flow

**Files:**
- Create: `src/agile_ci_demo/auth/models.py` (currently empty)
- Modify: `src/agile_ci_demo/core/database.py`
- Modify: `src/agile_ci_demo/auth/schemas.py`
- Modify: `src/agile_ci_demo/auth/service.py`
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `tests/test_auth.py`

**Interfaces:**
- Produces: `PasswordResetToken` model (`staff_id`, `token_hash`, `expires_at`, `used_at`, `created_at`)
- Produces: `auth.service.request_password_reset(db: Session, email: str) -> None`
- Produces: `POST /api/auth/forgot-password` — always 200, body `{"message": str}`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_auth.py`. First, add this import near the top, next to the existing `from agile_ci_demo.staff import models as _staff_models  # noqa: F401` line:

```python
from agile_ci_demo.auth import models as _auth_models  # noqa: F401
```

Then add these tests after `test_delete_session_clears_the_session`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -k forgot_password -v`
Expected: FAIL with 404 Not Found (no `/api/auth/forgot-password` or `/auth/forgot-password` route exists yet).

- [ ] **Step 3: Create `auth/models.py`**

```python
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agile_ci_demo.core.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
```

- [ ] **Step 4: Wire the new model into `init_db()`**

In `src/agile_ci_demo/core/database.py`, inside `init_db()`, add (alphabetically before the `appointments` import):

```python
    from agile_ci_demo.auth import (
        models as _auth_models,  # noqa: F401
    )
```

- [ ] **Step 5: Add request/response schemas**

In `src/agile_ci_demo/auth/schemas.py`, change the `pydantic` import line to:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
```

Add at the end of the file:

```python
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
    confirm_password: str

    @model_validator(mode="after")
    def check_passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
```

- [ ] **Step 6: Add `request_password_reset` to `auth/service.py`**

Add these imports to the top of `src/agile_ci_demo/auth/service.py`:

```python
import datetime as dt
import hashlib
import secrets

from agile_ci_demo.auth.models import PasswordResetToken
from agile_ci_demo.core.email import send_email
```

Add near the bottom of the file (after `authenticate_patient`):

```python
_RESET_TOKEN_TTL = dt.timedelta(minutes=30)


class InvalidResetTokenError(Exception):
    """Raised when a password reset token is unknown, expired, or already used."""


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> None:
    """Email a password reset link if the email matches a staff account.

    Always succeeds silently for an unknown email, so this endpoint can't be used
    to discover which emails have accounts - same reasoning as authenticate_staff
    checking the password before the active-status check.
    """
    staff = db.execute(select(Staff).where(Staff.email == email)).scalar_one_or_none()
    if staff is None:
        return

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        staff_id=staff.id,
        token_hash=_hash_token(raw_token),
        expires_at=dt.datetime.utcnow() + _RESET_TOKEN_TTL,
    )
    db.add(reset_token)
    db.commit()

    send_email(
        to=staff.email,
        subject="Reset your Agile Clinic Portal password",
        body=(
            f"Hi {staff.full_name},\n\n"
            "We received a request to reset your password. This link expires in "
            "30 minutes:\n"
            f"/auth/reset-password?token={raw_token}\n\n"
            "If you didn't request this, you can ignore this email."
        ),
    )
```

- [ ] **Step 7: Add the endpoints**

In `src/agile_ci_demo/auth/router.py`, extend the `auth.schemas` import with `ForgotPasswordRequest, ForgotPasswordResponse` and the `auth.service` import with `request_password_reset`. Add:

```python
@api_router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> ForgotPasswordResponse:
    request_password_reset(db, str(payload.email))
    return ForgotPasswordResponse(message="If that email is registered, we've sent a reset link.")


@pages_router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/forgot_password.html", {})
```

(The `auth/forgot_password.html` template doesn't exist yet — that's Task 7. `test_forgot_password_page_renders` will fail until then; the two `forgot-password` API tests will pass after this step.)

- [ ] **Step 8: Run tests to verify the API tests pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -k forgot_password -v`
Expected: `test_forgot_password_returns_generic_message_for_known_email` and
`test_forgot_password_returns_same_generic_message_for_unknown_email` PASS.
`test_forgot_password_page_renders` still FAILs (template missing) — that's expected, Task 7 fixes it.

- [ ] **Step 9: Commit**

```bash
git add src/agile_ci_demo/auth/models.py src/agile_ci_demo/core/database.py src/agile_ci_demo/auth/schemas.py src/agile_ci_demo/auth/service.py src/agile_ci_demo/auth/router.py tests/test_auth.py
git commit -m "Add password reset token model and forgot-password endpoint"
```

---

### Task 6: Reset-password flow

**Files:**
- Modify: `src/agile_ci_demo/auth/service.py`
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `tests/test_auth.py`

**Interfaces:**
- Consumes: `PasswordResetToken`, `_hash_token`, `_RESET_TOKEN_TTL`, `InvalidResetTokenError` (from Task 5)
- Produces: `auth.service.reset_password(db: Session, token: str, new_password: str) -> None`
- Produces: `POST /api/auth/reset-password` — 200 on success, 400 on invalid/expired/used token, 422 on password validation failure
- Produces: `GET /auth/reset-password` page

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_auth.py`, after the forgot-password tests:

```python
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
```

This uses `dt` (the `datetime` module) - add `import datetime as dt` to the top imports of `tests/test_auth.py` alongside the existing `import itertools` / `import re` lines.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -k reset_password -v`
Expected: FAIL with 404 Not Found (no `/api/auth/reset-password` or `/auth/reset-password` route exists yet).

- [ ] **Step 3: Add `reset_password` to `auth/service.py`**

Add to `src/agile_ci_demo/auth/service.py`, after `request_password_reset`:

```python
def reset_password(db: Session, token: str, new_password: str) -> None:
    """Set a new password for the staff account owning a valid, unused, unexpired token."""
    token_hash = _hash_token(token)
    reset_token = db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    ).scalar_one_or_none()

    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at < dt.datetime.utcnow()
    ):
        raise InvalidResetTokenError("This reset link is invalid or has expired")

    staff = db.get(Staff, reset_token.staff_id)
    assert staff is not None  # the FK guarantees the staff row exists

    staff.password_hash = hash_password(new_password)
    staff.must_change_password = False
    reset_token.used_at = dt.datetime.utcnow()
    db.commit()
```

`service.py` currently only imports `verify_password` from `core.security`. Change that import line to `from agile_ci_demo.core.security import hash_password, verify_password`.

- [ ] **Step 4: Add the endpoints**

In `src/agile_ci_demo/auth/router.py`, extend the `auth.schemas` import with `ResetPasswordRequest` and the `auth.service` import with `InvalidResetTokenError, reset_password`. Add:

```python
@api_router.post("/reset-password")
def reset_password_endpoint(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    try:
        reset_password(db, payload.token, payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"status": "ok"}


@pages_router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/reset_password.html", {})
```

(The `auth/reset_password.html` template doesn't exist yet — that's Task 8. `test_reset_password_page_renders` will fail until then; the other reset-password tests will pass after this step.)

- [ ] **Step 5: Run tests to verify the API tests pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py -k reset_password -v`
Expected: all `test_reset_password_*` tests PASS except `test_reset_password_page_renders` (expected — Task 8 fixes it).

- [ ] **Step 6: Commit**

```bash
git add src/agile_ci_demo/auth/service.py src/agile_ci_demo/auth/router.py tests/test_auth.py
git commit -m "Add reset-password endpoint with single-use, time-limited tokens"
```

---

### Task 7: Forgot-password page (template + JS)

**Files:**
- Create: `templates/auth/forgot_password.html`
- Create: `static/js/auth-forgot-password.js`
- Modify: `templates/auth/login.html`

**Interfaces:**
- Consumes: `POST /api/auth/forgot-password` (from Task 5)

- [ ] **Step 1: Create the template**

`templates/auth/forgot_password.html`:

```html
{% extends "base.html" %}

{% block title %}Forgot Password - Agile Clinic Portal{% endblock %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-md-6">
    <h1 class="h3 mb-4">Forgot Password</h1>

    <div id="form-alert" class="alert alert-danger d-none" role="alert"></div>
    <div id="form-success" class="alert alert-success d-none" role="alert"></div>

    <form id="forgot-password-form" novalidate>
      <div class="mb-3">
        <label for="forgot-email" class="form-label">Email</label>
        <input type="email" class="form-control" id="forgot-email" name="email" required>
        <div class="invalid-feedback">Email is required.</div>
      </div>
      <button type="submit" class="btn btn-primary" id="forgot-submit-btn">Send Reset Link</button>
    </form>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="/static/js/auth-forgot-password.js"></script>
{% endblock %}
```

- [ ] **Step 2: Create the JS**

`static/js/auth-forgot-password.js`:

```js
(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");
  const successBox = document.getElementById("form-success");

  function showAlert(message) {
    successBox.classList.add("d-none");
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function showSuccess(message) {
    alertBox.classList.add("d-none");
    successBox.textContent = message;
    successBox.classList.remove("d-none");
  }

  function detailMessage(body, fallback) {
    return typeof body.detail === "string" ? body.detail : fallback;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("forgot-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email")?.trim() }),
      });

      const body = await response.json().catch(() => ({}));
      if (response.ok) {
        showSuccess(body.message || "If that email is registered, we've sent a reset link.");
        form.reset();
      } else {
        showAlert(detailMessage(body, "Something went wrong. Please try again."));
      }
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const form = document.getElementById("forgot-password-form");
  if (form) form.addEventListener("submit", handleSubmit);
})();
```

- [ ] **Step 3: Link to it from the login page**

In `templates/auth/login.html`, inside the staff tab's form, replace:

```html
          <button type="submit" class="btn btn-primary" id="staff-submit-btn">Log In</button>
        </form>
```

with:

```html
          <button type="submit" class="btn btn-primary" id="staff-submit-btn">Log In</button>
          <a href="/auth/forgot-password" class="ms-2">Forgot password?</a>
        </form>
```

- [ ] **Step 4: Run the page-render test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py::test_forgot_password_page_renders -v`
Expected: PASS.

- [ ] **Step 5: Manually verify in the browser**

Navigate to `/auth/login`, confirm the "Forgot password?" link appears under the staff login form and is styled consistently with the rest of the page. Click it, land on `/auth/forgot-password`, submit a known staff email, confirm the green success alert appears. Submit an unknown email, confirm the exact same success message appears (no way to tell the difference).

- [ ] **Step 6: Commit**

```bash
git add templates/auth/forgot_password.html static/js/auth-forgot-password.js templates/auth/login.html
git commit -m "Add forgot-password page"
```

---

### Task 8: Reset-password page (template + JS)

**Files:**
- Create: `templates/auth/reset_password.html`
- Create: `static/js/auth-reset-password.js`

**Interfaces:**
- Consumes: `POST /api/auth/reset-password` (from Task 6)

- [ ] **Step 1: Create the template**

`templates/auth/reset_password.html`:

```html
{% extends "base.html" %}

{% block title %}Reset Password - Agile Clinic Portal{% endblock %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-md-6">
    <h1 class="h3 mb-4">Reset Password</h1>

    <div id="form-alert" class="alert alert-danger d-none" role="alert"></div>

    <form id="reset-password-form" novalidate>
      <div class="mb-3">
        <label for="reset-new-password" class="form-label">New password</label>
        <input type="password" class="form-control" id="reset-new-password" name="new_password" minlength="8" required>
        <div class="invalid-feedback">Password must be at least 8 characters.</div>
      </div>
      <div class="mb-3">
        <label for="reset-confirm-password" class="form-label">Confirm new password</label>
        <input type="password" class="form-control" id="reset-confirm-password" name="confirm_password" minlength="8" required>
        <div class="invalid-feedback">Please confirm your new password.</div>
      </div>
      <button type="submit" class="btn btn-primary" id="reset-submit-btn">Reset Password</button>
    </form>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="/static/js/auth-reset-password.js"></script>
{% endblock %}
```

- [ ] **Step 2: Create the JS**

`static/js/auth-reset-password.js`:

```js
(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function detailMessage(body, fallback) {
    return typeof body.detail === "string" ? body.detail : fallback;
  }

  function getTokenFromUrl() {
    return new URLSearchParams(window.location.search).get("token") || "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const form = event.target;

    const newPassword = document.getElementById("reset-new-password").value;
    const confirmPassword = document.getElementById("reset-confirm-password").value;

    if (!form.checkValidity() || newPassword !== confirmPassword) {
      form.classList.add("was-validated");
      if (newPassword !== confirmPassword) {
        showAlert("Passwords do not match.");
      }
      return;
    }

    const submitBtn = document.getElementById("reset-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token: getTokenFromUrl(),
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });

      if (response.ok) {
        window.location.href = "/auth/login";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(detailMessage(body, "Something went wrong. Please try again."));
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const form = document.getElementById("reset-password-form");
  if (form) form.addEventListener("submit", handleSubmit);
})();
```

- [ ] **Step 3: Run the page-render test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_auth.py::test_reset_password_page_renders -v`
Expected: PASS.

- [ ] **Step 4: Manually verify in the browser end-to-end**

There's no SMTP configured locally, so the reset email only lands in the in-memory outbox, not a real inbox. Submit the forgot-password form for a known staff account's email in the browser, then in a separate terminal pull the token out of the outbox:

```bash
.venv/Scripts/python.exe -c "
import agile_ci_demo.app  # noqa: F401 - registers models via app import
from agile_ci_demo.core.email import get_outbox
print(get_outbox()[-1].body)
"
```

This only works if the dev server and this script share the same DB (they do - both use `clinic.db` via `DATABASE_URL`/the default), but the outbox is in-memory and per-process, so it will be empty here since the outbox lives inside the running server process, not this script. Instead, open the terminal running the dev server (`preview_logs`, or the terminal it was started in) and add a temporary `print(body)` inside `send_email` in `src/agile_ci_demo/core/email.py` before triggering the forgot-password request, so the email body (with the token) shows up in the server's own log output. Remove the temporary print once you've captured the token. Copy the token from `token=<...>` in the printed body, navigate to `/auth/reset-password?token=<that token>`, submit matching passwords, confirm redirect to `/auth/login`, then log in with the new password and confirm success.

- [ ] **Step 5: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -v`
Expected: PASS (every test in `tests/`, including all pre-existing ones — nothing in this plan changes existing behavior outside what's described above).

- [ ] **Step 6: Commit**

```bash
git add templates/auth/reset_password.html static/js/auth-reset-password.js
git commit -m "Add reset-password page"
```
