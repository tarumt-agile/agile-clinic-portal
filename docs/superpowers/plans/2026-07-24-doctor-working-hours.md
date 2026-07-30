# Doctor Working Hours Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin set each doctor's own working hours, with appointment booking and the available-slots grid respecting each doctor's individual hours instead of one clinic-wide constant. A change only takes effect starting the day after it's saved.

**Architecture:** Two new column pairs on `DoctorProfile` (current hours, and an optional queued next-day change), resolved by one pure function `get_doctor_hours(profile, date)` that every other piece of code calls instead of reading the columns directly. Admin edits the hours through the existing staff detail page's edit form (no new page). `appointments/service.py`'s slot grid and booking validation switch from the global `CLINIC_OPEN`/`CLINIC_CLOSE` constants to this per-doctor resolution.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite), Jinja2 templates, vanilla JS, pytest.

## Global Constraints

- Commit messages: plain-language, non-technical (this is graded university coursework read by non-technical reviewers).
- Commit directly - never add a `Co-Authored-By` trailer or any AI-attribution line to any commit.
- Keep code as simple as possible: no new libraries, no new pages/endpoints beyond what's specified below.
- Full check suite (`ruff check . && black --check . && mypy src && pytest --disable-warnings -q`) must pass before every commit.
- Only one change can be queued per doctor at a time - saving a new edit before a previously-queued change has taken effect replaces it (this is by design, not a bug to fix).
- Existing booked appointments are never touched or blocked by an hours change, even if the appointment falls outside the new range.

---

### Task 1: Per-doctor working-hours columns and the resolution function

**Files:**
- Modify: `src/agile_ci_demo/staff/models.py`
- Modify: `src/agile_ci_demo/core/database.py`
- Test: `tests/test_staff.py`

**Interfaces:**
- Produces: `get_doctor_hours(profile: DoctorProfile, date: dt.date) -> tuple[dt.time, dt.time]` in `agile_ci_demo.staff.models` - the single source of truth every later task uses to find a doctor's hours on a given date. `Staff.start_time` / `Staff.end_time` properties (both `dt.time | None`) resolving today's effective hours, for use by `StaffOut` in Task 2.

- [ ] **Step 1: Write the failing tests**

In `tests/test_staff.py`, add (these don't need the `client` fixture - they build a `DoctorProfile` directly in memory):

```python
def test_get_doctor_hours_uses_current_pair_when_no_change_queued() -> None:
    import datetime as dt

    from agile_ci_demo.staff.models import DoctorProfile, get_doctor_hours

    profile = DoctorProfile(
        license_number="MMC-11111",
        specialty="Cardiology",
        department="Cardiology",
        start_time=dt.time(9, 0),
        end_time=dt.time(17, 0),
    )

    assert get_doctor_hours(profile, dt.date(2026, 1, 1)) == (dt.time(9, 0), dt.time(17, 0))


def test_get_doctor_hours_uses_queued_pair_once_effective_date_reached() -> None:
    import datetime as dt

    from agile_ci_demo.staff.models import DoctorProfile, get_doctor_hours

    profile = DoctorProfile(
        license_number="MMC-11111",
        specialty="Cardiology",
        department="Cardiology",
        start_time=dt.time(9, 0),
        end_time=dt.time(17, 0),
        next_start_time=dt.time(10, 0),
        next_end_time=dt.time(16, 0),
        next_effective_date=dt.date(2026, 1, 2),
    )

    # The day before the queued change - still the current pair.
    assert get_doctor_hours(profile, dt.date(2026, 1, 1)) == (dt.time(9, 0), dt.time(17, 0))
    # Exactly the effective date - the queued pair now applies.
    assert get_doctor_hours(profile, dt.date(2026, 1, 2)) == (dt.time(10, 0), dt.time(16, 0))
    # Any later date - the queued pair still applies.
    assert get_doctor_hours(profile, dt.date(2026, 1, 5)) == (dt.time(10, 0), dt.time(16, 0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_staff.py -v -k get_doctor_hours`
Expected: FAIL with `ImportError: cannot import name 'get_doctor_hours'`

- [ ] **Step 3: Add the columns and the resolution function**

In `src/agile_ci_demo/staff/models.py`, change the import line:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, String
```

to:

```python
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Time
```

Add five columns to `DoctorProfile` (after the existing `status` column):

```python
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Working hours in effect right now (used for today and any date without a
    # newer change queued). New doctors default to the clinic's old 9-5 hours.
    start_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(9, 0))
    end_time: Mapped[dt.time] = mapped_column(Time, default=dt.time(17, 0))

    # A queued future change, set when an admin edits a doctor's hours. Only one
    # change can be queued at a time - see get_doctor_hours() below.
    next_start_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    next_end_time: Mapped[dt.time | None] = mapped_column(Time, nullable=True)
    next_effective_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
```

Add the resolution function after the `DoctorProfile` class:

```python
def get_doctor_hours(profile: DoctorProfile, date: dt.date) -> tuple[dt.time, dt.time]:
    """The doctor's working hours in effect on the given date. A queued change
    (next_start_time/next_end_time) only applies from next_effective_date onward -
    before that, the current start_time/end_time pair still applies."""
    if profile.next_effective_date is not None and date >= profile.next_effective_date:
        return profile.next_start_time, profile.next_end_time
    return profile.start_time, profile.end_time
```

Add two properties to `Staff` (after the existing `doctor_status` property), so `StaffOut` can expose today's effective hours the same way it already exposes `license_number`/`specialty`:

```python
    @property
    def start_time(self) -> dt.time | None:
        if self.doctor_profile is None:
            return None
        return get_doctor_hours(self.doctor_profile, dt.date.today())[0]

    @property
    def end_time(self) -> dt.time | None:
        if self.doctor_profile is None:
            return None
        return get_doctor_hours(self.doctor_profile, dt.date.today())[1]
```

(`get_doctor_hours` is defined later in the same file - that's fine, Python resolves it at call time, not at class-definition time.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_staff.py -v -k get_doctor_hours`
Expected: PASS

- [ ] **Step 5: Add the SQLite migration**

In `src/agile_ci_demo/core/database.py`, inside `migrate_sqlite_database()`, add this block after the existing `prescription_history` block (still inside the `with engine.begin() as connection:` block):

```python
        # Add working-hours columns to old doctor_profiles table.
        if "doctor_profiles" in table_names:
            doctor_columns = {
                column["name"] for column in inspector.get_columns("doctor_profiles")
            }

            if "start_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN start_time TIME
                        """))

            if "end_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN end_time TIME
                        """))

            if "next_start_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_start_time TIME
                        """))

            if "next_end_time" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_end_time TIME
                        """))

            if "next_effective_date" not in doctor_columns:
                connection.execute(text("""
                        ALTER TABLE doctor_profiles
                        ADD COLUMN next_effective_date DATE
                        """))

            # Give existing doctors the clinic's old default hours.
            connection.execute(text("""
                    UPDATE doctor_profiles
                    SET start_time = '09:00:00'
                    WHERE start_time IS NULL
                    """))

            connection.execute(text("""
                    UPDATE doctor_profiles
                    SET end_time = '17:00:00'
                    WHERE end_time IS NULL
                    """))
```

Note: the automated test suite always starts from a fresh in-memory database via `Base.metadata.create_all()`, so this migration path is never exercised by `pytest` - it only matters for a real, pre-existing `clinic.db` file (the same is true of every other block already in this function). No test is needed for this step; it's covered by manual verification in Task 4.

- [ ] **Step 6: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/staff/models.py src/agile_ci_demo/core/database.py tests/test_staff.py
git commit -m "Let each doctor have their own working hours in the database"
```

---

### Task 2: Admin can edit a doctor's working hours, effective the next day

**Files:**
- Modify: `src/agile_ci_demo/staff/schemas.py`
- Modify: `src/agile_ci_demo/staff/service.py`
- Test: `tests/test_staff.py`

**Interfaces:**
- Consumes: `get_doctor_hours(profile, date)` (Task 1).
- Produces: `StaffUpdate.start_time` / `StaffUpdate.end_time` (`dt.time | None`), `StaffOut.start_time` / `StaffOut.end_time` (`dt.time | None`) - both consumed by Task 3's UI.

- [ ] **Step 1: Write the failing tests**

In `tests/test_staff.py`, add a small admin-login helper near the top (after `valid_staff_payload`, following the same pattern already used for other roles elsewhere in this test suite):

```python
def _login_as_admin(client: TestClient) -> None:
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="admin@example.com", role="admin"
    )
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": temp_password})
```

Then add these tests:

```python
def _register_doctor_for_hours_test(client: TestClient) -> str:
    created = client.post(
        "/api/staff",
        json=valid_staff_payload(
            email="doctor@example.com",
            role="doctor",
            license_number="MMC-12345",
            specialty="Cardiology",
            status="active",
        ),
    ).json()
    return str(created["staff_id"])


def _doctor_update_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Dr. Alan Chua",
        "email": "doctor@example.com",
        "is_active": True,
        "license_number": "MMC-12345",
        "specialty": "Cardiology",
        "doctor_status": "active",
        "start_time": "10:00",
        "end_time": "16:00",
    }
    payload.update(overrides)
    return payload


def test_update_staff_new_hours_do_not_apply_today(client: TestClient) -> None:
    """
    Scenario: Admin changes a doctor's working hours
      Given a doctor with the default 09:00-17:00 hours
      When admin PATCHes new hours for that doctor
      Then today's effective hours in the response are unchanged
    """
    staff_id = _register_doctor_for_hours_test(client)
    _login_as_admin(client)

    r = client.patch(f"/api/staff/{staff_id}", json=_doctor_update_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["start_time"] == "09:00:00"
    assert body["end_time"] == "17:00:00"


def test_update_staff_requires_start_before_end(client: TestClient) -> None:
    staff_id = _register_doctor_for_hours_test(client)
    _login_as_admin(client)

    r = client.patch(
        f"/api/staff/{staff_id}",
        json=_doctor_update_payload(start_time="16:00", end_time="10:00"),
    )
    assert r.status_code == 422


def test_update_staff_requires_30_minute_alignment(client: TestClient) -> None:
    staff_id = _register_doctor_for_hours_test(client)
    _login_as_admin(client)

    r = client.patch(
        f"/api/staff/{staff_id}",
        json=_doctor_update_payload(start_time="09:15", end_time="16:00"),
    )
    assert r.status_code == 422


def test_update_staff_second_edit_collapses_the_first_queued_change() -> None:
    """
    Scenario: Admin edits a doctor's hours twice
      Given a doctor's hours were already queued to change, and that change's
        effective date has already arrived (simulated directly, without waiting
        a real day)
      When admin edits the hours again, calling update_staff() directly
      Then the queued change has become the doctor's current hours, and the new
        edit queues a further change for the day after today

    This test builds its own isolated in-memory database and calls update_staff()
    directly (bypassing the HTTP layer and the client fixture) because it needs
    precise control over next_effective_date relative to "today" at test-run
    time - something the real day-by-day flow can't be driven through in a fast
    automated test.
    """
    import datetime as dt

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from agile_ci_demo.core.database import Base
    from agile_ci_demo.staff.models import DoctorProfile, Staff
    from agile_ci_demo.staff.schemas import StaffUpdate
    from agile_ci_demo.staff.service import update_staff

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    staff = Staff(
        staff_id="S00001",
        full_name="Dr. Alan Chua",
        email="alan.chua@example.com",
        role="doctor",
        password_hash="x",
        is_active=True,
    )
    db.add(staff)
    db.flush()

    profile = DoctorProfile(
        doctor_id="D00001",
        staff_account_id=staff.id,
        license_number="MMC-12345",
        specialty="Cardiology",
        department="Cardiology",
        start_time=dt.time(9, 0),
        end_time=dt.time(17, 0),
        next_start_time=dt.time(10, 0),
        next_end_time=dt.time(18, 0),
        next_effective_date=dt.date.today(),  # already in effect as of today
    )
    db.add(profile)
    db.commit()

    update_staff(
        db,
        "S00001",
        StaffUpdate(
            full_name="Dr. Alan Chua",
            email="alan.chua@example.com",
            is_active=True,
            license_number="MMC-12345",
            specialty="Cardiology",
            doctor_status="active",
            start_time=dt.time(9, 0),
            end_time=dt.time(16, 0),
        ),
    )

    db.refresh(profile)
    # The already-effective queued change (10:00-18:00) is now "current"...
    assert profile.start_time == dt.time(10, 0)
    assert profile.end_time == dt.time(18, 0)
    # ...and the new edit is queued for tomorrow.
    assert profile.next_start_time == dt.time(9, 0)
    assert profile.next_end_time == dt.time(16, 0)
    assert profile.next_effective_date == dt.date.today() + dt.timedelta(days=1)

    db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_staff.py -v -k "update_staff_new_hours or update_staff_requires or update_staff_second_edit"`
Expected: FAIL. The first three fail with 422 assertion mismatches (the endpoint doesn't accept `start_time`/`end_time` yet - passing them today either gets silently dropped by Pydantic or has no effect on `update_staff`'s behavior, so nothing is rejected and today's values never move off the Task-1 default). The fourth fails because `update_staff` doesn't yet touch `start_time`/`end_time`/`next_*` at all, so `profile.start_time` stays `09:00` instead of collapsing to `10:00`.

- [ ] **Step 3: Add the schema fields**

In `src/agile_ci_demo/staff/schemas.py`, add to `StaffOut` (after `doctor_status`):

```python
    doctor_status: str | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
```

Add to `StaffUpdate` (after `doctor_status`):

```python
    doctor_status: DoctorStatus | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
```

- [ ] **Step 4: Wire the collapse-then-queue logic into update_staff**

In `src/agile_ci_demo/staff/service.py`, add the import at the top:

```python
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
```

In `update_staff`, add this block right after the existing `staff.is_active = doctor.status == DoctorStatus.ACTIVE.value` line (still inside the `if staff.role == Role.DOCTOR.value:` block, before the `try:` that commits):

```python
        staff.is_active = doctor.status == DoctorStatus.ACTIVE.value

        if data.start_time is None:
            raise ValueError("Working hours start time is required for a doctor.")

        if data.end_time is None:
            raise ValueError("Working hours end time is required for a doctor.")

        if data.start_time >= data.end_time:
            raise ValueError("Working hours start time must be before the end time.")

        # 30 minutes matches SLOT_MINUTES in appointments/service.py - duplicated
        # here as a plain number rather than imported, to avoid a circular import
        # between the staff and appointments modules.
        for label, value in (("start", data.start_time), ("end", data.end_time)):
            minutes_since_midnight = value.hour * 60 + value.minute
            if minutes_since_midnight % 30 != 0:
                raise ValueError(f"Working hours {label} time must align to 30-minute slots.")

        today = dt.date.today()
        if doctor.next_effective_date is not None and doctor.next_effective_date <= today:
            doctor.start_time = doctor.next_start_time
            doctor.end_time = doctor.next_end_time

        doctor.next_start_time = data.start_time
        doctor.next_end_time = data.end_time
        doctor.next_effective_date = today + dt.timedelta(days=1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_staff.py -v -k "update_staff_new_hours or update_staff_requires or update_staff_second_edit"`
Expected: PASS

- [ ] **Step 6: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/staff/schemas.py src/agile_ci_demo/staff/service.py tests/test_staff.py
git commit -m "Let admin change a doctor's working hours, starting the next day"
```

---

### Task 3: Show and edit working hours on the staff detail page

**Files:**
- Modify: `templates/staff/staff_view.html`
- Modify: `static/js/staff_view.js`

**Interfaces:**
- Consumes: `StaffOut.start_time` / `StaffOut.end_time`, `PATCH /api/staff/{staff_id}` accepting `start_time`/`end_time` (Task 2).

- [ ] **Step 1: Add the read-only view field**

In `templates/staff/staff_view.html`, inside the `doctor-information-card` section, add this block after the "Doctor Status" `<div>` (before the closing `</dl>`):

```html
          <div>
            <dt>Working Hours</dt>
            <dd id="view-working-hours">—</dd>
          </div>
```

- [ ] **Step 2: Add the edit form fields**

In `templates/staff/staff_view.html`, inside `#doctor-edit-fields`, add this block after the "Doctor Status" field's closing `</div>` (still inside `#doctor-edit-fields`, before its own closing `</div>`):

```html
            <div class="staff-edit-field">
              <label for="edit-start-time">
                Working Hours Start *
              </label>

              <input
                type="time"
                id="edit-start-time"
                step="1800"
              >

              <div
                id="edit-start-time-error"
                class="staff-field-error"
              ></div>
            </div>

            <div class="staff-edit-field">
              <label for="edit-end-time">
                Working Hours End *
              </label>

              <input
                type="time"
                id="edit-end-time"
                step="1800"
              >

              <div
                id="edit-end-time-error"
                class="staff-field-error"
              ></div>

              <small class="staff-field-hint">
                Changes take effect starting tomorrow, not today.
              </small>
            </div>
```

- [ ] **Step 3: Wire up the JS**

In `static/js/staff_view.js`, add two input refs after the existing `doctorStatusInput`:

```javascript
  const doctorStatusInput = byId(
    "edit-doctor-status"
  );

  const startTimeInput = byId(
    "edit-start-time"
  );

  const endTimeInput = byId(
    "edit-end-time"
  );
```

In `renderStaff`, inside the `if (isDoctor) { ... }` block, add after the `view-doctor-status` call:

```javascript
      setText(
        "view-doctor-status",
        staff.doctor_status
      );

      setText(
        "view-working-hours",
        staff.start_time && staff.end_time
          ? staff.start_time.slice(0, 5) + " - " + staff.end_time.slice(0, 5)
          : null
      );
    }
```

In `populateForm`, add after the `doctorStatusInput.value = ...` assignment:

```javascript
    doctorStatusInput.value =
      currentStaff.doctor_status ||
      "active";

    startTimeInput.value =
      (currentStaff.start_time || "").slice(0, 5);

    endTimeInput.value =
      (currentStaff.end_time || "").slice(0, 5);

    [
      nameInput,
      emailInput,
      licenseInput,
      specialtyInput,
      startTimeInput,
      endTimeInput
    ].forEach(function (input) {
```

(this replaces the existing shorter `[nameInput, emailInput, licenseInput, specialtyInput]` array in that same `forEach` call - the rest of that block is unchanged.)

In `validateForm`, inside the `if (currentStaff.role === "doctor") { ... }` block, add after the `specialtyInput` validation (before the block's closing `}`):

```javascript
      if (!specialtyInput.value) {
        isValid = showFieldError(
          specialtyInput,
          "Please select a specialty."
        );
      } else {
        showFieldValid(
          specialtyInput
        );
      }

      if (!startTimeInput.value) {
        isValid = showFieldError(
          startTimeInput,
          "Please choose a start time."
        );
      } else {
        showFieldValid(startTimeInput);
      }

      if (!endTimeInput.value) {
        isValid = showFieldError(
          endTimeInput,
          "Please choose an end time."
        );
      } else if (
        startTimeInput.value &&
        endTimeInput.value <= startTimeInput.value
      ) {
        isValid = showFieldError(
          endTimeInput,
          "End time must be after the start time."
        );
      } else {
        showFieldValid(endTimeInput);
      }
    }
```

In the submit handler, change the initial `payload` object:

```javascript
      const payload = {
        full_name: nameInput.value,
        email: emailInput.value,
        is_active:
          activeInput.value === "true",
        license_number: null,
        specialty: null,
        doctor_status: null,
        start_time: null,
        end_time: null
      };
```

And add to the `if (currentStaff.role === "doctor") { ... }` block right after it:

```javascript
      if (
        currentStaff.role === "doctor"
      ) {
        payload.license_number =
          licenseInput.value;

        payload.specialty =
          specialtyInput.value;

        payload.doctor_status =
          doctorStatusInput.value;

        payload.start_time =
          startTimeInput.value;

        payload.end_time =
          endTimeInput.value;
      }
```

- [ ] **Step 4: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass (this task touches no Python, so this just confirms nothing else broke).

- [ ] **Step 5: Manual browser check**

Start the dev server, log in as admin, open a doctor's detail page (`/staff/{staff_id}`), click Edit. Confirm: the working-hours fields are pre-filled with the doctor's current hours (09:00/17:00 for a fresh doctor), changing them and saving succeeds, the page's "Working Hours" display still shows the *old* hours right after saving (since the change only takes effect tomorrow), and the hint text under the end-time field is visible. Also confirm a non-doctor staff member's edit form does not show any working-hours fields at all.

- [ ] **Step 6: Commit**

```bash
git add templates/staff/staff_view.html static/js/staff_view.js
git commit -m "Show and let admin edit a doctor's working hours on their staff page"
```

---

### Task 4: Appointment booking and the slot grid use each doctor's own hours

**Files:**
- Modify: `src/agile_ci_demo/appointments/service.py`
- Modify: `src/agile_ci_demo/appointments/router.py`
- Test: `tests/test_appointments.py`

**Interfaces:**
- Consumes: `get_doctor_hours(profile, date)` (Task 1), `PATCH /api/staff/{staff_id}` with `start_time`/`end_time` (Task 2).

- [ ] **Step 1: Write the failing tests**

In `tests/test_appointments.py`, add an admin-login helper (mirrors the existing `_login_as_doctor` in this same file):

```python
def _login_as_admin(client: TestClient) -> None:
    response = client.post(
        "/api/staff",
        json={
            "full_name": "Admin User",
            "email": "admin@example.com",
            "role": "admin",
        },
    )
    assert response.status_code == 201, response.json()

    from agile_ci_demo.core.email import get_outbox

    body = get_outbox()[-1].body
    match = re.search(r"temporary password is: (\S+)", body)
    assert match is not None
    client.post("/api/auth/login", json={"email": "admin@example.com", "password": match.group(1)})
```

Then add:

```python
def test_get_slots_respects_a_doctors_custom_hours(client: TestClient) -> None:
    """
    Scenario: A doctor has non-default working hours
      Given admin has changed a doctor's hours to 10:00-16:00, effective tomorrow
      When I GET /api/appointments/slots for that doctor for tomorrow
      Then the slot grid runs from 10:00 to 16:00, not the old 09:00-17:00
    """
    doctor_id = _register_doctor(client)
    _login_as_admin(client)

    client.patch(
        f"/api/staff/{doctor_id}",
        json={
            "full_name": "Dr. Alan Chua",
            "email": "alan.chua@example.com",
            "is_active": True,
            "license_number": "MMC-12345",
            "specialty": "General Medicine",
            "doctor_status": "active",
            "start_time": "10:00",
            "end_time": "16:00",
        },
    )

    r = client.get("/api/appointments/slots", params={"doctor_id": doctor_id, "date": TOMORROW})
    assert r.status_code == 200
    body = r.json()
    assert len(body["slots"]) == 12  # (16:00 - 10:00) / 30 minutes
    assert body["slots"][0]["start_time"] == "10:00:00"
    assert body["slots"][-1]["start_time"] == "15:30:00"


def test_booking_outside_a_doctors_custom_hours_is_rejected(client: TestClient) -> None:
    """A booking request for a time the doctor no longer works must fail, even
    though it would have been valid under the old 09:00-17:00 default - this is
    the real enforcement boundary, not just the slot grid's display."""
    doctor_id = _register_doctor(client)
    patient_id = _register_patient(client)
    _login_as_admin(client)

    client.patch(
        f"/api/staff/{doctor_id}",
        json={
            "full_name": "Dr. Alan Chua",
            "email": "alan.chua@example.com",
            "is_active": True,
            "license_number": "MMC-12345",
            "specialty": "General Medicine",
            "doctor_status": "active",
            "start_time": "10:00",
            "end_time": "16:00",
        },
    )

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, start_time="09:00"),
    )
    assert r.status_code == 422


def test_booking_within_a_doctors_custom_hours_succeeds(client: TestClient) -> None:
    doctor_id = _register_doctor(client)
    patient_id = _register_patient(client)
    _login_as_admin(client)

    client.patch(
        f"/api/staff/{doctor_id}",
        json={
            "full_name": "Dr. Alan Chua",
            "email": "alan.chua@example.com",
            "is_active": True,
            "license_number": "MMC-12345",
            "specialty": "General Medicine",
            "doctor_status": "active",
            "start_time": "10:00",
            "end_time": "16:00",
        },
    )

    r = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, start_time="11:00"),
    )
    assert r.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_appointments.py -v -k "custom_hours"`
Expected: FAIL - all three still use the global 09:00-17:00 constants today, so the slot grid test sees 16 slots instead of 12, and both booking tests get the opposite of what they expect (09:00 succeeds when it should be rejected; 11:00's behavior doesn't yet depend on the doctor's own hours at all).

- [ ] **Step 3: Rewire get_available_slots and booking validation**

In `src/agile_ci_demo/appointments/service.py`, change the import line:

```python
from agile_ci_demo.staff.service import get_staff_by_staff_id
```

to:

```python
from agile_ci_demo.staff.models import Staff, get_doctor_hours
from agile_ci_demo.staff.service import get_staff_by_staff_id
```

Delete these two lines entirely:

```python
CLINIC_OPEN = dt.time(9, 0)
CLINIC_CLOSE = dt.time(17, 0)
```

(leave `SLOT_MINUTES = 30` in place - it's still a global constant, unchanged by this story.)

Change `_validate_slot`'s signature and body:

```python
def _validate_slot(
    appointment_date: dt.date,
    start_time: dt.time,
    end_time: dt.time,
    doctor_open: dt.time,
    doctor_close: dt.time,
) -> None:
    now = dt.datetime.now()
    if appointment_date < now.date():
        raise InvalidSlotError("Appointment date cannot be in the past")

    if appointment_date == now.date() and start_time < now.time():
        raise InvalidSlotError("Appointment time cannot be in the past")

    if start_time < doctor_open or end_time > doctor_close:
        raise InvalidSlotError(
            f"Appointments must be between {doctor_open.strftime('%H:%M')} "
            f"and {doctor_close.strftime('%H:%M')}"
        )

    minutes_since_open = (
        dt.datetime.combine(appointment_date, start_time)
        - dt.datetime.combine(appointment_date, doctor_open)
    ).total_seconds() / 60
    if minutes_since_open % SLOT_MINUTES != 0:
        raise InvalidSlotError(f"Appointment start time must align to {SLOT_MINUTES}-minute slots")
```

In `create_appointment`, change the two lines that build `end_time` and call `_validate_slot`:

```python
    end_time = add_minutes(data.start_time, SLOT_MINUTES)
    _validate_slot(data.appointment_date, data.start_time, end_time)
```

to:

```python
    doctor_open, doctor_close = get_doctor_hours(doctor.doctor_profile, data.appointment_date)
    end_time = add_minutes(data.start_time, SLOT_MINUTES)
    _validate_slot(data.appointment_date, data.start_time, end_time, doctor_open, doctor_close)
```

Change `get_available_slots`'s signature and body:

```python
def get_available_slots(
    db: Session, doctor: Staff, schedule_date: dt.date
) -> list[tuple[dt.time, dt.time, bool]]:
    """Compute the full working-hours slot grid for a doctor on a date, marking each
    slot as available or not. A slot is unavailable if it is already scheduled
    (cancelled appointments free the slot back up) or already in the past today."""
    if schedule_date < dt.date.today():
        raise PastDateError("Cannot view available slots for a date before today")

    doctor_open, doctor_close = get_doctor_hours(doctor.doctor_profile, schedule_date)

    booked_starts = set(
        db.execute(
            select(Appointment.start_time).where(
                Appointment.doctor_id == doctor.id,
                Appointment.appointment_date == schedule_date,
                Appointment.status == "scheduled",
            )
        )
        .scalars()
        .all()
    )

    now = dt.datetime.now()
    is_today = schedule_date == now.date()

    slots = []
    current = doctor_open
    while current < doctor_close:
        end = add_minutes(current, SLOT_MINUTES)
        is_past = is_today and current < now.time()
        available = current not in booked_starts and not is_past
        slots.append((current, end, available))
        current = end
    return slots
```

- [ ] **Step 4: Update the one caller of get_available_slots**

In `src/agile_ci_demo/appointments/router.py`, find `get_slots` (the `GET /api/appointments/slots` handler) and change:

```python
        slots = get_available_slots(db, doctor.id, schedule_date)
```

to:

```python
        slots = get_available_slots(db, doctor, schedule_date)
```

(`doctor` is already the loaded `Staff` object at this point in the function - this is a one-line change, nothing else in that handler moves.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_appointments.py -v -k "custom_hours"`
Expected: PASS

- [ ] **Step 6: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass. In particular, confirm every pre-existing test in `tests/test_appointments.py` that asserted the old 09:00-17:00 default (e.g. `test_get_slots_full_grid_when_nothing_booked`) still passes unchanged - it should, since Task 1's default for a freshly-registered doctor is still 09:00-17:00.

- [ ] **Step 7: Manual verification of the migration**

If you have a real, pre-existing `clinic.db` file from before this plan (not the test suite's in-memory databases), start the app against it and confirm it starts without error and that `sqlite3 clinic.db "select start_time, end_time from doctor_profiles"` shows `09:00:00`/`17:00:00` for every existing doctor row. This exercises the Task 1 migration path that the automated test suite can't reach.

- [ ] **Step 8: Commit**

```bash
git add src/agile_ci_demo/appointments/service.py src/agile_ci_demo/appointments/router.py tests/test_appointments.py
git commit -m "Make appointment booking and the slot picker follow each doctor's own hours"
```

---

## Self-Review Notes

- **Spec coverage:** data model + resolution function (Task 1), admin-only editing with collapse-then-queue (Task 2), UI (Task 3), slot-grid and booking-validation rewiring (Task 4), migration (Task 1, verified manually in Task 4). All design sections are covered.
- **Placeholder scan:** no TBDs; every step has complete, runnable code.
- **Type consistency:** `get_doctor_hours(profile: DoctorProfile, date: dt.date) -> tuple[dt.time, dt.time]` is defined once in Task 1 and used with the same signature in Task 2 (`Staff.start_time`/`end_time` properties), and Task 4 (`_validate_slot`, `get_available_slots`). `StaffUpdate.start_time`/`end_time` and `StaffOut.start_time`/`end_time` (both `dt.time | None`) are defined once in Task 2 and consumed as-is by Task 3's JS (which reads them as ISO time strings, e.g. `"09:00:00"`, over JSON - no type mismatch, since that's how every other `dt.time` field in this codebase already round-trips through the API).
- **Known accepted trade-off (carried over from the spec):** only one change can be queued per doctor at a time; a second edit before the first queued change takes effect simply replaces it. This is deliberate, not a gap - the spec's "Out of scope" section covers this and multi-day-of-week hours.
