# Doctor Schedule Calendar View + Dashboard Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a List/Calendar toggle (FullCalendar-powered) to both doctor-schedule pages, plus 4 dashboard stat cards on the doctor's own page, without changing any existing booking/cancellation business rule or touching the existing list view's behavior.

**Architecture:** Backward-compatible API extension (existing single-`date` endpoints gain optional `start_date`/`end_date` range mode; one new `/schedule/stats` endpoint) + a new shared frontend module (`static/js/schedule-calendar.js`) that wraps FullCalendar (loaded via CDN, no build step) and the List/Calendar toggle, used by both `doctor-schedule.js` and `receptionist-view-doctor-schedule.js`. The existing date-list/day-detail UI is wrapped in one container and left otherwise untouched.

**Tech Stack:** FastAPI + SQLAlchemy + Jinja2, FullCalendar 7.0.2 (CDN), vanilla JS, pytest + FastAPI TestClient.

## Global Constraints

- No change to booking, slot-availability, or cancellation business rules.
- The existing single-`date` behavior of `/api/appointments/schedule` and `/api/appointments/schedule/by-doctor` must be preserved byte-for-byte when `start_date`/`end_date` are omitted.
- No new roles/permissions — same `require_role(Role.DOCTOR)` / front-desk access as today.
- pytest must be green after every task.
- FullCalendar version pinned to `6.1.19` via `https://cdn.jsdelivr.net/npm/fullcalendar@6.1.19/index.global.min.js`. (Originally written against `7.0.2`, which looked real via a jsDelivr package search but 404s in practice — v7 apparently dropped the `index.global.min.js` bundle. Caught and corrected during Task 5's manual verification; `6.1.19` was confirmed to return 200 with real `Calendar`-containing JS before switching. No separate CSS file needed — FullCalendar 6's global bundle injects its own styles via JS.)

---

## File Structure

- `src/agile_ci_demo/appointments/schemas.py` — extend `DoctorSchedule` with optional `start_date`/`end_date`; add `DoctorScheduleStats`.
- `src/agile_ci_demo/appointments/service.py` — add `get_doctor_schedule_range` and `get_doctor_schedule_stats`.
- `src/agile_ci_demo/appointments/router.py` — extend `/schedule` and `/schedule/by-doctor` with optional range params; add `/schedule/stats`.
- `tests/test_appointments.py` — new tests for the range query and the stats endpoint.
- `static/js/schedule-calendar.js` — new shared module: FullCalendar init + List/Calendar toggle, used by both pages.
- `templates/appointments/doctor_viewSchedule.html`, `static/js/doctor-schedule.js` — stat cards, toggle markup, calendar wiring, cancel-from-calendar.
- `templates/appointments/receptionist_viewDoctorSchedule.html`, `static/js/receptionist-view-doctor-schedule.js` — toggle markup, calendar wiring.
- `tests/test_base_layout.py` — markup-contract tests for the new toggle/stat-card elements (matches this repo's existing convention of asserting on rendered HTML rather than a JS test framework, since none exists here).

---

### Task 1: Backend — range query + stats endpoint

**Files:**
- Modify: `src/agile_ci_demo/appointments/schemas.py`
- Modify: `src/agile_ci_demo/appointments/service.py`
- Modify: `src/agile_ci_demo/appointments/router.py`
- Test: `tests/test_appointments.py`

**Interfaces:**
- Produces: `get_doctor_schedule_range(db, doctor_id, start_date, end_date) -> list[Appointment]`, `get_doctor_schedule_stats(db, doctor_id) -> dict[str, int]` (keys `total`/`today`/`future`/`completed`), `DoctorScheduleStats` schema, and the extended `DoctorSchedule` schema (`start_date`/`end_date` optional fields) — consumed by Tasks 3-4's frontend code via the JSON response shape.
- Consumes: `Appointment.status` can be `"scheduled"`, `"cancelled"`, or `"completed"` (confirmed via `consultations/service.py:end_consultation`, which flips a `"scheduled"` appointment to `"completed"` when its linked consultation note is ended) — the stats query filters directly on this field, no join needed.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_appointments.py` (near the other `/schedule` tests):

```python
def test_schedule_range_returns_appointments_across_multiple_days(client: TestClient) -> None:
    """?start_date=&end_date= returns appointments spanning the whole range, not
    just one day - the calendar view needs a whole visible month/week at once."""
    patient_id = _register_patient(client)
    doctor_id = _register_and_login_doctor(client)
    day_after_tomorrow = (dt.date.today() + dt.timedelta(days=2)).isoformat()

    client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, appointment_date=TOMORROW),
    )
    client.post(
        "/api/appointments",
        json=valid_appointment_payload(
            patient_id, doctor_id, appointment_date=day_after_tomorrow, start_time="11:00"
        ),
    )

    r = client.get(f"/api/appointments/schedule?start_date={TOMORROW}&end_date={day_after_tomorrow}")
    assert r.status_code == 200
    body = r.json()
    assert body["start_date"] == TOMORROW
    assert body["end_date"] == day_after_tomorrow
    assert body["schedule_date"] is None
    dates = {a["appointment_date"] for a in body["appointments"]}
    assert dates == {TOMORROW, day_after_tomorrow}


def test_schedule_without_range_params_is_unchanged(client: TestClient) -> None:
    """Omitting start_date/end_date must behave exactly as before - single date,
    schedule_date populated, no range fields."""
    patient_id = _register_patient(client)
    doctor_id = _register_and_login_doctor(client)
    client.post("/api/appointments", json=valid_appointment_payload(patient_id, doctor_id))

    r = client.get(f"/api/appointments/schedule?date={TOMORROW}")
    assert r.status_code == 200
    body = r.json()
    assert body["schedule_date"] == TOMORROW
    assert body["start_date"] is None
    assert body["end_date"] is None
    assert len(body["appointments"]) == 1


def test_schedule_by_doctor_range_returns_appointments_across_multiple_days(
    client: TestClient,
) -> None:
    patient_id = _register_patient(client)
    doctor_id = _register_doctor(client)
    day_after_tomorrow = (dt.date.today() + dt.timedelta(days=2)).isoformat()

    client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, appointment_date=TOMORROW),
    )
    client.post(
        "/api/appointments",
        json=valid_appointment_payload(
            patient_id, doctor_id, appointment_date=day_after_tomorrow, start_time="11:00"
        ),
    )

    r = client.get(
        f"/api/appointments/schedule/by-doctor?doctor_id={doctor_id}"
        f"&start_date={TOMORROW}&end_date={day_after_tomorrow}"
    )
    assert r.status_code == 200
    body = r.json()
    dates = {a["appointment_date"] for a in body["appointments"]}
    assert dates == {TOMORROW, day_after_tomorrow}


def test_schedule_stats_counts_scheduled_future_and_completed_separately(
    client: TestClient,
) -> None:
    """
    Scenario: The dashboard stat cards reflect scheduled, future, cancelled,
    and completed appointments correctly
      Given a doctor with a future appointment, a cancelled appointment, and a
        completed appointment (status flips to "completed" when its linked
        consultation is ended)
      When I GET /api/appointments/schedule/stats
      Then future/completed/total reflect exactly those buckets, and the
        cancelled appointment counts toward none of them

    Note: deliberately avoids booking a real "today" appointment, since the
    doctor's working-hours slot validation would make that test's pass/fail
    depend on what time of day the suite happens to run (the existing TOMORROW
    constant in this file exists for the same reason) - the "today" bucket's
    query logic is simple enough (status == scheduled AND date == today) that
    exercising future/completed/cancelled/total here is sufficient coverage.
    """
    patient_id = _register_patient(client)
    doctor_id = _register_and_login_doctor(client)
    day_after_tomorrow = (dt.date.today() + dt.timedelta(days=2)).isoformat()

    future_ref = client.post(
        "/api/appointments",
        json=valid_appointment_payload(patient_id, doctor_id, appointment_date=TOMORROW),
    ).json()["reference_number"]

    cancelled_ref = client.post(
        "/api/appointments",
        json=valid_appointment_payload(
            patient_id, doctor_id, appointment_date=TOMORROW, start_time="11:00"
        ),
    ).json()["reference_number"]
    client.patch(
        f"/api/appointments/{cancelled_ref}/cancel",
        json={"cancellation_reason": "Patient rescheduled"},
    )

    to_complete_ref = client.post(
        "/api/appointments",
        json=valid_appointment_payload(
            patient_id, doctor_id, appointment_date=day_after_tomorrow, start_time="09:00"
        ),
    ).json()["reference_number"]
    record = client.post(
        "/api/consultations",
        json={
            "patient_id": patient_id,
            "notes": "Follow-up visit.",
            "diagnoses": [{"icd10_code": "J00", "description": "Acute nasopharyngitis"}],
            "appointment_reference": to_complete_ref,
        },
    ).json()
    client.patch(f"/api/consultations/{record['record_id']}/end")

    r = client.get("/api/appointments/schedule/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["future"] == 1  # only future_ref is still scheduled + in the future
    assert body["completed"] == 1  # only to_complete_ref
    assert body["total"] == 2  # future_ref + to_complete_ref; cancelled_ref excluded
    assert future_ref  # keeps the variable referenced for readability of the scenario
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_appointments.py::test_schedule_range_returns_appointments_across_multiple_days tests/test_appointments.py::test_schedule_without_range_params_is_unchanged tests/test_appointments.py::test_schedule_by_doctor_range_returns_appointments_across_multiple_days tests/test_appointments.py::test_schedule_stats_counts_scheduled_future_and_completed_separately -v`
Expected: FAIL (404 on `/schedule/stats`, and 422/missing-field errors on the range params, since none of this exists yet).

- [ ] **Step 3: Extend the `DoctorSchedule` schema and add `DoctorScheduleStats`**

In `src/agile_ci_demo/appointments/schemas.py`, replace:

```python
class DoctorSchedule(BaseModel):
    """A doctor's appointments for a single day, ordered by start time ascending."""

    doctor_id: str
    doctor_name: str
    schedule_date: dt.date
    appointments: list[AppointmentOut]
```

with:

```python
class DoctorSchedule(BaseModel):
    """A doctor's appointments for a single day (schedule_date set, start_date/
    end_date left None), or for a date range instead (start_date/end_date set,
    schedule_date left None) - the calendar view uses the range form to fetch
    a whole visible month/week in one call."""

    doctor_id: str
    doctor_name: str
    schedule_date: dt.date | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
    appointments: list[AppointmentOut]
```

Append to the end of the file:

```python


class DoctorScheduleStats(BaseModel):
    """Summary counts for the doctor dashboard stat cards."""

    total: int
    today: int
    future: int
    completed: int
```

- [ ] **Step 4: Add the two new service functions**

In `src/agile_ci_demo/appointments/service.py`, append after `get_doctor_schedule_dates` (before `get_patient_appointments`):

```python
def get_doctor_schedule_range(
    db: Session, doctor_id: int, start_date: dt.date, end_date: dt.date
) -> list[Appointment]:
    """Return a doctor's appointments across a date range (inclusive), ordered by
    date then start time ascending. Unlike get_doctor_schedule, past dates are
    allowed here - the calendar view needs to browse previous months too."""
    return list(
        db.execute(
            select(Appointment)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date >= start_date,
                Appointment.appointment_date <= end_date,
            )
            .order_by(Appointment.appointment_date, Appointment.start_time)
        )
        .scalars()
        .all()
    )


def get_doctor_schedule_stats(db: Session, doctor_id: int) -> dict[str, int]:
    """Summary counts for the doctor dashboard: total non-cancelled appointments
    (status "scheduled" or "completed"), today's, future (after today), and
    completed. Status flips from "scheduled" to "completed" when the linked
    consultation is ended - see consultations.service.end_consultation."""
    today = dt.date.today()

    total = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(["scheduled", "completed"]),
        )
    ).scalar_one()

    today_count = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "scheduled",
            Appointment.appointment_date == today,
        )
    ).scalar_one()

    future_count = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "scheduled",
            Appointment.appointment_date > today,
        )
    ).scalar_one()

    completed_count = db.execute(
        select(func.count())
        .select_from(Appointment)
        .where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == "completed",
        )
    ).scalar_one()

    return {
        "total": total,
        "today": today_count,
        "future": future_count,
        "completed": completed_count,
    }
```

- [ ] **Step 5: Wire the router — extend `/schedule` and `/schedule/by-doctor`, add `/schedule/stats`**

In `src/agile_ci_demo/appointments/router.py`, update the imports. Replace:

```python
from agile_ci_demo.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    DoctorSchedule,
    DoctorScheduleDates,
    DoctorSlots,
    PatientAppointments,
    ScheduleDateSummary,
    SlotInfo,
)
from agile_ci_demo.appointments.service import (
    AlreadyCancelledError,
    AppointmentNotFoundError,
    DoctorNotFoundError,
    InvalidSlotError,
    PastDateError,
    PatientNotFoundError,
    SlotUnavailableError,
    cancel_appointment,
    create_appointment,
    get_appointment_by_reference,
    get_available_slots,
    get_doctor_schedule,
    get_doctor_schedule_dates,
    get_patient_appointments,
)
```

with:

```python
from agile_ci_demo.appointments.schemas import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentOut,
    DoctorSchedule,
    DoctorScheduleDates,
    DoctorScheduleStats,
    DoctorSlots,
    PatientAppointments,
    ScheduleDateSummary,
    SlotInfo,
)
from agile_ci_demo.appointments.service import (
    AlreadyCancelledError,
    AppointmentNotFoundError,
    DoctorNotFoundError,
    InvalidSlotError,
    PastDateError,
    PatientNotFoundError,
    SlotUnavailableError,
    cancel_appointment,
    create_appointment,
    get_appointment_by_reference,
    get_available_slots,
    get_doctor_schedule,
    get_doctor_schedule_dates,
    get_doctor_schedule_range,
    get_doctor_schedule_stats,
    get_patient_appointments,
)
```

Replace the `get_my_schedule` function:

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

with:

```python
@api_router.get("/schedule", response_model=DoctorSchedule)
def get_my_schedule(
    schedule_date: dt.date | None = Query(default=None, alias="date"),
    start_date: dt.date | None = Query(default=None),
    end_date: dt.date | None = Query(default=None),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    """The logged-in doctor's appointments for a given date (defaults to today),
    or for a date range when start_date/end_date are both provided instead -
    used by the calendar view to fetch a whole visible month/week at once."""
    if start_date is not None and end_date is not None:
        appointments = get_doctor_schedule_range(db, doctor.id, start_date, end_date)
        return DoctorSchedule(
            doctor_id=doctor.staff_id or "",
            doctor_name=doctor.full_name,
            start_date=start_date,
            end_date=end_date,
            appointments=[_serialize(a) for a in appointments],
        )

    resolved_date = schedule_date or dt.date.today()
    try:
        appointments = get_doctor_schedule(db, doctor.id, resolved_date)
    except PastDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return DoctorSchedule(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        schedule_date=resolved_date,
        appointments=[_serialize(a) for a in appointments],
    )


@api_router.get("/schedule/stats", response_model=DoctorScheduleStats)
def get_my_schedule_stats(
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
    db: Session = Depends(get_db),
) -> DoctorScheduleStats:
    """Summary counts for the doctor dashboard stat cards: total, today's,
    future, and completed appointments."""
    stats = get_doctor_schedule_stats(db, doctor.id)
    return DoctorScheduleStats(**stats)
```

Replace the `get_schedule_for_doctor` function:

```python
@api_router.get("/schedule/by-doctor", response_model=DoctorSchedule)
def get_schedule_for_doctor(
    doctor_id: str = Query(..., description="Doctor's public staff_id, e.g. S00001"),
    schedule_date: dt.date = Query(default_factory=dt.date.today, alias="date"),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    """A specific doctor's appointments for a given date (defaults to today), for
    front-desk staff looking up any doctor's schedule - unlike /schedule, which is
    always the current doctor's own."""
    doctor = get_staff_by_staff_id(db, doctor_id)
    if doctor is None or doctor.role != Role.DOCTOR.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No doctor found with staff_id '{doctor_id}'",
        )

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

with:

```python
@api_router.get("/schedule/by-doctor", response_model=DoctorSchedule)
def get_schedule_for_doctor(
    doctor_id: str = Query(..., description="Doctor's public staff_id, e.g. S00001"),
    schedule_date: dt.date | None = Query(default=None, alias="date"),
    start_date: dt.date | None = Query(default=None),
    end_date: dt.date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> DoctorSchedule:
    """A specific doctor's appointments for a given date (defaults to today), or
    for a date range when start_date/end_date are both provided instead - for
    front-desk staff looking up any doctor's schedule (unlike /schedule, which
    is always the current doctor's own)."""
    doctor = get_staff_by_staff_id(db, doctor_id)
    if doctor is None or doctor.role != Role.DOCTOR.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No doctor found with staff_id '{doctor_id}'",
        )

    if start_date is not None and end_date is not None:
        appointments = get_doctor_schedule_range(db, doctor.id, start_date, end_date)
        return DoctorSchedule(
            doctor_id=doctor.staff_id or "",
            doctor_name=doctor.full_name,
            start_date=start_date,
            end_date=end_date,
            appointments=[_serialize(a) for a in appointments],
        )

    resolved_date = schedule_date or dt.date.today()
    try:
        appointments = get_doctor_schedule(db, doctor.id, resolved_date)
    except PastDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return DoctorSchedule(
        doctor_id=doctor.staff_id or "",
        doctor_name=doctor.full_name,
        schedule_date=resolved_date,
        appointments=[_serialize(a) for a in appointments],
    )
```

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `python -m pytest tests/test_appointments.py::test_schedule_range_returns_appointments_across_multiple_days tests/test_appointments.py::test_schedule_without_range_params_is_unchanged tests/test_appointments.py::test_schedule_by_doctor_range_returns_appointments_across_multiple_days tests/test_appointments.py::test_schedule_stats_counts_scheduled_future_and_completed_separately -v`
Expected: PASS

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: All PASS (this task changes no existing behavior — only additive optional params and one new endpoint)

- [ ] **Step 8: Commit**

```bash
git add src/agile_ci_demo/appointments/schemas.py src/agile_ci_demo/appointments/service.py src/agile_ci_demo/appointments/router.py tests/test_appointments.py
git commit -m "feat: add date-range schedule query and dashboard stats endpoint"
```

---

### Task 2: Shared frontend calendar module

**Files:**
- Create: `static/js/schedule-calendar.js`

**Interfaces:**
- Produces: `window.initScheduleViewToggle(config) -> { refresh: () => void }`, consumed by Tasks 3 and 4.
  - `config.viewModeStorageKey: string` — localStorage key for List vs Calendar preference
  - `config.listViewId, config.calendarViewId: string` — container element ids to show/hide
  - `config.listButtonId, config.calendarButtonId: string` — toggle button ids
  - `config.calendar: { containerId, calendarViewStorageKey, eventsUrl(startDate, endDate) -> string, onEventClick?(appointment) }`
- Consumes: global `FullCalendar` (loaded via CDN `<script>` before this file) and `AppointmentOut`-shaped JSON objects (fields: `reference_number`, `patient_id`, `patient_name`, `appointment_date`, `start_time`, `end_time`, `reason`, `status`) from the range endpoints built in Task 1.

- [ ] **Step 1: Create the shared module**

Create `static/js/schedule-calendar.js`:

```javascript
(function () {
  "use strict";

  const STATUS_COLORS = {
    scheduled: "#4f46e5",
    completed: "#059669",
    cancelled: "#94a3b8",
  };

  function initScheduleCalendar(config) {
    const el = document.getElementById(config.containerId);
    if (!el || !window.FullCalendar) return null;

    const calendar = new FullCalendar.Calendar(el, {
      initialView: localStorage.getItem(config.calendarViewStorageKey) || "dayGridMonth",
      headerToolbar: {
        left: "prev,next today",
        center: "title",
        right: "dayGridMonth,timeGridWeek,timeGridDay,listWeek",
      },
      height: "auto",
      events: function (info, successCallback, failureCallback) {
        const startDate = info.startStr.slice(0, 10);
        const endDate = info.endStr.slice(0, 10);
        fetch(config.eventsUrl(startDate, endDate))
          .then((response) => {
            if (!response.ok) throw new Error("Request failed");
            return response.json();
          })
          .then((data) => {
            const events = data.appointments.map((a) => {
              const color = STATUS_COLORS[a.status] || "#64748b";
              const suffix = a.status === "cancelled" ? " (Cancelled)" : "";
              return {
                id: a.reference_number,
                title: a.start_time.slice(0, 5) + " " + a.patient_name + suffix,
                start: a.appointment_date + "T" + a.start_time,
                end: a.appointment_date + "T" + a.end_time,
                backgroundColor: color,
                borderColor: color,
                extendedProps: a,
              };
            });
            successCallback(events);
          })
          .catch(failureCallback);
      },
      eventClick: function (clickInfo) {
        if (config.onEventClick) config.onEventClick(clickInfo.event.extendedProps);
      },
      viewDidMount: function (arg) {
        localStorage.setItem(config.calendarViewStorageKey, arg.view.type);
      },
    });

    calendar.render();
    return calendar;
  }

  function initScheduleViewToggle(config) {
    const listViewEl = document.getElementById(config.listViewId);
    const calendarViewEl = document.getElementById(config.calendarViewId);
    const listButton = document.getElementById(config.listButtonId);
    const calendarButton = document.getElementById(config.calendarButtonId);
    let calendarInstance = null;

    function showList() {
      listViewEl.classList.remove("d-none");
      calendarViewEl.classList.add("d-none");
      listButton.classList.add("active");
      calendarButton.classList.remove("active");
      localStorage.setItem(config.viewModeStorageKey, "list");
    }

    function showCalendar() {
      listViewEl.classList.add("d-none");
      calendarViewEl.classList.remove("d-none");
      calendarButton.classList.add("active");
      listButton.classList.remove("active");
      localStorage.setItem(config.viewModeStorageKey, "calendar");
      if (!calendarInstance) {
        calendarInstance = initScheduleCalendar(config.calendar);
      } else {
        calendarInstance.updateSize();
      }
    }

    listButton.addEventListener("click", showList);
    calendarButton.addEventListener("click", showCalendar);

    if (localStorage.getItem(config.viewModeStorageKey) === "calendar") {
      showCalendar();
    } else {
      showList();
    }

    return {
      refresh: function () {
        if (calendarInstance) calendarInstance.refetchEvents();
      },
    };
  }

  window.initScheduleViewToggle = initScheduleViewToggle;
})();
```

- [ ] **Step 2: Commit**

This file has no automated test (pure client-side JS, no JS test framework in this repo) — it's exercised by Tasks 3-4's manual verification.

```bash
git add static/js/schedule-calendar.js
git commit -m "feat: add shared FullCalendar wrapper and List/Calendar toggle module"
```

---

### Task 3: Doctor's own "My Schedule" page — stat cards + toggle + calendar

**Files:**
- Modify: `templates/appointments/doctor_viewSchedule.html`
- Modify: `static/js/doctor-schedule.js`
- Test: `tests/test_base_layout.py`

**Interfaces:**
- Consumes: `window.initScheduleViewToggle` from Task 2; `GET /api/appointments/schedule/stats` and the range form of `GET /api/appointments/schedule` from Task 1.
- Produces: `#stat-total`, `#stat-today`, `#stat-future`, `#stat-completed`, `#view-list-btn`, `#view-calendar-btn`, `#list-view`, `#calendar-view`, `#schedule-calendar` element ids — consumed only by this task's own JS and its test.

- [ ] **Step 1: Write the failing markup-contract test**

Add to `tests/test_base_layout.py`:

```python
def test_doctor_schedule_page_has_stat_cards_and_view_toggle(client: TestClient) -> None:
    create_staff_and_login(client, "doctor")

    response = client.get("/appointments/schedule")

    assert response.status_code == 200
    assert 'id="stat-total"' in response.text
    assert 'id="stat-today"' in response.text
    assert 'id="stat-future"' in response.text
    assert 'id="stat-completed"' in response.text
    assert 'id="view-list-btn"' in response.text
    assert 'id="view-calendar-btn"' in response.text
    assert 'id="schedule-calendar"' in response.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_base_layout.py::test_doctor_schedule_page_has_stat_cards_and_view_toggle -v`
Expected: FAIL — none of this markup exists yet.

- [ ] **Step 3: Update the template**

Replace the entire content of `templates/appointments/doctor_viewSchedule.html` with:

```html
{% extends "base.html" %}

{% block title %}My Schedule - Agile Clinic Portal{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
  <h1 class="h3 mb-0" id="schedule-heading">My Schedule</h1>
</div>

<div id="schedule-alert" class="alert alert-danger d-none" role="alert"></div>

<div class="row g-3 mb-4">
  <div class="col-sm-3">
    <div class="stat-card h-100">
      <p class="stat-card-label mb-0">Total Appointments</p>
      <strong id="stat-total" class="stat-card-value">0</strong>
    </div>
  </div>
  <div class="col-sm-3">
    <div class="stat-card h-100">
      <p class="stat-card-label mb-0">Today's Appointments</p>
      <strong id="stat-today" class="stat-card-value">0</strong>
    </div>
  </div>
  <div class="col-sm-3">
    <div class="stat-card h-100">
      <p class="stat-card-label mb-0">Future Appointments</p>
      <strong id="stat-future" class="stat-card-value">0</strong>
    </div>
  </div>
  <div class="col-sm-3">
    <div class="stat-card h-100">
      <p class="stat-card-label mb-0">Completed</p>
      <strong id="stat-completed" class="stat-card-value">0</strong>
    </div>
  </div>
</div>

<div class="btn-group mb-3" role="group" aria-label="Schedule view mode">
  <button type="button" class="btn btn-outline-primary" id="view-list-btn">List</button>
  <button type="button" class="btn btn-outline-primary" id="view-calendar-btn">Calendar</button>
</div>

<div id="list-view">
  <!-- Date list view: every upcoming date with at least one appointment, shown by
       default so a doctor isn't required to filter by date to see what's coming up. -->
  <div id="date-list-view">
    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <span>Upcoming Dates</span>
        <div>
          <label for="jump-to-date" class="visually-hidden">Jump to a specific date</label>
          <input type="date" id="jump-to-date" class="form-control form-control-sm"
                 title="Jump to a specific date">
        </div>
      </div>
      <div class="list-group list-group-flush" id="date-list-body">
        <div class="list-group-item text-center text-muted py-4">Loading...</div>
      </div>
    </div>
  </div>

  <!-- Day detail view: the appointments booked on one specific date, opened by
       clicking a date in the list above (or via "Jump to a specific date"). -->
  <div id="day-detail-view" class="d-none">
    <div class="card">
      <div class="card-header d-flex justify-content-between align-items-center">
        <button type="button" class="btn btn-sm btn-outline-secondary" id="back-to-dates-btn">
          &larr; Back to dates
        </button>
        <span id="day-detail-heading" class="fw-semibold"></span>
        <span></span>
      </div>
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">Time</th>
              <th scope="col">Patient</th>
              <th scope="col">Reason</th>
              <th scope="col">Status</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody id="schedule-table-body">
            <tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<div id="calendar-view" class="d-none">
  <div class="card">
    <div class="card-body">
      <div id="schedule-calendar"></div>
    </div>
  </div>
</div>

<!-- Cancellation dialog, shown when cancelling an appointment -->
<div class="modal fade" id="cancel-modal" tabindex="-1" aria-labelledby="cancel-modal-label" aria-hidden="true">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="cancel-modal-label">Cancel Appointment</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
      </div>
      <form id="cancel-form" novalidate>
        <div class="modal-body">
          <p class="mb-3">
            Cancel the appointment with <strong id="cancel-target-patient"></strong>?
            The slot will be freed for other patients.
          </p>
          <label for="cancel-reason" class="form-label">Reason for cancellation *</label>
          <textarea class="form-control" id="cancel-reason" name="cancellation_reason" rows="2" required minlength="2" maxlength="255"></textarea>
          <div class="invalid-feedback">A cancellation reason is required.</div>
          <div id="cancel-alert" class="alert alert-danger d-none mt-3" role="alert"></div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Keep Appointment</button>
          <button type="submit" class="btn btn-danger" id="confirm-cancel-btn">Cancel Appointment</button>
        </div>
      </form>
    </div>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@7.0.2/index.global.min.js"></script>
<script src="/static/js/schedule-calendar.js"></script>
<script src="/static/js/doctor-schedule.js?v=2"></script>
{% endblock %}
```

- [ ] **Step 4: Update `doctor-schedule.js`**

Replace the entire content of `static/js/doctor-schedule.js` with:

```javascript
(function () {
  "use strict";

  const tableBody = document.getElementById("schedule-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("schedule-heading");
  const dateListView = document.getElementById("date-list-view");
  const dateListBody = document.getElementById("date-list-body");
  const jumpToDateInput = document.getElementById("jump-to-date");
  const dayDetailView = document.getElementById("day-detail-view");
  const dayDetailHeading = document.getElementById("day-detail-heading");
  const backToDatesBtn = document.getElementById("back-to-dates-btn");
  const alertBox = document.getElementById("schedule-alert");

  const statTotal = document.getElementById("stat-total");
  const statToday = document.getElementById("stat-today");
  const statFuture = document.getElementById("stat-future");
  const statCompleted = document.getElementById("stat-completed");

  const cancelModalEl = document.getElementById("cancel-modal");
  const cancelModal = window.bootstrap ? new bootstrap.Modal(cancelModalEl) : null;
  const cancelForm = document.getElementById("cancel-form");
  const cancelReasonInput = document.getElementById("cancel-reason");
  const cancelTargetPatient = document.getElementById("cancel-target-patient");
  const cancelAlert = document.getElementById("cancel-alert");
  const confirmCancelBtn = document.getElementById("confirm-cancel-btn");

  const STATUS_BADGE = {
    scheduled: "text-bg-primary",
    cancelled: "text-bg-secondary",
    completed: "text-bg-success",
  };

  let pendingReferenceNumber = null;
  let currentDate = null;

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  function formatDateLong(dateValue) {
    const [year, month, day] = dateValue.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  }

  function showDateListView() {
    currentDate = null;
    heading.textContent = "My Schedule";
    dayDetailView.classList.add("d-none");
    dateListView.classList.remove("d-none");
    loadDateList();
  }

  function showDayDetailView(dateValue) {
    currentDate = dateValue;
    dateListView.classList.add("d-none");
    dayDetailView.classList.remove("d-none");
    loadSchedule(dateValue);
  }

  async function loadStats() {
    try {
      const response = await fetch("/api/appointments/schedule/stats");
      if (!response.ok) return;
      const body = await response.json();
      statTotal.textContent = body.total;
      statToday.textContent = body.today;
      statFuture.textContent = body.future;
      statCompleted.textContent = body.completed;
    } catch (err) {
      // Stat cards are a summary, not critical path - fail silently and leave
      // the zeros in place rather than blocking the rest of the page.
    }
  }

  async function loadDateList() {
    hideAlert();
    dateListBody.innerHTML =
      '<div class="list-group-item text-center text-muted py-4">Loading...</div>';

    try {
      const response = await fetch("/api/appointments/schedule/dates");
      const body = await response.json();

      if (response.status === 404) {
        dateListBody.innerHTML = "";
        showAlert(body.detail || "No doctor account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      heading.textContent = `${body.doctor_name}'s Schedule`;
      renderDateList(body.dates);
    } catch (err) {
      dateListBody.innerHTML = "";
      showAlert("Unable to load your schedule. Please try again.");
    }
  }

  function renderDateList(dates) {
    if (dates.length === 0) {
      dateListBody.innerHTML =
        '<div class="list-group-item text-center text-muted py-4">' +
        "No upcoming appointments. Use the date field above to check a specific date." +
        "</div>";
      return;
    }

    dateListBody.innerHTML = dates
      .map((d) => {
        const countLabel = d.appointment_count === 1 ? "1 appointment" : `${d.appointment_count} appointments`;
        return `
      <button type="button" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center date-list-item" data-date="${escapeHtml(d.schedule_date)}">
        <span>${escapeHtml(formatDateLong(d.schedule_date))}</span>
        <span class="badge text-bg-primary rounded-pill">${escapeHtml(countLabel)}</span>
      </button>`;
      })
      .join("");

    dateListBody.querySelectorAll(".date-list-item").forEach((btn) => {
      btn.addEventListener("click", () => showDayDetailView(btn.dataset.date));
    });
  }

  async function loadSchedule(dateValue) {
    hideAlert();
    dayDetailHeading.textContent = formatDateLong(dateValue);
    tableBody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch(`/api/appointments/schedule?date=${dateValue}`);
      const body = await response.json();

      if (response.status === 422) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "Please choose today or a future date.");
        return;
      }

      if (response.status === 404) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "No doctor account found.");
        return;
      }

      if (!response.ok) throw new Error("Request failed");

      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="5" class="text-center text-muted py-4">No appointments for this date.</td></tr>';
      return;
    }

    tableBody.innerHTML = appointments
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.status] || "text-bg-light";
        const action =
          a.status === "scheduled"
            ? `<button type="button" class="btn btn-sm btn-outline-danger cancel-btn" data-reference="${escapeHtml(a.reference_number)}" data-patient-name="${escapeHtml(a.patient_name)}">Cancel</button>`
            : "-";
        return `
      <tr>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.patient_name)} (${escapeHtml(a.patient_id)})</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.status)}</span></td>
        <td>${action}</td>
      </tr>`;
      })
      .join("");

    tableBody.querySelectorAll(".cancel-btn").forEach((btn) => {
      btn.addEventListener("click", () => openCancelModal(btn.dataset.reference, btn.dataset.patientName));
    });
  }

  function openCancelModal(referenceNumber, patientName) {
    pendingReferenceNumber = referenceNumber;
    cancelTargetPatient.textContent = patientName;
    cancelReasonInput.value = "";
    cancelForm.classList.remove("was-validated");
    cancelReasonInput.classList.remove("is-invalid");
    cancelAlert.classList.add("d-none");
    if (cancelModal) {
      cancelModal.show();
    } else {
      const reason = window.prompt(`Cancel appointment with ${patientName}? Enter a reason:`);
      if (reason && reason.trim()) submitCancellation(referenceNumber, reason.trim());
    }
  }

  async function handleCancelSubmit(event) {
    event.preventDefault();
    cancelAlert.classList.add("d-none");

    if (!cancelForm.checkValidity()) {
      cancelForm.classList.add("was-validated");
      return;
    }

    await submitCancellation(pendingReferenceNumber, cancelReasonInput.value.trim());
  }

  async function submitCancellation(referenceNumber, reason) {
    confirmCancelBtn.disabled = true;
    try {
      const response = await fetch(
        `/api/appointments/${encodeURIComponent(referenceNumber)}/cancel`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cancellation_reason: reason }),
        }
      );

      if (response.ok) {
        if (cancelModal) cancelModal.hide();
        if (currentDate) loadSchedule(currentDate);
        loadStats();
        if (scheduleView) scheduleView.refresh();
        return;
      }

      const body = await response.json().catch(() => ({}));
      const message = typeof body.detail === "string" ? body.detail : "Unable to cancel this appointment.";
      if (cancelModal) {
        cancelAlert.textContent = message;
        cancelAlert.classList.remove("d-none");
      } else {
        window.alert(message);
      }
    } catch (err) {
      const message = "Unable to reach the server. Please check your connection and try again.";
      if (cancelModal) {
        cancelAlert.textContent = message;
        cancelAlert.classList.remove("d-none");
      } else {
        window.alert(message);
      }
    } finally {
      confirmCancelBtn.disabled = false;
    }
  }

  // Local date, not UTC - toISOString() converts to UTC and can be a day off
  // from the server's dt.date.today() (which uses local time), especially near midnight.
  function todayLocalISODate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const today = todayLocalISODate();
  jumpToDateInput.min = today;

  jumpToDateInput.addEventListener("change", () => {
    if (jumpToDateInput.value) showDayDetailView(jumpToDateInput.value);
  });
  backToDatesBtn.addEventListener("click", () => {
    jumpToDateInput.value = "";
    showDateListView();
  });
  cancelForm.addEventListener("submit", handleCancelSubmit);

  const scheduleView = window.initScheduleViewToggle
    ? window.initScheduleViewToggle({
        viewModeStorageKey: "doctorScheduleViewMode",
        listViewId: "list-view",
        calendarViewId: "calendar-view",
        listButtonId: "view-list-btn",
        calendarButtonId: "view-calendar-btn",
        calendar: {
          containerId: "schedule-calendar",
          calendarViewStorageKey: "doctorScheduleCalendarView",
          eventsUrl: function (startDate, endDate) {
            return `/api/appointments/schedule?start_date=${startDate}&end_date=${endDate}`;
          },
          onEventClick: function (appointment) {
            if (appointment.status === "scheduled") {
              openCancelModal(appointment.reference_number, appointment.patient_name);
            }
          },
        },
      })
    : null;

  loadStats();
  showDateListView();
})();
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `python -m pytest tests/test_base_layout.py::test_doctor_schedule_page_has_stat_cards_and_view_toggle -v`
Expected: PASS

- [ ] **Step 6: Run the appointments and base-layout suites for regressions**

Run: `python -m pytest tests/test_appointments.py tests/test_base_layout.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add templates/appointments/doctor_viewSchedule.html static/js/doctor-schedule.js tests/test_base_layout.py
git commit -m "feat: add dashboard stat cards and calendar view to My Schedule"
```

---

### Task 4: Receptionist's "Doctor Schedule" page — toggle + calendar

**Files:**
- Modify: `templates/appointments/receptionist_viewDoctorSchedule.html`
- Modify: `static/js/receptionist-view-doctor-schedule.js`
- Test: `tests/test_base_layout.py`

**Interfaces:**
- Consumes: `window.initScheduleViewToggle` from Task 2; the range form of `GET /api/appointments/schedule/by-doctor` from Task 1.
- Produces: `#view-list-btn`, `#view-calendar-btn`, `#list-view`, `#calendar-view`, `#schedule-calendar` — same id scheme as Task 3 but scoped to this page's own DOM (no collision, different pages).

- [ ] **Step 1: Write the failing markup-contract test**

Add to `tests/test_base_layout.py`:

```python
def test_receptionist_doctor_schedule_page_has_view_toggle(client: TestClient) -> None:
    create_staff_and_login(client, "receptionist")

    response = client.get("/appointments/doctor-schedule")

    assert response.status_code == 200
    assert 'id="view-list-btn"' in response.text
    assert 'id="view-calendar-btn"' in response.text
    assert 'id="schedule-calendar"' in response.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_base_layout.py::test_receptionist_doctor_schedule_page_has_view_toggle -v`
Expected: FAIL

- [ ] **Step 3: Update the template**

Replace the entire content of `templates/appointments/receptionist_viewDoctorSchedule.html` with:

```html
{% extends "base.html" %}

{% block title %}Doctor Schedule - Agile Clinic Portal{% endblock %}

{% block content %}
<header class="mb-4">
  <p class="text-muted mb-1">Front Desk / Doctor Schedule</p>
  <h1 class="h3 mb-1">Doctor Schedule</h1>
  <p class="text-muted mb-0">View each doctor's appointments for the day.</p>
</header>

<div id="doctor-schedule-alert" class="alert alert-danger d-none" role="alert"></div>

<div class="btn-group mb-3" role="group" aria-label="Schedule view mode">
  <button type="button" class="btn btn-outline-primary" id="view-list-btn">List</button>
  <button type="button" class="btn btn-outline-primary" id="view-calendar-btn">Calendar</button>
</div>

<div id="list-view">
  <div class="card">
    <div class="card-header d-flex justify-content-between align-items-center">
      <span id="doctor-schedule-heading">Today's Appointments</span>
      <div>
        <label for="doctor-filter" class="visually-hidden">Doctor</label>
        <select id="doctor-filter" class="form-select form-select-sm">
          <option value="" selected disabled>Loading doctors...</option>
        </select>
      </div>
    </div>
    <div class="table-responsive">
      <table class="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Patient</th>
            <th scope="col">Reason</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody id="doctor-schedule-table-body">
          <tr><td colspan="4" class="text-center text-muted py-4">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>

<div id="calendar-view" class="d-none">
  <div class="card">
    <div class="card-body">
      <div id="schedule-calendar"></div>
    </div>
  </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@7.0.2/index.global.min.js"></script>
<script src="/static/js/schedule-calendar.js"></script>
<script src="/static/js/receptionist-view-doctor-schedule.js"></script>
{% endblock %}
```

- [ ] **Step 4: Update `receptionist-view-doctor-schedule.js`**

Replace the entire content of `static/js/receptionist-view-doctor-schedule.js` with:

```javascript
(function () {
  "use strict";

  const tableBody = document.getElementById("doctor-schedule-table-body");
  if (!tableBody) return;

  const heading = document.getElementById("doctor-schedule-heading");
  const alertBox = document.getElementById("doctor-schedule-alert");
  const doctorFilter = document.getElementById("doctor-filter");

  const STATUS_BADGE = {
    scheduled: "text-bg-primary",
    cancelled: "text-bg-secondary",
    completed: "text-bg-success",
  };

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
  }

  function showAlert(message) {
    alertBox.textContent = message;
    alertBox.classList.remove("d-none");
  }

  function hideAlert() {
    alertBox.classList.add("d-none");
    alertBox.textContent = "";
  }

  // Local date, not UTC - toISOString() converts to UTC and can be a day off from
  // the server's dt.date.today() (which uses local time), especially near midnight.
  function todayLocalISODate() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  const today = todayLocalISODate();

  async function loadDoctors() {
    try {
      const response = await fetch("/api/staff/doctor");
      if (!response.ok) throw new Error("Request failed");
      const doctors = await response.json();
      const active = doctors.filter((d) => d.status === "active");

      if (active.length === 0) {
        doctorFilter.innerHTML = '<option value="" selected disabled>No doctors available</option>';
        tableBody.innerHTML =
          '<tr><td colspan="4" class="text-center text-muted py-4">No doctors available.</td></tr>';
        return;
      }

      doctorFilter.innerHTML = active
        .map((d) => `<option value="${escapeHtml(d.staff_id)}">${escapeHtml(d.full_name)}</option>`)
        .join("");

      loadSchedule(doctorFilter.value);
      if (scheduleView) scheduleView.refresh();
    } catch (err) {
      doctorFilter.innerHTML = '<option value="" selected disabled>Unable to load doctors</option>';
      tableBody.innerHTML = "";
      showAlert("Unable to load the doctor list. Please try again.");
    }
  }

  async function loadSchedule(doctorId) {
    if (!doctorId) return;
    hideAlert();
    tableBody.innerHTML =
      '<tr><td colspan="4" class="text-center text-muted py-4">Loading...</td></tr>';

    try {
      const response = await fetch(
        `/api/appointments/schedule/by-doctor?doctor_id=${encodeURIComponent(doctorId)}&date=${today}`
      );
      const body = await response.json();

      if (!response.ok) {
        tableBody.innerHTML = "";
        showAlert(body.detail || "Unable to load this doctor's schedule.");
        return;
      }

      heading.textContent = `${body.doctor_name}'s Appointments Today`;
      renderTable(body.appointments);
    } catch (err) {
      tableBody.innerHTML = "";
      showAlert("Unable to load the schedule. Please try again.");
    }
  }

  function renderTable(appointments) {
    if (appointments.length === 0) {
      tableBody.innerHTML =
        '<tr><td colspan="4" class="text-center text-muted py-4">No appointments today.</td></tr>';
      return;
    }

    tableBody.innerHTML = appointments
      .map((a) => {
        const badgeClass = STATUS_BADGE[a.status] || "text-bg-light";
        return `
      <tr>
        <td>${escapeHtml(a.start_time.slice(0, 5))} - ${escapeHtml(a.end_time.slice(0, 5))}</td>
        <td>${escapeHtml(a.patient_name)} (${escapeHtml(a.patient_id)})</td>
        <td>${escapeHtml(a.reason)}</td>
        <td><span class="badge ${badgeClass} text-capitalize">${escapeHtml(a.status)}</span></td>
      </tr>`;
      })
      .join("");
  }

  const scheduleView = window.initScheduleViewToggle
    ? window.initScheduleViewToggle({
        viewModeStorageKey: "receptionistDoctorScheduleViewMode",
        listViewId: "list-view",
        calendarViewId: "calendar-view",
        listButtonId: "view-list-btn",
        calendarButtonId: "view-calendar-btn",
        calendar: {
          containerId: "schedule-calendar",
          calendarViewStorageKey: "receptionistDoctorScheduleCalendarView",
          eventsUrl: function (startDate, endDate) {
            return `/api/appointments/schedule/by-doctor?doctor_id=${encodeURIComponent(doctorFilter.value)}&start_date=${startDate}&end_date=${endDate}`;
          },
        },
      })
    : null;

  doctorFilter.addEventListener("change", () => {
    loadSchedule(doctorFilter.value);
    if (scheduleView) scheduleView.refresh();
  });
  loadDoctors();
})();
```

- [ ] **Step 5: Run the new test to verify it passes**

Run: `python -m pytest tests/test_base_layout.py::test_receptionist_doctor_schedule_page_has_view_toggle -v`
Expected: PASS

- [ ] **Step 6: Run the full test suite for regressions**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add templates/appointments/receptionist_viewDoctorSchedule.html static/js/receptionist-view-doctor-schedule.js tests/test_base_layout.py
git commit -m "feat: add List/Calendar toggle to the receptionist's doctor schedule page"
```

---

### Task 5: Manual cross-role verification

**Files:** none (verification only)

**Interfaces:** none

- [ ] **Step 1: Start the app** (`.claude/launch.json` "api" config, or `uvicorn agile_ci_demo.app:app --reload`)

- [ ] **Step 2: Doctor's own "My Schedule"**

Log in as a doctor with some seeded appointments. Confirm the 4 stat cards show non-zero, sensible numbers. Click "Calendar" — confirm FullCalendar renders, its month/week/day/list toolbar buttons all work, and appointments appear as colored events (indigo = scheduled, gray = cancelled, green = completed if any exist). Click a scheduled event — confirm the existing cancel modal opens and cancelling it updates both the calendar (event disappears/updates on `refetchEvents`) and the stat cards. Click "List" — confirm the original date-list/day-detail UI is completely unchanged.

- [ ] **Step 3: Preference persistence**

While in Calendar mode, reload the page — confirm it reopens in Calendar mode (not List), and reopens on whichever of month/week/day/list was last selected.

- [ ] **Step 4: Receptionist's "Doctor Schedule"**

Log in as a receptionist. Confirm the doctor dropdown still works in both List and Calendar mode, and that switching doctors while in Calendar mode refreshes the calendar's events to the newly selected doctor.

- [ ] **Step 5: Report findings**

Note anything that looks wrong (page/role/interaction + what's off) for a follow-up fix — the structural work is done and tested by this point.

---

## Self-Review Notes

- **Spec coverage:** every item in the design spec maps to a task — List/Calendar toggle on both pages (Tasks 3-4), 4 stat cards on the doctor's own page only (Task 3), backward-compatible API range extension + stats endpoint (Task 1), cancel-from-calendar reusing the existing modal (Task 3), preference persistence via localStorage (Task 2's shared module, exercised in Task 5).
- **Corrected understanding preserved:** the plan implements the corrected architecture (top-level List/Calendar toggle, existing list view untouched, FullCalendar's own toolbar only inside Calendar mode) rather than the earlier "replace entirely" idea that was floated and then corrected during brainstorming.
- **"Completed" status discovery:** the design spec assumed computing "Completed" would need a join against `consultation_notes`. Research during planning found `consultations/service.py:end_consultation` already flips `Appointment.status` to `"completed"` directly — the plan's stats query filters on `Appointment.status` alone, no join, which is simpler than the spec anticipated. Flagging this since it's a deviation from the spec's literal text (in the simplifying direction).
- **Test flakiness avoided:** the stats test deliberately does not book a real "today" appointment (would make pass/fail depend on time-of-day the suite runs, given the existing slot-time-in-the-past validation) — matches this repo's existing `TOMORROW`-only convention for exactly this reason.
- **Type/id consistency:** `#view-list-btn` / `#view-calendar-btn` / `#list-view` / `#calendar-view` / `#schedule-calendar` are the same id scheme on both pages (Tasks 3 and 4) but scoped to separate DOM trees on separate pages, consumed identically by the one shared `schedule-calendar.js` module (Task 2) via config objects rather than hardcoded ids.
