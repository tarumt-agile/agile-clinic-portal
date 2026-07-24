# Real Login Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every placeholder "current user" with identity read from a real login session, for every role, and make every page redirect to login if the wrong (or no) role is signed in.

**Architecture:** A signed cookie session (Starlette `SessionMiddleware`, no new database table) holds `user_type`/`staff_id`/`role` or `user_type`/`patient_id`. Two FastAPI dependencies - `require_role(*roles)` for staff pages, `require_patient` for patient pages - read the session, look up the real row, and raise a shared exception that a single app-wide handler turns into a redirect to `/auth/login`.

**Tech Stack:** FastAPI, Starlette `SessionMiddleware` (needs `itsdangerous`), SQLAlchemy, Jinja2, pytest + `TestClient` (its cookie jar persists a session across requests in the same test, same as a real browser).

## Global Constraints

- Commit messages must be non-technical / plain language (per user preference) - describe what changed and why in everyday terms, not internal symbol names or library flags.
- Do not add `Co-Authored-By` to any commit.
- Keep new code as simple as possible - no new database tables, no new libraries beyond `itsdangerous`.
- Full check suite (`ruff check .`, `black --check .`, `mypy src`, `pytest`) must pass before every commit.
- Design reference: `docs/superpowers/specs/2026-07-23-real-login-sessions-design.md`.

---

## Task 1: Session middleware and settings

**Files:**
- Modify: `pyproject.toml` (add `itsdangerous` to `dependencies`)
- Modify: `src/agile_ci_demo/core/config.py` (add `secret_key`)
- Modify: `src/agile_ci_demo/app.py` (add `SessionMiddleware`)
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `settings.secret_key: str`, used by Task 2's middleware setup.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `"itsdangerous>=2.1"` to the `dependencies` list (alongside `python-dotenv>=1.0`).

- [ ] **Step 2: Install it**

Run: `pip install -e ".[dev]"`
Expected: `itsdangerous` installs with no errors.

- [ ] **Step 3: Write the failing test**

In `tests/test_app.py`, add. This builds its own tiny standalone app rather than adding routes to
the shared `app` object, so it can't leak test-only routes into the real app that every other test
file also imports:

```python
def test_session_cookie_round_trips() -> None:
    """A FastAPI app with SessionMiddleware can set and read back a signed session value."""
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient as FastAPITestClient
    from starlette.middleware.sessions import SessionMiddleware

    probe_app = FastAPI()
    probe_app.add_middleware(SessionMiddleware, secret_key="test-secret")

    @probe_app.get("/write")
    def _write(request: Request) -> dict:
        request.session["probe"] = "hello"
        return {"ok": True}

    @probe_app.get("/read")
    def _read(request: Request) -> dict:
        return {"probe": request.session.get("probe")}

    probe_client = FastAPITestClient(probe_app)
    probe_client.get("/write")
    r = probe_client.get("/read")
    assert r.json() == {"probe": "hello"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_app.py::test_session_cookie_round_trips -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'itsdangerous'` or `AssertionError: SessionMiddleware requires itsdangerous` - the package isn't installed yet.

- [ ] **Step 5: Add the setting**

In `src/agile_ci_demo/core/config.py`, add inside `class Settings`:

```python
    # Signs the login session cookie. Falls back to a fixed dev value so local
    # runs and tests work with no .env entry - set a real SECRET_KEY in
    # production.
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
```

- [ ] **Step 6: Add the middleware**

In `src/agile_ci_demo/app.py`, add the import near the other `fastapi`/`starlette` imports:

```python
from starlette.middleware.sessions import SessionMiddleware
```

Immediately after `app = FastAPI(...)` (before the static files mount), add:

```python
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/test_app.py::test_session_cookie_round_trips -v`
Expected: PASS

- [ ] **Step 8: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass (existing xfail prescription tests still show as expected failures, nothing else changes)

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml src/agile_ci_demo/core/config.py src/agile_ci_demo/app.py tests/test_app.py
git commit -m "Add login session support to the app"
```

---

## Task 2: Staff login writes a session, logout clears it, first protected page

**Files:**
- Create: `src/agile_ci_demo/auth/deps.py`
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `src/agile_ci_demo/app.py` (register exception handler)
- Modify: `src/agile_ci_demo/staff/router.py` (protect the staff list page as the first proof point)
- Test: `tests/test_auth.py`, `tests/test_staff.py`

**Interfaces:**
- Consumes: `settings.secret_key` (Task 1), `authenticate_staff(db, email, password) -> Staff` (existing), `get_staff_by_staff_id(db, staff_id) -> Staff | None` (existing).
- Produces: `NotAuthenticatedError` exception, `login_staff(request, staff) -> None`, `logout(request) -> None`, `require_role(*roles: Role)` dependency factory returning `Staff` - all from `agile_ci_demo.auth.deps`, used by every later task that protects a page.

- [ ] **Step 1: Write the failing tests**

In `tests/test_staff.py`, add (needs `from fastapi.testclient import TestClient` already imported at top of file):

```python
def test_staff_list_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/staff", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"


def test_staff_list_page_loads_when_logged_in_as_admin(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="admin@example.com", role="admin"
    )
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": temp_password})

    r = client.get("/staff")
    assert r.status_code == 200


def test_staff_list_page_redirects_for_wrong_role(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="nurse@example.com", role="nurse"
    )
    client.post("/api/auth/login", json={"email": "nurse@example.com", "password": temp_password})

    r = client.get("/staff", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"
```

In `tests/test_auth.py`, change `_create_staff_and_get_temp_password` to accept a role (needed by the tests above and by later tasks) and add logout/session tests:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py tests/test_staff.py -v -k "session or logout or redirect"`
Expected: FAIL - `/api/auth/logout` doesn't exist (404), and `/staff` returns 200 today with no login at all instead of redirecting.

- [ ] **Step 3: Create the auth dependency module**

Create `src/agile_ci_demo/auth/deps.py`:

```python
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.staff.service import get_staff_by_staff_id


class NotAuthenticatedError(Exception):
    """Raised when a page needs a session that isn't there, or the wrong role is signed in."""


def login_staff(request: Request, staff: Staff) -> None:
    request.session["user_type"] = "staff"
    request.session["staff_id"] = staff.staff_id
    request.session["role"] = staff.role


def logout(request: Request) -> None:
    request.session.clear()


def require_role(*roles: Role):
    """Dependency factory: only lets the given staff roles through, otherwise redirects to login."""
    allowed = {role.value for role in roles}

    def dependency(request: Request, db: Session = Depends(get_db)) -> Staff:
        staff_id = request.session.get("staff_id")
        staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
        if staff is None or staff.role not in allowed:
            raise NotAuthenticatedError()
        return staff

    return dependency
```

- [ ] **Step 4: Wire the exception handler into the app**

In `src/agile_ci_demo/app.py`, add imports:

```python
from starlette.responses import RedirectResponse

from agile_ci_demo.auth.deps import NotAuthenticatedError
```

After the `app.add_middleware(...)` line from Task 1, add:

```python
@app.exception_handler(NotAuthenticatedError)
def handle_not_authenticated(request, exc: NotAuthenticatedError) -> RedirectResponse:
    return RedirectResponse("/auth/login", status_code=303)
```

- [ ] **Step 5: Make login write the session, add logout**

In `src/agile_ci_demo/auth/router.py`, change the `login` function signature to accept `request: Request` and call `login_staff`, and add a logout endpoint:

```python
from agile_ci_demo.auth.deps import login_staff, logout


@api_router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        staff = authenticate_staff(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AccountInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    login_staff(request, staff)
    return LoginResponse.model_validate(staff)


@api_router.post("/logout")
def logout_endpoint(request: Request) -> dict:
    logout(request)
    return {"status": "ok"}
```

(`Request` is already imported in this file.)

- [ ] **Step 6: Protect the staff list page**

In `src/agile_ci_demo/staff/router.py`, add the import:

```python
from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.rbac import Role
```

Change the staff list page handler to require an admin session:

```python
@pages_router.get(
    "",
    response_class=HTMLResponse,
)
def staff_list_page(
    request: Request,
    _staff=Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_list.html",
        {},
    )
```

(`Depends` is already imported in this file - check the existing import line and add it if not already there.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_auth.py tests/test_staff.py -v`
Expected: PASS - all of `test_auth.py` and `test_staff.py`, including the 3 new tests and the 2 new session tests.

Note: `test_staff_list_page_renders` (the pre-existing test) will now fail because it doesn't log in first - fix it now too:

```python
def test_staff_list_page_renders(client: TestClient) -> None:
    """The HTML staff list page loads successfully."""
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(client, role="admin")
    client.post(
        "/api/auth/login", json={"email": "alice.wong@example.com", "password": temp_password}
    )
    r = client.get("/staff")
    assert r.status_code == 200
```

- [ ] **Step 8: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/agile_ci_demo/auth src/agile_ci_demo/app.py src/agile_ci_demo/staff/router.py tests/test_auth.py tests/test_staff.py
git commit -m "Make staff login start a real session, add logout, protect the staff list page"
```

---

## Task 3: Patient login and the first protected patient page

**Files:**
- Modify: `src/agile_ci_demo/auth/schemas.py`
- Modify: `src/agile_ci_demo/auth/service.py`
- Modify: `src/agile_ci_demo/auth/router.py`
- Modify: `src/agile_ci_demo/auth/deps.py`
- Modify: `src/agile_ci_demo/patients/router.py` (protect the dashboard page as the proof point)
- Test: `tests/test_auth.py`, `tests/test_patients.py`

**Interfaces:**
- Consumes: `get_patient_by_patient_id(db, patient_id) -> Patient | None` (existing, from `agile_ci_demo.patients.service`).
- Produces: `authenticate_patient(db, patient_id, ic_or_passport) -> Patient` (raises `InvalidCredentialsError`), `login_patient(request, patient) -> None`, `require_patient` dependency returning `Patient` - both from `agile_ci_demo.auth.deps`, used by later tasks protecting patient pages.

- [ ] **Step 1: Write the failing tests**

In `tests/test_auth.py`, add:

```python
def test_patient_login_success(client: TestClient) -> None:
    """
    Scenario: A patient logs in with their patient ID and IC number
      Given a patient is registered
      When I POST /api/auth/patient-login with their patient ID and IC number
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
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
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
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    r = client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": "000000-00-0000"},
    )
    assert r.status_code == 401


def test_patient_login_unknown_patient_id_returns_401(client: TestClient) -> None:
    r = client.post(
        "/api/auth/patient-login",
        json={"patient_id": "P99999", "ic_or_passport": "000000-00-0000"},
    )
    assert r.status_code == 401
```

In `tests/test_patients.py`, add:

```python
def test_dashboard_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/dashboard", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/auth/login"


def test_dashboard_page_loads_when_logged_in_as_patient(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
    )

    r = client.get("/patients/dashboard")
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth.py tests/test_patients.py -v -k "patient_login or dashboard_page"`
Expected: FAIL - `/api/auth/patient-login` doesn't exist (404), and `/patients/dashboard` returns 200 with no login today.

- [ ] **Step 3: Add the schemas**

In `src/agile_ci_demo/auth/schemas.py`, add:

```python
class PatientLoginRequest(BaseModel):
    patient_id: str
    ic_or_passport: str


class PatientLoginResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    full_name: str
```

- [ ] **Step 4: Add the service function**

In `src/agile_ci_demo/auth/service.py`, add the import and function:

```python
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_patient_id


def authenticate_patient(db: Session, patient_id: str, ic_or_passport: str) -> Patient:
    """Verify a patient's ID and IC/passport number match a registered patient."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None or patient.ic_or_passport != ic_or_passport:
        raise InvalidCredentialsError("Invalid patient ID or IC/passport number")
    return patient
```

- [ ] **Step 5: Add login_patient and require_patient to auth/deps.py**

In `src/agile_ci_demo/auth/deps.py`, add the import and functions:

```python
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.patients.service import get_patient_by_patient_id


def login_patient(request: Request, patient: Patient) -> None:
    request.session["user_type"] = "patient"
    request.session["patient_id"] = patient.patient_id


def require_patient(request: Request, db: Session = Depends(get_db)) -> Patient:
    patient_id = request.session.get("patient_id")
    patient = get_patient_by_patient_id(db, patient_id) if patient_id else None
    if patient is None:
        raise NotAuthenticatedError()
    return patient
```

- [ ] **Step 6: Add the patient-login endpoint**

In `src/agile_ci_demo/auth/router.py`, add the import and endpoint:

```python
from agile_ci_demo.auth.deps import login_patient, login_staff, logout
from agile_ci_demo.auth.schemas import (
    LoginRequest,
    LoginResponse,
    PatientLoginRequest,
    PatientLoginResponse,
)
from agile_ci_demo.auth.service import authenticate_patient, authenticate_staff


@api_router.post("/patient-login", response_model=PatientLoginResponse)
def patient_login(
    payload: PatientLoginRequest, request: Request, db: Session = Depends(get_db)
) -> PatientLoginResponse:
    try:
        patient = authenticate_patient(db, payload.patient_id, payload.ic_or_passport)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    login_patient(request, patient)
    return PatientLoginResponse.model_validate(patient)
```

- [ ] **Step 7: Protect the patient dashboard page**

In `src/agile_ci_demo/patients/router.py`, add the import:

```python
from agile_ci_demo.auth.deps import require_patient
```

Change the dashboard page handler:

```python
@pages_router.get("/dashboard", response_class=HTMLResponse)
def patient_dashboard_page(request: Request, _patient=Depends(require_patient)) -> HTMLResponse:
    """Patient self-service home page."""
    return templates.TemplateResponse(request, "patients/patient_dashboard.html", {})
```

(Also remove the old docstring line about `get_current_patient` being a placeholder - it no longer is.)

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_auth.py tests/test_patients.py -v`
Expected: PASS

- [ ] **Step 9: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 10: Commit**

```bash
git add src/agile_ci_demo/auth src/agile_ci_demo/patients/router.py tests/test_auth.py tests/test_patients.py
git commit -m "Add patient login and protect the patient dashboard page"
```

---

## Task 4: Protect the rest of the patients pages

**Files:**
- Modify: `src/agile_ci_demo/patients/router.py`
- Test: `tests/test_patients.py`

**Interfaces:**
- Consumes: `require_role(*roles: Role)` (Task 2), `Role` enum (existing `agile_ci_demo.core.rbac`).

- [ ] **Step 1: Write the failing tests**

In `tests/test_patients.py`, add a small local login helper and the redirect tests:

```python
def _login_as_receptionist(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="receptionist@example.com", role="receptionist"
    )
    client.post(
        "/api/auth/login", json={"email": "receptionist@example.com", "password": temp_password}
    )


def test_register_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/register", follow_redirects=False)
    assert r.status_code == 303


def test_register_page_loads_when_logged_in_as_receptionist(client: TestClient) -> None:
    _login_as_receptionist(client)
    r = client.get("/patients/register")
    assert r.status_code == 200


def test_list_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients", follow_redirects=False)
    assert r.status_code == 303


def test_detail_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/patients/P00001", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_patients.py -v -k "redirects_when_not_logged_in or loads_when_logged_in_as_receptionist"`
Expected: FAIL - these pages return 200 to anyone today.

- [ ] **Step 3: Protect the pages**

In `src/agile_ci_demo/patients/router.py`, add the import (if not already present from Task 3):

```python
from agile_ci_demo.auth.deps import require_patient, require_role
from agile_ci_demo.core.rbac import Role
```

Update the three remaining page handlers:

```python
@pages_router.get("/register", response_class=HTMLResponse)
def register_patient_page(
    request: Request,
    _staff=Depends(require_role(Role.RECEPTIONIST, Role.NURSE, Role.DOCTOR, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "patients/receptionist_registerPatients.html", {})


@pages_router.get("", response_class=HTMLResponse)
def list_patients_page(
    request: Request,
    _staff=Depends(require_role(Role.RECEPTIONIST, Role.NURSE, Role.DOCTOR, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "patients/receptionist_viewPatients.html", {})


@pages_router.get("/{patient_id}", response_class=HTMLResponse)
def patient_detail_page(
    request: Request,
    patient_id: str,
    _staff=Depends(require_role(Role.RECEPTIONIST, Role.NURSE, Role.DOCTOR, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "patients/patients_details.html", {"patient_id": patient_id}
    )
```

- [ ] **Step 4: Fix the pre-existing "page renders" tests, which now need a login first**

In `tests/test_patients.py`, update both tests:

```python
def test_register_page_renders(client: TestClient) -> None:
    """The HTML registration form page loads successfully."""
    _login_as_receptionist(client)

    r = client.get("/patients/register")
    assert r.status_code == 200
    assert "Register New Patient" in r.text
```

```python
def test_list_page_renders(client: TestClient) -> None:
    """The HTML patient list page loads successfully."""
    _login_as_receptionist(client)

    r = client.get("/patients")
    assert r.status_code == 200
    assert "Patients" in r.text
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_patients.py -v`
Expected: PASS

- [ ] **Step 6: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/patients/router.py tests/test_patients.py
git commit -m "Require a front-desk login for the patient registration, list, and detail pages"
```

---

## Task 5: Protect the appointments pages

**Files:**
- Modify: `src/agile_ci_demo/appointments/router.py`
- Test: `tests/test_appointments.py`

**Interfaces:**
- Consumes: `require_role(*roles: Role)`, `require_patient` (Tasks 2-3), `Role` enum.

- [ ] **Step 1: Write the failing tests**

In `tests/test_appointments.py`, add:

```python
def test_create_appointment_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/appointments/create", follow_redirects=False)
    assert r.status_code == 303


def test_schedule_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/appointments/schedule", follow_redirects=False)
    assert r.status_code == 303


def test_book_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/appointments/book", follow_redirects=False)
    assert r.status_code == 303


def test_mine_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/appointments/mine", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_appointments.py -v -k redirects_when_not_logged_in`
Expected: FAIL - these all return 200 today.

- [ ] **Step 3: Protect the pages**

In `src/agile_ci_demo/appointments/router.py`, add the import:

```python
from agile_ci_demo.auth.deps import require_patient, require_role
from agile_ci_demo.core.rbac import Role
```

Update each page handler:

```python
@pages_router.get("/create", response_class=HTMLResponse)
def create_appointment_page(
    request: Request,
    _staff=Depends(require_role(Role.RECEPTIONIST, Role.NURSE, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "appointments/receptionist_createAppointment.html", {}
    )


@pages_router.get("/schedule", response_class=HTMLResponse)
def doctor_schedule_page(
    request: Request, _staff=Depends(require_role(Role.DOCTOR))
) -> HTMLResponse:
    return templates.TemplateResponse(request, "appointments/doctor_viewSchedule.html", {})


@pages_router.get("/consultations", response_class=HTMLResponse)
def start_consultation_page(
    request: Request, _staff=Depends(require_role(Role.DOCTOR))
) -> HTMLResponse:
    """Doctor's schedule with a "Start Consultation" action per appointment instead
    of "Cancel" - links into records.new_note_page (ping's consultation-note flow)."""
    return templates.TemplateResponse(request, "appointments/doctor_startConsultation.html", {})


@pages_router.get("/doctor-schedule", response_class=HTMLResponse)
def receptionist_doctor_schedule_page(
    request: Request,
    _staff=Depends(require_role(Role.RECEPTIONIST, Role.NURSE, Role.ADMIN)),
) -> HTMLResponse:
    """Front-desk view of any doctor's schedule for today, filterable by doctor."""
    return templates.TemplateResponse(
        request, "appointments/receptionist_viewDoctorSchedule.html", {}
    )


@pages_router.get("/book", response_class=HTMLResponse)
def self_book_appointment_page(
    request: Request, _patient=Depends(require_patient)
) -> HTMLResponse:
    """Patient self-service booking."""
    return templates.TemplateResponse(request, "appointments/patient_bookAppointment.html", {})


@pages_router.get("/mine", response_class=HTMLResponse)
def my_appointments_page(request: Request, _patient=Depends(require_patient)) -> HTMLResponse:
    return templates.TemplateResponse(request, "appointments/patient_appointment.html", {})
```

- [ ] **Step 4: Fix the pre-existing "page renders" tests, which now need a login first**

In `tests/test_appointments.py`, update these four tests:

```python
def test_create_appointment_page_renders(client: TestClient) -> None:
    """The HTML appointment booking form page loads successfully."""
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="receptionist@example.com", role="receptionist"
    )
    client.post(
        "/api/auth/login", json={"email": "receptionist@example.com", "password": temp_password}
    )

    r = client.get("/appointments/create")
    assert r.status_code == 200
    assert "Book Appointment" in r.text


def test_self_book_appointment_page_renders(client: TestClient) -> None:
    """The HTML patient self-service booking page loads successfully."""
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
    )

    r = client.get("/appointments/book")
    assert r.status_code == 200
    assert "Book My Appointment" in r.text
```

```python
def test_schedule_page_renders(client: TestClient) -> None:
    """The HTML doctor schedule page loads successfully."""
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    r = client.get("/appointments/schedule")
    assert r.status_code == 200
    assert "My Schedule" in r.text
```

```python
def test_my_appointments_page_renders(client: TestClient) -> None:
    """The HTML "My Appointments" page loads successfully."""
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
    )

    r = client.get("/appointments/mine")
    assert r.status_code == 200
    assert "My Appointments" in r.text
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_appointments.py -v`
Expected: PASS

- [ ] **Step 6: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/appointments/router.py tests/test_appointments.py
git commit -m "Require the right login for every appointment page"
```

---

## Task 6: Protect the records and staff pages

**Files:**
- Modify: `src/agile_ci_demo/records/router.py`
- Modify: `src/agile_ci_demo/staff/router.py`
- Test: `tests/test_records.py`, `tests/test_staff.py`

**Interfaces:**
- Consumes: `require_role(*roles: Role)` (Task 2), `Role` enum.

- [ ] **Step 1: Write the failing tests**

In `tests/test_records.py`, add:

```python
def test_new_record_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/records/new?patient_id=P00001", follow_redirects=False)
    assert r.status_code == 303


def test_record_detail_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/records/R00001", follow_redirects=False)
    assert r.status_code == 303
```

In `tests/test_staff.py`, add:

```python
def test_create_staff_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/staff/create", follow_redirects=False)
    assert r.status_code == 303


def test_staff_detail_page_redirects_when_not_logged_in(client: TestClient) -> None:
    r = client.get("/staff/S00001", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_records.py tests/test_staff.py -v -k redirects_when_not_logged_in`
Expected: FAIL - all four return 200 today.

- [ ] **Step 3: Protect the records pages**

In `src/agile_ci_demo/records/router.py`, add the import:

```python
from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.rbac import Role
```

Update both page handlers:

```python
@pages_router.get("/new", response_class=HTMLResponse)
def new_note_page(
    request: Request,
    patient_id: str = Query(..., description="Patient to document a visit for"),
    _staff=Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "records/new.html", {"patient_id": patient_id})


@pages_router.get("/{record_id}", response_class=HTMLResponse)
def note_detail_page(
    request: Request,
    record_id: str,
    _staff=Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(request, "records/detail.html", {"record_id": record_id})
```

- [ ] **Step 4: Protect the remaining staff pages**

In `src/agile_ci_demo/staff/router.py`, update the two remaining page handlers (the list page was already protected in Task 2):

```python
@pages_router.get(
    "/create",
    response_class=HTMLResponse,
)
def create_staff_page(
    request: Request,
    _staff=Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_create.html",
        {},
    )


@pages_router.get(
    "/{staff_id}",
    response_class=HTMLResponse,
)
def staff_detail_page(
    request: Request,
    staff_id: str,
    _staff=Depends(require_role(Role.ADMIN)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "staff/staff_view.html",
        {
            "staff_id": staff_id,
        },
    )
```

- [ ] **Step 5: Fix the pre-existing "page renders" tests, which now need a login first**

In `tests/test_records.py`, update both tests:

```python
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
```

In `tests/test_staff.py`, update:

```python
def test_create_staff_page_renders(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="admin@example.com", role="admin"
    )
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": temp_password})

    r = client.get("/staff/create")
    assert r.status_code == 200
    assert "Create Staff Account" in r.text
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_records.py tests/test_staff.py -v`
Expected: PASS

- [ ] **Step 7: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add src/agile_ci_demo/records/router.py src/agile_ci_demo/staff/router.py tests/test_records.py tests/test_staff.py
git commit -m "Require a login for the consultation-note and staff-admin pages"
```

---

## Task 7: Replace the placeholder "current user" logic with the real session

**Files:**
- Modify: `src/agile_ci_demo/appointments/router.py`
- Modify: `src/agile_ci_demo/appointments/service.py`
- Modify: `src/agile_ci_demo/patients/router.py`
- Modify: `src/agile_ci_demo/patients/service.py`
- Test: `tests/test_appointments.py`, `tests/test_patients.py`

**Interfaces:**
- Consumes: `require_role(*roles: Role)`, `require_patient` (Tasks 2-3).

- [ ] **Step 1: Write the failing tests**

In `tests/test_appointments.py`, add:

```python
def test_my_schedule_shows_the_logged_in_doctor(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="doctor@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "doctor@example.com", "password": temp_password})

    r = client.get("/api/appointments/schedule")
    assert r.status_code == 200
    assert r.json()["doctor_id"] == "S00001"


def test_my_appointments_shows_the_logged_in_patient(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
    )

    r = client.get("/api/appointments/mine")
    assert r.status_code == 200
    assert r.json()["patient_id"] == created["patient_id"]
```

In `tests/test_patients.py`, add:

```python
def test_me_endpoint_shows_the_logged_in_patient(client: TestClient) -> None:
    created = client.post("/api/patients", json=valid_patient_payload()).json()
    client.post(
        "/api/auth/patient-login",
        json={"patient_id": created["patient_id"], "ic_or_passport": created["ic_or_passport"]},
    )

    r = client.get("/api/patients/me")
    assert r.status_code == 200
    assert r.json()["patient_id"] == created["patient_id"]
```

- [ ] **Step 2: Run tests to verify they fail, then add the test that actually proves the bug**

Run: `pytest tests/test_appointments.py tests/test_patients.py -v -k "logged_in_doctor or logged_in_patient"`

These two may already pass today even though the underlying code is still using the placeholder,
because the placeholder picks "the first doctor/patient in the database" - which happens to be the
same one just created and logged in as, in a fresh single-user test DB. That coincidence means
they don't actually prove anything yet. Add this test to `tests/test_appointments.py`, which
creates a *second* doctor so the placeholder (still active at this point) and the real session
identity point at two different people:

```python
def test_my_schedule_does_not_show_a_different_doctor(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    # First doctor created - the old placeholder logic would have picked this one.
    _create_staff_and_get_temp_password(client, email="first@example.com", role="doctor")
    temp_password = _create_staff_and_get_temp_password(
        client, email="second@example.com", role="doctor"
    )
    client.post("/api/auth/login", json={"email": "second@example.com", "password": temp_password})

    r = client.get("/api/appointments/schedule")
    assert r.json()["doctor_id"] == "S00002"
```

Run: `pytest tests/test_appointments.py::test_my_schedule_does_not_show_a_different_doctor -v`
Expected: FAIL - today this returns `S00001` (the first doctor), not the one actually logged in.

- [ ] **Step 3: Replace the placeholder in appointments**

In `src/agile_ci_demo/appointments/router.py`:

Remove `get_current_doctor` and `get_current_patient` from the imports (the `from agile_ci_demo.appointments.service import (...)` block and the `from agile_ci_demo.patients.service import get_current_patient` line).

Add:

```python
from agile_ci_demo.auth.deps import require_patient, require_role
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.staff.models import Staff
from agile_ci_demo.patients.models import Patient
```

Change `get_my_schedule`:

```python
@api_router.get("/schedule", response_model=DoctorSchedule)
def get_my_schedule(
    schedule_date: dt.date = Query(default_factory=dt.date.today, alias="date"),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    """The logged-in doctor's appointments for a given date (defaults to today)."""
    try:
        appointments = get_doctor_schedule(db, doctor.id, schedule_date)
    except PastDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return DoctorSchedule(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        schedule_date=schedule_date,
        appointments=[_serialize(a) for a in appointments],
    )
```

Change `get_my_appointments`:

```python
@api_router.get("/mine", response_model=PatientAppointments)
def get_my_appointments(
    patient: Patient = Depends(require_patient), db: Session = Depends(get_db)
) -> PatientAppointments:
    """The logged-in patient's own upcoming appointments (today or later)."""
    appointments = get_patient_appointments(db, patient.id)
    return PatientAppointments(
        patient_id=patient.patient_id or "",
        patient_name=patient.full_name,
        appointments=[_serialize(a) for a in appointments],
    )
```

- [ ] **Step 4: Delete the now-unused get_current_doctor**

In `src/agile_ci_demo/appointments/service.py`, delete the `get_current_doctor` function entirely (search for `def get_current_doctor`).

- [ ] **Step 5: Replace the placeholder in patients**

In `src/agile_ci_demo/patients/router.py`, remove `get_current_patient` from the import block, add:

```python
from agile_ci_demo.auth.deps import require_patient
from agile_ci_demo.patients.models import Patient
```

Change `get_my_patient_record`:

```python
@api_router.get("/me", response_model=PatientOut)
def get_my_patient_record(patient: Patient = Depends(require_patient)) -> PatientOut:
    """The logged-in patient's own record, for self-service booking."""
    return PatientOut.model_validate(patient)
```

- [ ] **Step 6: Delete the now-unused get_current_patient**

In `src/agile_ci_demo/patients/service.py`, delete the `get_current_patient` function entirely (search for `def get_current_patient`). Check no other file still imports it: `grep -rn "get_current_patient" src/` should show nothing left except in `auth/deps.py`'s unrelated `login_patient`/`require_patient` (those are new functions with different names, not this one).

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_appointments.py tests/test_patients.py -v`
Expected: PASS, including `test_my_schedule_does_not_show_a_different_doctor`.

- [ ] **Step 8: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass. Note the self-booking JS's auto-fill (`GET /api/patients/me`) and "my schedule"/"my appointments" pages keep working exactly as before from the frontend's point of view - only where the identity comes from changed.

- [ ] **Step 9: Commit**

```bash
git add src/agile_ci_demo/appointments src/agile_ci_demo/patients tests/test_appointments.py tests/test_patients.py
git commit -m "Use the real logged-in doctor and patient instead of always picking the first one in the database"
```

---

## Task 8: Login page with staff and patient tabs

**Files:**
- Modify: `templates/auth/login.html`
- Modify: `static/js/auth-login.js`

**Interfaces:**
- Consumes: `POST /api/auth/login` (existing, now sets session), `POST /api/auth/patient-login` (Task 3).

- [ ] **Step 1: Look at the current login page**

Run: `cat templates/auth/login.html`

Note the existing form's field IDs and structure so the rewrite keeps the same alert/validation pattern.

- [ ] **Step 2: Rewrite the login page with two tabs**

Replace the content block of `templates/auth/login.html` with:

```html
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-6">
    <h1 class="h3 mb-4">Login</h1>

    <ul class="nav nav-tabs mb-3" id="login-tabs" role="tablist">
      <li class="nav-item" role="presentation">
        <button class="nav-link active" id="staff-tab-btn" data-bs-toggle="tab"
                data-bs-target="#staff-tab" type="button" role="tab">Staff</button>
      </li>
      <li class="nav-item" role="presentation">
        <button class="nav-link" id="patient-tab-btn" data-bs-toggle="tab"
                data-bs-target="#patient-tab" type="button" role="tab">Patient</button>
      </li>
    </ul>

    <div id="form-alert" class="alert alert-danger d-none" role="alert"></div>

    <div class="tab-content">
      <div class="tab-pane fade show active" id="staff-tab" role="tabpanel">
        <form id="staff-login-form" novalidate>
          <div class="mb-3">
            <label for="staff-email" class="form-label">Email</label>
            <input type="email" class="form-control" id="staff-email" name="email" required>
            <div class="invalid-feedback">Email is required.</div>
          </div>
          <div class="mb-3">
            <label for="staff-password" class="form-label">Password</label>
            <input type="password" class="form-control" id="staff-password" name="password" required>
            <div class="invalid-feedback">Password is required.</div>
          </div>
          <button type="submit" class="btn btn-primary" id="staff-submit-btn">Log In</button>
        </form>
      </div>

      <div class="tab-pane fade" id="patient-tab" role="tabpanel">
        <form id="patient-login-form" novalidate>
          <div class="mb-3">
            <label for="patient-id" class="form-label">Patient ID</label>
            <input type="text" class="form-control" id="patient-id" name="patient_id" required
                   placeholder="e.g. P00001">
            <div class="invalid-feedback">Patient ID is required.</div>
          </div>
          <div class="mb-3">
            <label for="patient-ic" class="form-label">IC / Passport number</label>
            <input type="text" class="form-control" id="patient-ic" name="ic_or_passport" required>
            <div class="invalid-feedback">IC / passport number is required.</div>
          </div>
          <button type="submit" class="btn btn-primary" id="patient-submit-btn">Log In</button>
        </form>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="/static/js/auth-login.js"></script>
{% endblock %}
```

- [ ] **Step 3: Rewrite auth-login.js for both forms**

Replace the entire content of `static/js/auth-login.js`:

```javascript
(function () {
  "use strict";

  const alertBox = document.getElementById("form-alert");

  const REDIRECT_BY_ROLE = {
    admin: "/staff",
    doctor: "/appointments/schedule",
    nurse: "/patients",
    receptionist: "/patients",
  };

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  async function handleStaffSubmit(event) {
    event.preventDefault();
    hideAlert();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("staff-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: data.get("email")?.trim(),
          password: data.get("password"),
        }),
      });

      if (response.ok) {
        const body = await response.json();
        window.location.href = REDIRECT_BY_ROLE[body.role] || "/patients";
        return;
      }

      const body = await response.json().catch(() => ({}));
      if (response.status === 403) {
        showAlert(body.detail || "This account has been deactivated.");
      } else if (response.status === 401) {
        showAlert(body.detail || "Invalid email or password.");
      } else {
        showAlert("Something went wrong while logging in. Please try again.");
      }
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function handlePatientSubmit(event) {
    event.preventDefault();
    hideAlert();
    const form = event.target;
    if (!form.checkValidity()) {
      form.classList.add("was-validated");
      return;
    }

    const data = new FormData(form);
    const submitBtn = document.getElementById("patient-submit-btn");
    submitBtn.disabled = true;
    try {
      const response = await fetch("/api/auth/patient-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: data.get("patient_id")?.trim(),
          ic_or_passport: data.get("ic_or_passport")?.trim(),
        }),
      });

      if (response.ok) {
        window.location.href = "/patients/dashboard";
        return;
      }

      const body = await response.json().catch(() => ({}));
      showAlert(body.detail || "Invalid patient ID or IC/passport number.");
    } catch (err) {
      showAlert("Unable to reach the server. Please check your connection and try again.");
    } finally {
      submitBtn.disabled = false;
    }
  }

  const staffForm = document.getElementById("staff-login-form");
  const patientForm = document.getElementById("patient-login-form");
  if (staffForm) staffForm.addEventListener("submit", handleStaffSubmit);
  if (patientForm) patientForm.addEventListener("submit", handlePatientSubmit);
})();
```

- [ ] **Step 4: Run the full test suite (no test file changes in this task, but confirm nothing broke)**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass (this task is templates/JS only, not covered by pytest, but must not break anything else)

- [ ] **Step 5: Manual browser check**

Start the dev server and visit `/auth/login`. Confirm: both tabs show and switch correctly, staff login with a known account redirects to the right page for that role, patient login with a patient ID + IC redirects to `/patients/dashboard`, and a wrong password/IC shows the error alert without a page reload.

- [ ] **Step 6: Commit**

```bash
git add templates/auth/login.html static/js/auth-login.js
git commit -m "Add a patient tab to the login page, and send each role to the right page after login"
```

---

## Task 9: Real nav bar, remove the fake role switcher

**Files:**
- Modify: `templates/base.html`
- Delete: `static/js/role-view.js`

**Interfaces:**
- Consumes: `request.session` (set by Tasks 2-3's `login_staff`/`login_patient`).

- [ ] **Step 1: Look at the current nav bar**

Run: `cat templates/base.html`

Note the current `data-role` links and the role-switcher `<select>` block, to be replaced.

- [ ] **Step 2: Rewrite the nav bar**

Replace the `<nav>` block and the "Viewing as" div in `templates/base.html` with:

```html
{% set role = request.session.get("role") %}
{% set is_patient = request.session.get("user_type") == "patient" %}
<nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-2">
  <div class="container">
    <a class="navbar-brand" href="/patients">Agile Clinic Portal</a>
    <div class="navbar-nav">
      {% if role in ["receptionist", "nurse", "doctor", "admin"] %}
        <a class="nav-link" href="/patients">Patients</a>
        <a class="nav-link" href="/patients/register">Register Patient</a>
      {% endif %}
      {% if role in ["receptionist", "nurse", "admin"] %}
        <a class="nav-link" href="/appointments/create">Book Appointment</a>
        <a class="nav-link" href="/appointments/doctor-schedule">Doctor Schedule</a>
      {% endif %}
      {% if role == "doctor" %}
        <a class="nav-link" href="/appointments/schedule">My Schedule</a>
        <a class="nav-link" href="/appointments/consultations">Start Consultation</a>
      {% endif %}
      {% if is_patient %}
        <a class="nav-link" href="/patients/dashboard">My Dashboard</a>
        <a class="nav-link" href="/appointments/book">Book My Appointment</a>
        <a class="nav-link" href="/appointments/mine">My Appointments</a>
      {% endif %}
      {% if role == "admin" %}
        <a class="nav-link" href="/staff">Staff</a>
      {% endif %}
      {% if role or is_patient %}
        <a class="nav-link" href="#" id="logout-link">Logout</a>
      {% else %}
        <a class="nav-link" href="/auth/login">Login</a>
      {% endif %}
    </div>
  </div>
</nav>
```

Remove the old `<div class="bg-warning-subtle border-bottom">...Viewing as...</div>` block entirely, and remove `<script src="/static/js/role-view.js"></script>`.

Add a small inline script right before `{% block extra_js %}` to wire up logout (keeps this task self-contained without a new JS file for one click handler):

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

- [ ] **Step 3: Delete the old role-switcher script**

Run: `rm static/js/role-view.js`

- [ ] **Step 4: Run full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass

- [ ] **Step 5: Manual browser check**

Log in as each role in turn (doctor, receptionist, admin, patient) and confirm the nav shows only the links that role should see, and Logout returns you to the login page and actually clears the session (visiting a protected page afterward redirects to login again).

- [ ] **Step 6: Commit**

```bash
git add templates/base.html
git rm static/js/role-view.js
git commit -m "Show real nav links based on who's actually logged in, remove the fake role switcher"
```

---

## Self-Review Notes

- **Spec coverage**: session mechanism (Task 1), staff login sets session + logout (Task 2), patient login (Task 3), page protection for patients/appointments/records/staff (Tasks 2, 4, 5, 6), placeholder replacement + deletion (Task 7), login page UI with redirect-by-role (Task 8), nav bar + role-switcher removal (Task 9). All design sections are covered.
- **Placeholder scan**: no TBDs; every step has complete, runnable code.
- **Type consistency**: `require_role(*roles: Role) -> Callable[..., Staff]` and `require_patient(request, db) -> Patient` are defined once in Task 2/3 and referenced with the same names and signatures in every later task. `login_staff`/`login_patient`/`logout`/`NotAuthenticatedError` are likewise defined once and reused as-is.
- **Test file conventions followed**: every new test reuses each file's existing local `client` fixture and payload helpers rather than introducing a new pattern, matching how this codebase's test suite is already organized (helpers duplicated per file, not shared).
- **Known accepted trade-off**: `require_role`/`require_patient` always redirect (303) when there's no valid session, even on the 3 API endpoints from Task 7 that a page's own JavaScript calls in the background (`/api/appointments/schedule`, `/api/appointments/mine`, `/api/patients/me`). In practice this only matters if a session expires in the gap between loading the page (which is itself already gated) and that background call firing - a rare case. A cleaner fix would return a 401 for API calls and a redirect for page loads, but that's extra branching this plan intentionally skips to keep the dependency simple, per the "keep code as simple as possible" constraint. Worth a follow-up later if it turns out to matter in practice.
