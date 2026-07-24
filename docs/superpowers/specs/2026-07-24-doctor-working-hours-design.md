# Doctor Working Hours Editor - Design

## Goal

Let an admin set each doctor's own working hours (currently every doctor shares one
hardcoded clinic-wide range), and have appointment booking and the available-slots
grid respect each doctor's individual hours. A change to a doctor's hours only takes
effect starting the day after it's saved - it never retroactively changes today.

## Background

`src/agile_ci_demo/appointments/service.py` currently defines:

```python
CLINIC_OPEN = dt.time(9, 0)
CLINIC_CLOSE = dt.time(17, 0)
SLOT_MINUTES = 30
```

Every doctor's bookable slots and booking validation use these two constants
uniformly. There is no working-hours field anywhere on `DoctorProfile` today. This
story replaces the clinic-wide constant with a per-doctor value. `SLOT_MINUTES`
(the 30-minute slot granularity) stays a global constant - it is not part of this
story.

## Data model

Two new nullable columns on `DoctorProfile`, backfilled for every existing doctor to
`09:00`-`17:00` (today's constant) so nothing changes until an admin actually edits a
doctor's hours:

- `start_time: Time` - the hours currently in effect (used for today and any date
  without a newer change queued).
- `end_time: Time` - same.

Three more columns represent a single queued future change (nullable - most doctors
will have no pending change most of the time):

- `next_start_time: Time | None`
- `next_end_time: Time | None`
- `next_effective_date: Date | None` - the date from which `next_start_time`/
  `next_end_time` take over.

Only one change can be queued at a time. Saving a new edit always sets
`next_effective_date` to tomorrow's date (relative to when the edit is saved) and
overwrites whatever was queued before - see "Editing" below for what happens if a
previously-queued change has already taken effect.

### Resolution function

One function is the single source of truth for "what are this doctor's hours on date
D":

```python
def get_doctor_hours(profile: DoctorProfile, date: dt.date) -> tuple[dt.time, dt.time]:
    if profile.next_effective_date is not None and date >= profile.next_effective_date:
        return profile.next_start_time, profile.next_end_time
    return profile.start_time, profile.end_time
```

Every place that needs a doctor's hours - the available-slots grid, booking
validation, and the admin edit form's pre-filled values - calls this function. Nothing
reads `start_time`/`end_time` directly for date-specific logic.

### Saving an edit (collapse-then-queue)

When admin submits new hours for a doctor:

1. If a change is already queued (`next_effective_date is not None`) and that date is
   today or earlier (i.e. it already took effect), first collapse it: copy
   `next_start_time`/`next_end_time` into `start_time`/`end_time`. This keeps
   `start_time`/`end_time` an accurate record of "hours in effect right now" between
   edits, for anything that ever needs to display or query the record directly.
2. Set `next_start_time`/`next_end_time` to the submitted values and
   `next_effective_date` to tomorrow's date.

Worked example: Monday, admin sets hours to 10:00-18:00 (queued for Tuesday).
Tuesday, admin changes their mind and sets 09:00-16:00. At the moment of the Tuesday
edit, step 1 sees the Monday-queued 10:00-18:00 already took effect (its date,
Tuesday, is today), so it collapses into `start_time`/`end_time`; step 2 then queues
09:00-16:00 for Wednesday. Result: Monday used 09:00-17:00 (the original default),
Tuesday used 10:00-18:00, Wednesday onward uses 09:00-16:00 - each edit only ever
changes the day after it was made, never the day it was made on.

### Validation

- `start_time < end_time`.
- Both values must fall on a 30-minute boundary (matching `SLOT_MINUTES`), the same
  rule already enforced on appointment bookings today.

### Existing bookings are never touched

If a hours change (effective tomorrow or later) would leave an already-booked
appointment outside the new range, that appointment is left exactly as it is - no
cancellation, no validation blocking the hours change. Only future slot generation
and future booking attempts respect the new range. This matches how the system
already treats a booked appointment as fixed once made.

## Editing UI

No new page or endpoint. The existing staff detail page (`/staff/{staff_id}`) already
has a doctor-only fields section in its edit form (specialty, license number, etc.,
shown only when the staff member is a doctor). Two more fields go in that same
section: "Working hours start" and "Working hours end", pre-filled with
`get_doctor_hours(profile, today)` (i.e. today's effective hours, correctly
accounting for a queued change that already took effect but hasn't been collapsed
into `start_time`/`end_time` yet).

The existing `PATCH /api/staff/{staff_id}` endpoint, `StaffUpdate` schema, and
`StaffOut` schema all gain two more optional fields (`start_time`, `end_time`),
following the exact pattern already used for the other doctor-only fields on those
same schemas. Submitting the form runs through the "saving an edit" logic above.

Only admin can reach this page's edit form for a doctor's fields (existing
`require_role(Role.ADMIN)` gate on the staff detail page, unchanged).

## Slot-availability rewiring

Two call sites in `src/agile_ci_demo/appointments/service.py` change from the global
`CLINIC_OPEN`/`CLINIC_CLOSE` constants to `get_doctor_hours(doctor.doctor_profile,
date)`:

- `get_available_slots` - walks from the doctor's own start to end for the requested
  date instead of the clinic-wide range.
- `_validate_slot` (called from `create_appointment`) - this is the actual
  enforcement boundary, since a booking could be POSTed directly and bypass the slot
  picker UI entirely. `create_appointment` already loads the doctor (and therefore
  `doctor.doctor_profile`) before calling `_validate_slot`, so this is a
  straightforward parameter change, not a new lookup.

`CLINIC_OPEN` and `CLINIC_CLOSE` are removed entirely once both call sites are
switched over.

## Database migration

Following the existing pattern in `src/agile_ci_demo/core/database.py`'s
`migrate_sqlite_database()`: add the five new columns to `doctor_profiles` via
`ALTER TABLE` if they don't already exist, then backfill `start_time = '09:00'`,
`end_time = '17:00'` for any row where they're still null. `next_start_time`,
`next_end_time`, and `next_effective_date` are left null (no doctor starts with a
queued change).

## Testing

- `get_doctor_hours` resolution: no queued change, queued change not yet effective,
  queued change effective today, queued change effective on a past date (still
  applies - "today or later" per the function's `>=` comparison).
- Collapse-then-queue: editing once (no prior queue), editing again before the first
  queued change takes effect (queue is simply replaced), editing again after the
  first queued change has taken effect (collapses first, matching the worked
  example above).
- `get_available_slots` for a doctor with non-default hours, and for a date on either
  side of a queued change's effective date.
- `create_appointment` rejects a booking outside the doctor's hours for the
  appointment's date, using the correct (current vs. queued) hours for that date.
- Existing appointment untouched after an hours change that would exclude it.
- Validation: `start_time >= end_time` rejected; a time off the 30-minute boundary
  rejected.
- Staff detail page: working-hours fields only shown/editable for doctor role;
  pre-filled with today's effective hours; non-admin roles cannot reach the edit form
  (existing gate, regression-covered already).

## Out of scope

- Per-day-of-week hours or marking specific days as non-working days - the system has
  no day-of-week concept today, and this story keeps a single hours range applied to
  every day.
- Blocking an hours change because it would leave a future (not-yet-occurred) booking
  outside the new range - out of scope per the "existing bookings are never touched"
  decision above; this applies to future bookings the same as past ones.
- A doctor editing their own hours - admin-only for this story.
