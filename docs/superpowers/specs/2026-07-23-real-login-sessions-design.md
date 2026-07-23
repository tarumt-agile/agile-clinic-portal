# Real login sessions - design

## Goal

Replace every "current user" placeholder (`get_current_doctor()`, `get_current_patient()`) with
identity resolved from a real login session, for every role (admin, doctor, nurse, receptionist,
patient), and protect every page so visiting it while logged in as the wrong role (or not logged
in) redirects to the login page instead of just being visible.

This replaces the cosmetic "Viewing as" nav switcher, which only ever changed what was *shown*,
never what was actually allowed.

## Session mechanism

Starlette's built-in `SessionMiddleware` - a signed cookie holding the logged-in identity. No new
database table. Added to `app.py` with a `SECRET_KEY` from `Settings` (env var, falls back to a
fixed dev value so local runs and tests don't need a `.env` entry to work).

Session contents:

```python
{"user_type": "staff", "staff_id": "S00001", "role": "doctor"}
# or
{"user_type": "patient", "patient_id": "P00001"}
```

New dependency: `itsdangerous` (required by `SessionMiddleware`, not currently installed).

## Login

**Staff** - existing `POST /api/auth/login` (email + password) now also writes the session on
success. No API shape change.

**Patient** - new `POST /api/auth/patient-login`, taking `patient_id` + `ic_or_passport` (reuses
the IC lookup already built this session; no new database column, no password to manage).

`login.html` gets a two-tab layout: Staff (email/password) and Patient (patient ID/IC), each
posting to its own endpoint. Both redirect to a role-appropriate landing page on success
(`/patients/dashboard` for a patient, `/appointments/schedule` for a doctor, `/patients` for
receptionist/nurse, `/staff` for admin).

`POST /api/auth/logout` clears the session. A "Logout" link replaces "Login" in the nav once
someone is signed in.

## Protecting pages

Two small dependencies, reused everywhere:

```python
def require_role(*roles: Role):
    def dependency(request: Request, db: Session = Depends(get_db)) -> Staff:
        staff_id = request.session.get("staff_id")
        staff = get_staff_by_staff_id(db, staff_id) if staff_id else None
        if staff is None or staff.role not in [r.value for r in roles]:
            raise NotAuthenticatedError()
        return staff
    return dependency

def require_patient(request: Request, db: Session = Depends(get_db)) -> Patient:
    patient_id = request.session.get("patient_id")
    patient = get_patient_by_patient_id(db, patient_id) if patient_id else None
    if patient is None:
        raise NotAuthenticatedError()
    return patient
```

`NotAuthenticatedError` is a one-line custom exception with an app-wide handler that redirects to
`/auth/login` (303). Every protected page adds one `Depends(...)` parameter - no change to the
page's own logic.

Route -> required role:

| Route | Role |
|---|---|
| `/patients/register`, `/patients` (list), `/patients/{id}` | receptionist, nurse, doctor, admin |
| `/patients/dashboard` | patient |
| `/appointments/create`, `/appointments/doctor-schedule` | receptionist, nurse, admin |
| `/appointments/schedule`, `/appointments/consultations` | doctor |
| `/appointments/book`, `/appointments/mine` | patient |
| `/records/new`, `/records/{id}` | doctor, nurse, receptionist, admin |
| `/staff`, `/staff/create`, `/staff/{id}` | admin |
| `/auth/login` | public (no protection) |

Patient detail/records pages allow any staff role since front-desk, nurses, and doctors all
legitimately look patients up - only the staff-only admin pages (`/staff/*`) and the
appointment-booking/schedule pages are role-specific.

## Replacing the placeholders

Three call sites actually use the placeholders today (the `prescription` module also calls
`get_current_doctor()`, but that module isn't wired into the app - left untouched):

- `GET /api/appointments/schedule` - doctor comes from the session instead of "first doctor in DB"
- `GET /api/appointments/mine` - patient comes from the session instead of "first patient in DB"
- `GET /api/patients/me` - same

`get_current_doctor()` and `get_current_patient()` are deleted once nothing calls them.

## Nav bar

`base.html` already receives `request` in its template context (every `TemplateResponse` call
passes it). Nav links switch from client-side JS filtering to plain Jinja conditionals reading
`request.session`:

```jinja
{% set role = request.session.get("role") %}
{% set patient_id = request.session.get("patient_id") %}
```

`role-view.js` and the "Viewing as" dropdown are removed - real session state replaces them
directly, no JS needed. Nav shows "Logged in as <name> (<role>)" and a Logout link when signed in.

## Test impact

Existing "page renders" tests (`test_register_page_renders`, `test_schedule_page_renders`,
`test_staff_list_page_renders`, etc.) currently hit protected pages with no login and expect 200.
Once pages redirect unauthenticated visitors, those need a login step first. `TestClient` persists
cookies across requests automatically (same as a real browser), so each test file gets one small
helper (`_login_as_doctor(client)`, etc.) that logs in before the assertions that need it. New
tests cover: successful staff login sets a session, successful patient login sets a session, wrong
role redirects, no session redirects, logout clears the session.

## Out of scope (not part of this change)

- API endpoints that already take an explicit `patient_id`/`doctor_id` in their payload (e.g.
  `POST /api/appointments`) are not gaining new authorization checks - only the ones that used a
  placeholder for "current user" are changing.
- The `records` and `staff` page routes get the same `Depends(require_role(...))` treatment as
  `patients`/`appointments`, but their internal page logic is untouched.
- Password reset / "forgot password" flows are not part of this.
