# Manual IC/Passport Entry on Patient Registration - Design

## Goal

Let a receptionist or admin type in a patient's real IC or passport number during registration,
instead of the system auto-generating a fake one. Catch the two realism problems with the current
generator directly: the value typed in must actually be consistent with the patient's stated date
of birth and gender, where the Malaysian IC format defines that relationship.

## Background

`PatientCreate` (`src/agile_ci_demo/patients/schemas.py`) has no `ic_or_passport` field today.
`create_patient` (`src/agile_ci_demo/patients/service.py`) always calls `generate_ic(db,
date_of_birth)`, which derives `YYMMDD` from the date of birth, then fills the next two digits
with a random `0X` and the last four digits randomly - a shape that looks like a Malaysian IC but
carries no real place-of-birth or gender information, since the form never collects the former and
the generator ignores the latter. The registration page currently just tells the user "IC number
is generated automatically from the date of birth after registration" and has no input for it.

Three of the four test files that register patients (`tests/test_appointments.py`,
`tests/test_prescription.py`, `tests/test_records.py`) already include an `ic_or_passport` key in
their patient payloads - currently silently dropped by Pydantic since the field doesn't exist on
`PatientCreate` yet. Only `tests/test_patients.py`'s own helper is missing it. This keeps the test
blast radius small.

## Backend changes

`PatientCreate` gains a required field:

```python
ic_or_passport: str = Field(min_length=1, max_length=30)
```

Two validators enforce the format and the cross-checks against the rest of the payload:

- **Format**: either a Malaysian IC shape (`^\d{6}-\d{2}-\d{4}$`) or a passport shape (starts with
  a letter) - the same distinction already used on the login page's IC/passport field.
- **Cross-checks, IC-shaped input only** (skipped entirely for passport-shaped input, since a
  passport number carries neither a birth date nor a gender digit):
  - The first six digits must equal `date_of_birth` formatted as `YYMMDD`.
  - If `gender` is `male` or `female` (not `other`, which the real-world convention has no answer
    for), the last digit's parity must match: odd = male, even = female.

Both cross-checks live in a `model_validator(mode="after")` on `PatientCreate`, matching the
existing pattern used for doctor-specific cross-field validation on `StaffCreate` in
`src/agile_ci_demo/staff/schemas.py`. This is the authoritative check - it runs regardless of
whether the request came through the form's own JS pre-checks or a direct API call.

`create_patient` stops calling `generate_ic()` and instead uses `data.ic_or_passport` directly.
`generate_ic()` itself is deleted - it becomes dead code with no other callers. Duplicate-IC
handling (`DuplicatePatientError`, raised on the existing unique constraint) is unchanged.

## Frontend changes

The registration page gets a new "IC / Passport number *" field, placed where the "IC number is
generated automatically..." helper text currently sits (that text is removed). The field gets the
same auto-dash formatting already used on the login page and the appointment-booking page's IC
field (digits reformat into `xxxxxx-xx-xxxx` as typed; a value containing a letter is left
untouched, matching the existing passport-safety guard).

Client-side JS mirrors the two server-side cross-checks for instant feedback (no round trip
needed): after both the IC/Passport field and the Date of Birth/Gender fields have a value, a
Malaysian-IC-shaped entry is checked against the selected date of birth and gender, showing a
field-level error message on mismatch - the same "instant, then confirmed server-side" pattern
already used elsewhere in this codebase (e.g. the appointment form's IC format pre-check). The
server-side `model_validator` remains the actual authority; the client check is UX only.

The confirmation modal already displays `patient.ic_or_passport` from the registration response -
no change needed there, since it already reflects whatever was actually stored.

## Testing

- `PatientCreate`/`create_patient`: valid Malaysian IC matching DOB and gender succeeds; valid
  passport-shaped value succeeds regardless of DOB/gender; IC digits not matching DOB rejected;
  IC last-digit parity not matching gender (male/female) rejected; IC last-digit parity check
  skipped when gender is `other`; duplicate IC still rejected (existing behavior, regression
  coverage).
- `tests/test_patients.py`'s `valid_patient_payload` helper gains a matching `ic_or_passport` key
  (the other three test files' helpers already have one that satisfies the new cross-checks, per
  the Background section above - confirm this at implementation time rather than assuming).
- Manual browser check: registering a patient with a mismatched IC/DOB or IC/gender combination
  shows the client-side error before submission; a valid combination succeeds and the confirmation
  modal shows the exact value that was typed in, not a generated one.

## Out of scope

- Any change to how existing patients' already-generated IC values are displayed, edited, or
  migrated - this only changes what happens at the moment of registering a *new* patient. No
  backfill of old auto-generated values.
- Changing the appointment-booking page's IC lookup field or the login page's IC/phone field -
  both already work against whatever `ic_or_passport` value is stored, generated or manual, with
  no assumption about how it got there.
- A separate, more permissive passport-validation format (e.g. checking passport number length or
  structure) - "starts with a letter" is the only passport check, matching the login page's
  existing, deliberately loose rule.
