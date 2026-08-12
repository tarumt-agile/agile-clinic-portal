# Doctor Schedule Calendar View + Dashboard Stats — Design

## Context

Doctors and front-desk staff currently browse appointments through a custom-built list UI:
- **Doctor's own "My Schedule"** ([doctor_viewSchedule.html](../../../templates/appointments/doctor_viewSchedule.html)): an "Upcoming Dates" list (dates with a count badge) that, on click, swaps to a day-detail table with a cancel-appointment action.
- **Receptionist's "Doctor Schedule"** ([receptionist_viewDoctorSchedule.html](../../../templates/appointments/receptionist_viewDoctorSchedule.html)): a doctor-picker dropdown plus a single read-only table for "today" only (no date navigation at all today).

This spec adds a **second, alternate view mode** — a real calendar (month/week/day/list toggle, using the FullCalendar library) — that the user can switch to and from, without touching the existing list behavior. It also adds a small stats row ("dashboard") to the doctor's own page, based on a reference screenshot the user provided.

**Scope:** UI/UX addition + a backward-compatible API extension. No change to appointment booking, cancellation business rules, or existing route behavior — the existing single-date query and its behavior are preserved untouched; new capability is additive.

## What's Being Added

### 1. List / Calendar toggle (both pages)

A two-button toggle (e.g. "List" / "Calendar") near the top of the page content, below the header.

- **List mode**: exactly what exists today — completely unchanged markup, JS, and behavior.
- **Calendar mode**: a FullCalendar embed with its own built-in month/week/day/list toolbar (matching the reference screenshot's `month | week | day | list` buttons, prev/next arrows, and a "today" button).
- The chosen top-level mode (List vs Calendar) is remembered per page via `localStorage`, so it persists across visits. FullCalendar's own last-used internal view (month/week/day/list) is remembered the same way.

### 2. Stat cards (doctor's own "My Schedule" page only)

Four `.stat-card` tiles (reusing the component from the page-content-polish pass), above the List/Calendar toggle:

| Card | Definition |
|---|---|
| Total Appointments | All of this doctor's non-cancelled appointments, all-time |
| Today's Appointments | Scheduled for today |
| Future Appointments | Scheduled for a date after today |
| Completed | Past appointments with a linked consultation note whose status is `"completed"` |

Not added to the receptionist's page (per explicit scoping decision — it reads as a personal summary for the doctor, not something meaningful when browsing an arbitrary doctor's schedule from the front desk).

### 3. Calendar interaction

- Clicking an appointment event in the doctor's own calendar reuses the **existing cancel-appointment modal** (already present in `doctor_viewSchedule.html`) — same population logic and same `PATCH /api/appointments/{reference_number}/cancel` call already used by the day-detail table's cancel button, just triggered from a different entry point.
- The receptionist's page has no cancel action today (read-only table); its calendar view stays read-only too — clicking an event has no special behavior beyond FullCalendar's default (showing the event's title).
- Cancelled appointments still appear in the calendar (consistent with the existing day-detail table, which already shows cancelled appointments so staff can see their status) but rendered in a muted color with a "(Cancelled)" suffix, rather than the normal indigo.

## Backend Changes

Both existing endpoints gain an **optional** date-range mode, fully backward-compatible — omitting the new params preserves today's exact single-date behavior:

```
GET /api/appointments/schedule
  Existing: ?date=YYYY-MM-DD (default: today) -> single day, unchanged
  New:      ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD -> appointments across the range

GET /api/appointments/schedule/by-doctor
  Existing: ?doctor_id=...&date=YYYY-MM-DD (default: today) -> single day, unchanged
  New:      ?doctor_id=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD -> range
```

Both continue returning the same `DoctorSchedule` envelope shape (`doctor_id`, `doctor_name`, `appointments: [...]`) — for a range query, `appointments` simply spans every date in `[start_date, end_date]` instead of one date. FullCalendar calls this endpoint every time its visible range changes (new month, new week, etc.), passing the range it's currently displaying.

One new endpoint for the stat cards:

```
GET /api/appointments/schedule/stats
  Auth: require_role(DOCTOR) - the logged-in doctor
  Returns: { total: int, today: int, future: int, completed: int }
```

## Frontend Changes

- **FullCalendar** loaded via CDN (`https://cdn.jsdelivr.net/npm/fullcalendar@7.0.2/index.global.min.js`), the same no-build-step pattern already used for Bootstrap. The "global" bundle includes month/week/day/list views built in — no separate plugin scripts needed.
- Each appointment maps to a FullCalendar event: title showing time + patient name + reason, colored by status (indigo for scheduled, muted gray for cancelled), using FullCalendar's `events` callback (fetches from the range endpoints above whenever the visible range changes).
- Two small additions to `static/js/doctor-schedule.js` and `static/js/receptionist-view-doctor-schedule.js` (not a rewrite) — a toggle handler and a FullCalendar initializer — the existing list-view code paths are untouched.

## Out of Scope

- No changes to booking, slot availability, or cancellation business rules.
- No new roles or permissions — same `require_role(DOCTOR)` / front-desk access as today.
- Receptionist's page does not get stat cards or a cancel action in calendar mode (matches its current read-only list behavior).
- Week/day views reuse whatever range the endpoint returns; no separate "week stats" or "day stats" — only the 4 top-level cards described above.

## Testing

- Existing `pytest` suite must stay green; the range-query extension is additive and must not change the single-`date` code path's behavior (regression-test this explicitly).
- New tests: range query returns the correct appointments for a multi-day span; the stats endpoint returns correct counts for a seeded scenario (today/future/past+completed/cancelled mix).
- Manual verification: toggle between List/Calendar on both pages, confirm FullCalendar's month/week/day/list buttons work, confirm cancel-from-calendar on the doctor's page, confirm the stat cards' numbers match a known seeded dataset.
