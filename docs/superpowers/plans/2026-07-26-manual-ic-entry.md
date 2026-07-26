# Manual IC/Passport Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a receptionist or admin type in a patient's real IC or passport number during registration, with the server rejecting a Malaysian-IC-shaped value that doesn't match the patient's stated date of birth or gender.

**Architecture:** `PatientCreate` gains a required `ic_or_passport` field with a `model_validator` doing format checking plus the DOB/gender cross-checks; `create_patient` uses it directly instead of calling the deleted `generate_ic()`. The registration page gets a new input field with the existing auto-dash pattern and a client-side mirror of the cross-checks for instant feedback.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy (SQLite), Jinja2 templates, vanilla JS, pytest.

## Global Constraints

- Commit messages: plain-language, non-technical (this is graded university coursework read by non-technical reviewers).
- Commit directly - never add a `Co-Authored-By` trailer or any AI-attribution line to any commit.
- Keep code as simple as possible: no new libraries, no new endpoints.
- Full check suite (`ruff check . && black --check . && mypy src && pytest --disable-warnings -q`) must pass before every commit.
- `PatientUpdate` must keep `ic_or_passport` optional and `update_patient` must keep ignoring it entirely - IC/passport stays fixed after registration, unchanged from today's behavior. This is not optional: `PatientUpdate` currently inherits directly from `PatientCreate` with no field overrides, so making `ic_or_passport` required on `PatientCreate` without overriding it on `PatientUpdate` would silently break every patient edit (the edit form doesn't collect this field).

---

### Task 1: Backend - accept and validate a real IC/passport at registration

**Files:**
- Modify: `src/agile_ci_demo/patients/schemas.py`
- Modify: `src/agile_ci_demo/patients/service.py`
- Test: `tests/test_patients.py`

**Interfaces:**
- Produces: `PatientCreate.ic_or_passport: str` (required); `PatientUpdate.ic_or_passport: str | None = None` (optional override, always ignored by `update_patient`). Task 2 doesn't consume these directly - it just needs to know the field name (`ic_or_passport`) and that the server enforces the same format/cross-check rules the client-side JS will mirror.

- [ ] **Step 1: Write the failing tests**

In `tests/test_patients.py`, first update `valid_patient_payload` to include a real, consistent IC
(this file's own helper currently has no `ic_or_passport` key at all - the other three test files'
equivalent helpers already have one, which is why they aren't touched by this task):

```python
def valid_patient_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "full_name": "Jane Tan",
        "date_of_birth": "1990-05-20",
        "gender": "female",
        "phone_number": "012-3456789",
        "email": "jane.tan@example.com",
        "ic_or_passport": "900520-10-1234",
        "address": "1 Jalan Testing, Kuala Lumpur",
    }
    payload.update(overrides)
    return payload
```

(`900520-10-1234` is deliberately chosen to already satisfy the new cross-checks this task adds:
`900520` matches `date_of_birth: "1990-05-20"`, and `4` is even, matching `gender: "female"` - so
every existing test using this default payload keeps passing unchanged.)

Then replace the two tests whose entire premise was automatic generation. Find
`test_register_generates_ic_from_date_of_birth`:

```python
def test_register_generates_ic_from_date_of_birth(client: TestClient) -> None:
    """
    Scenario: IC number is generated automatically, not client-supplied
      Given a patient is registered with date_of_birth "1990-05-20"
      Then the generated ic_or_passport starts with "900520-0" and is
        formatted YYMMDD-0X-XXXX
    """
    r = client.post("/api/patients", json=valid_patient_payload(date_of_birth="1990-05-20"))
    assert r.status_code == 201
    ic = r.json()["ic_or_passport"]
    assert re.fullmatch(r"900520-0[1-9]-\d{4}", ic)
```

Replace it with:

```python
def test_register_stores_the_ic_exactly_as_submitted(client: TestClient) -> None:
    """
    Scenario: IC number is typed in by staff, not generated
      Given a patient is registered with a specific IC number
      Then the stored ic_or_passport is exactly that value
    """
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(date_of_birth="1990-05-20", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 201
    assert r.json()["ic_or_passport"] == "900520-10-1234"
```

Find `test_register_generates_unique_ic_for_same_date_of_birth`:

```python
def test_register_generates_unique_ic_for_same_date_of_birth(client: TestClient) -> None:
    """Two patients sharing a date_of_birth must still get distinct IC numbers."""
    r1 = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", date_of_birth="1990-05-20"),
    )
    r2 = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="John Lee", date_of_birth="1990-05-20"),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["ic_or_passport"] != r2.json()["ic_or_passport"]
```

Replace it with:

```python
def test_register_two_patients_sharing_a_date_of_birth_with_different_ics_succeeds(
    client: TestClient,
) -> None:
    """Sharing a date_of_birth is fine as long as the IC numbers themselves differ -
    there's no implicit uniqueness tied to date_of_birth anymore."""
    r1 = client.post(
        "/api/patients",
        json=valid_patient_payload(
            full_name="Jane Tan", date_of_birth="1990-05-20", ic_or_passport="900520-10-1234"
        ),
    )
    r2 = client.post(
        "/api/patients",
        json=valid_patient_payload(
            full_name="John Lee", date_of_birth="1990-05-20", ic_or_passport="900520-10-5678"
        ),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["ic_or_passport"] != r2.json()["ic_or_passport"]


def test_register_with_a_duplicate_ic_returns_409(client: TestClient) -> None:
    """Two different patients cannot share the same IC number - this was already true
    at the database level, but is now much more likely to actually be hit in practice
    since staff type the IC in by hand instead of the system generating a random one."""
    client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Jane Tan", ic_or_passport="900520-10-1234"),
    )
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(full_name="Someone Else", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 409
```

Now add the new tests for the format and cross-check rules:

```python
def test_register_with_a_passport_number_skips_dob_and_gender_checks(client: TestClient) -> None:
    """A passport-shaped value (starts with a letter) has no birth-date or gender digit
    to check against, regardless of what date_of_birth/gender were submitted."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1975-01-01", gender="male", ic_or_passport="A12345678"
        ),
    )
    assert r.status_code == 201
    assert r.json()["ic_or_passport"] == "A12345678"


def test_register_rejects_an_ic_not_matching_date_of_birth(client: TestClient) -> None:
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(date_of_birth="1985-01-01", ic_or_passport="900520-10-1234"),
    )
    assert r.status_code == 422


def test_register_rejects_an_ic_not_matching_male_gender(client: TestClient) -> None:
    """Male requires an odd last digit; 4 is even."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="male", ic_or_passport="900520-10-1234"
        ),
    )
    assert r.status_code == 422


def test_register_rejects_an_ic_not_matching_female_gender(client: TestClient) -> None:
    """Female requires an even last digit; 3 is odd."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="female", ic_or_passport="900520-10-1233"
        ),
    )
    assert r.status_code == 422


def test_register_gender_other_skips_the_last_digit_check(client: TestClient) -> None:
    """Gender "other" has no odd/even convention to check against - any last digit is fine
    as long as the date-of-birth digits still match."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(
            date_of_birth="1990-05-20", gender="other", ic_or_passport="900520-10-1234"
        ),
    )
    assert r.status_code == 201


def test_register_rejects_a_malformed_ic_that_is_neither_ic_nor_passport_shaped(
    client: TestClient,
) -> None:
    """Too few digits, no dashes, or otherwise not matching either recognized shape."""
    r = client.post(
        "/api/patients",
        json=valid_patient_payload(ic_or_passport="12345"),
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_patients.py -v -k "ic_or_passport or duplicate_ic or matching_ or shaped or generates_the_ic or two_patients_sharing"`
Expected: FAIL - `PatientCreate` doesn't have an `ic_or_passport` field yet, so every test above
either 422s for the wrong reason (unexpected field silently dropped, then some other required-ish
behavior doesn't match) or the replaced generation tests fail because `create_patient` still calls
`generate_ic()`.

- [ ] **Step 3: Add the field and validators to PatientCreate, and override it on PatientUpdate**

In `src/agile_ci_demo/patients/schemas.py`, add `ic_or_passport` to `PatientCreate` (right after
`phone_number`, before `email`):

```python
class PatientCreate(BaseModel):
    """Payload for registering a new patient. Mirrors the registration form fields."""

    full_name: str = Field(min_length=2, max_length=120)
    date_of_birth: dt.date
    gender: Gender
    phone_number: str = Field(min_length=7, max_length=20)
    ic_or_passport: str = Field(min_length=1, max_length=30)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)
```

Add this import at the top (`re` is already imported; add `model_validator` to the existing
`pydantic` import line):

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
```

Add the format-and-cross-check validator to `PatientCreate`, after the existing
`blank_address_is_none` validator:

```python
    @model_validator(mode="after")
    def validate_ic_or_passport(self) -> "PatientCreate":
        ic = self.ic_or_passport
        if ic is None:
            return self

        if re.fullmatch(r"\d{6}-\d{2}-\d{4}", ic):
            dob_digits = self.date_of_birth.strftime("%y%m%d")
            if ic[:6] != dob_digits:
                raise ValueError("IC number does not match the date of birth.")

            last_digit = int(ic[-1])
            if self.gender == Gender.MALE and last_digit % 2 == 0:
                raise ValueError("IC number's last digit does not match a male patient.")
            if self.gender == Gender.FEMALE and last_digit % 2 != 0:
                raise ValueError("IC number's last digit does not match a female patient.")
        elif not re.match(r"^[A-Za-z]", ic):
            raise ValueError("Enter a valid IC number (xxxxxx-xx-xxxx) or passport number.")

        return self
```

(The `if ic is None: return self` guard is what makes this validator safe to inherit onto
`PatientUpdate`, where the field becomes optional - see the next change.)

Change `PatientUpdate` to override the field as optional:

```python
class PatientUpdate(PatientCreate):
    """Payload for editing an existing patient. Same shape and validation as PatientCreate -
    every field is re-validated on save, per the "validate every patient field" requirement.
    ic_or_passport is the one exception: it's optional here and always ignored by
    update_patient() - IC/passport is fixed at registration and never changes."""

    ic_or_passport: str | None = None
```

- [ ] **Step 4: Use the submitted IC instead of generating one, and delete generate_ic**

In `src/agile_ci_demo/patients/service.py`, change `create_patient`:

```python
def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Register a new patient and assign it a unique, sequential patient_id (e.g. P00001)."""
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender.value,
        phone_number=data.phone_number,
        email=data.email,
        ic_or_passport=generate_ic(db, data.date_of_birth),
        address=data.address,
    )
```

to:

```python
def create_patient(db: Session, data: PatientCreate) -> Patient:
    """Register a new patient and assign it a unique, sequential patient_id (e.g. P00001)."""
    patient = Patient(
        full_name=data.full_name,
        date_of_birth=data.date_of_birth,
        gender=data.gender.value,
        phone_number=data.phone_number,
        email=data.email,
        ic_or_passport=data.ic_or_passport,
        address=data.address,
    )
```

Delete the `generate_ic` function entirely (search for `def generate_ic`) - it has no other
callers. Also delete the now-unused `_IC_GENERATION_ATTEMPTS = 20` constant and the `import
random` line at the top of the file, if `random` isn't used anywhere else in this file (check
first - it shouldn't be, `generate_ic` was its only user).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_patients.py -v -k "ic_or_passport or duplicate_ic or matching_ or shaped or generates_the_ic or two_patients_sharing"`
Expected: PASS

- [ ] **Step 6: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass. In particular, confirm `test_update_patient_does_not_change_ic` still passes
unchanged - it now sends an `ic_or_passport` value on the PUT request (since it reuses
`valid_patient_payload`, which now always includes one), but `PatientUpdate` accepts it as
optional and `update_patient` never assigns it to the patient row, so the assertion that the IC
stays fixed across the edit should still hold exactly as before.

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/patients/schemas.py src/agile_ci_demo/patients/service.py tests/test_patients.py
git commit -m "Let staff type in a patient's real IC or passport number at registration"
```

---

### Task 2: Frontend - IC/Passport field with auto-dash and instant validation

**Files:**
- Modify: `templates/patients/receptionist_registerPatients.html`
- Modify: `static/js/patient-form.js`
- Modify: `static/js/patients.js`

**Interfaces:**
- Consumes: `POST /api/patients` requiring `ic_or_passport` and enforcing the format/cross-check
  rules (Task 1).

- [ ] **Step 1: Add the field to the registration form**

In `templates/patients/receptionist_registerPatients.html`, change:

```html
        <div class="col-md-4">
          <label for="phone_number" class="form-label">Phone number *</label>
          <input type="tel" class="form-control" id="phone_number" name="phone_number" required
                 placeholder="e.g. 012-3456789" pattern="^\+?\d[\d\s\-]{6,19}$">
          <div class="invalid-feedback">Enter a valid phone number (7-20 digits).</div>
        </div>

        <div class="col-md-4">
          <label for="email" class="form-label">Email</label>
          <input type="email" class="form-control" id="email" name="email" placeholder="optional">
          <div class="invalid-feedback">Enter a valid email address.</div>
        </div>

        <div class="col-md-6">
          <label for="address" class="form-label">Address</label>
          <input type="text" class="form-control" id="address" name="address" placeholder="optional" maxlength="255">
          <div class="form-text">IC number is generated automatically from the date of birth after registration.</div>
        </div>
```

to:

```html
        <div class="col-md-4">
          <label for="phone_number" class="form-label">Phone number *</label>
          <input type="tel" class="form-control" id="phone_number" name="phone_number" required
                 placeholder="e.g. 012-3456789" pattern="^\+?\d[\d\s\-]{6,19}$">
          <div class="invalid-feedback">Enter a valid phone number (7-20 digits).</div>
        </div>

        <div class="col-md-4">
          <label for="ic_or_passport" class="form-label">IC / Passport number *</label>
          <input type="text" class="form-control" id="ic_or_passport" name="ic_or_passport" required
                 placeholder="e.g. xxxxxx-xx-xxxx">
          <div id="ic-or-passport-error" class="invalid-feedback">Enter a valid IC number matching the date of birth and gender, or a passport number.</div>
        </div>

        <div class="col-md-4">
          <label for="email" class="form-label">Email</label>
          <input type="email" class="form-control" id="email" name="email" placeholder="optional">
          <div class="invalid-feedback">Enter a valid email address.</div>
        </div>

        <div class="col-md-6">
          <label for="address" class="form-label">Address</label>
          <input type="text" class="form-control" id="address" name="address" placeholder="optional" maxlength="255">
        </div>
```

(The old "IC number is generated automatically..." helper text under Address is removed entirely -
there's nothing automatic left to explain.)

- [ ] **Step 2: Add auto-dash as a shared PatientForm utility**

In `static/js/patient-form.js`, add this function inside the `window.PatientForm` IIFE, after
`setFieldError` (this is the same auto-dash logic already used on the login page and the
appointment-booking page - same letter-guard behavior, so a passport number typed in never gets
corrupted):

```javascript
  // Reformats digits-only input into dash-separated groups as the user types,
  // e.g. groupSizes [6, 2, 4] turns "900520101234" into "900520-10-1234". Skips
  // reformatting if the field has any letters in it - this field also accepts
  // passport numbers, which aren't digits-only and shouldn't be touched.
  function autoDash(input, groupSizes) {
    input.addEventListener("input", () => {
      if (/[a-zA-Z]/.test(input.value)) {
        input.value = input.value.replace(/-/g, "");
        return;
      }
      const digits = input.value.replace(/\D/g, "");
      const groups = [];
      let start = 0;
      for (const size of groupSizes) {
        if (start >= digits.length) break;
        groups.push(digits.slice(start, start + size));
        start += size;
      }
      input.value = groups.join("-");
    });
  }
```

Add `autoDash` to the returned object at the bottom of the file:

```javascript
  return {
    showAlert,
    hideAlert,
    clearFieldErrors,
    setFieldError,
    applyValidationErrors,
    collectPayload,
    fillForm,
    autoDash,
  };
```

Change `collectPayload` to include the new field (matching how `email`/`address` are already
conditionally included - the edit form has no `ic_or_passport` input, so `data.get(...)` returns
`null` there and the key is simply omitted, which is fine since `PatientUpdate` doesn't require
it):

```javascript
  function collectPayload(form) {
    const data = new FormData(form);
    const payload = {
      full_name: data.get("full_name")?.trim(),
      date_of_birth: data.get("date_of_birth"),
      gender: data.get("gender"),
      phone_number: data.get("phone_number")?.trim(),
    };
    const email = data.get("email")?.trim();
    const address = data.get("address")?.trim();
    const icOrPassport = data.get("ic_or_passport")?.trim();
    if (email) payload.email = email;
    if (address) payload.address = address;
    if (icOrPassport) payload.ic_or_passport = icOrPassport;
    return payload;
  }
```

- [ ] **Step 3: Wire up auto-dash and instant cross-check validation on the registration page**

In `static/js/patients.js`, add this after the existing `const { showAlert, ... } =
window.PatientForm;` line:

```javascript
  const dobInput = document.getElementById("date_of_birth");
  const genderInput = document.getElementById("gender");
  const icInput = document.getElementById("ic_or_passport");

  const IC_PATTERN = /^\d{6}-\d{2}-\d{4}$/;

  function checkIcConsistency() {
    const ic = icInput.value.trim();
    icInput.classList.remove("is-invalid");
    if (!ic || !IC_PATTERN.test(ic)) return; // not IC-shaped (empty or a passport) - nothing to check

    const dob = dobInput.value; // "YYYY-MM-DD"
    if (dob) {
      const dobDigits = dob.slice(2, 4) + dob.slice(5, 7) + dob.slice(8, 10);
      if (ic.slice(0, 6) !== dobDigits) {
        icInput.classList.add("is-invalid");
        document.getElementById("ic-or-passport-error").textContent =
          "This IC number does not match the date of birth.";
        return;
      }
    }

    const gender = genderInput.value;
    const lastDigit = Number(ic.slice(-1));
    if (gender === "male" && lastDigit % 2 === 0) {
      icInput.classList.add("is-invalid");
      document.getElementById("ic-or-passport-error").textContent =
        "This IC number's last digit does not match a male patient.";
    } else if (gender === "female" && lastDigit % 2 !== 0) {
      icInput.classList.add("is-invalid");
      document.getElementById("ic-or-passport-error").textContent =
        "This IC number's last digit does not match a female patient.";
    }
  }

  window.PatientForm.autoDash(icInput, [6, 2, 4]);
  icInput.addEventListener("input", checkIcConsistency);
  dobInput.addEventListener("change", checkIcConsistency);
  genderInput.addEventListener("change", checkIcConsistency);
```

(`autoDash` already fires on `input` and reformats the value in place; `checkIcConsistency` is
registered as a *second* `input` listener on the same field, so it always reads the
already-reformatted value.)

- [ ] **Step 4: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass (this task touches no Python, so this just confirms nothing else broke).

- [ ] **Step 5: Manual browser check**

Start the dev server, log in as receptionist, open `/patients/register`. Confirm: typing digits
into the IC/Passport field auto-formats into `xxxxxx-xx-xxxx`; typing a value starting with a
letter is left alone (no dashes inserted); filling in a date of birth and an IC whose first six
digits don't match shows the field-level "does not match the date of birth" error immediately;
fixing the IC (or the date of birth) clears the error; selecting Male/Female with a
non-matching last digit shows the gender-mismatch error; selecting "Other" never shows a
gender-mismatch error regardless of the last digit; a fully consistent submission succeeds and the
confirmation modal shows the exact IC that was typed in.

- [ ] **Step 6: Commit**

```bash
git add templates/patients/receptionist_registerPatients.html static/js/patient-form.js static/js/patients.js
git commit -m "Add an IC or passport field to patient registration with instant validation"
```

---

## Self-Review Notes

- **Spec coverage:** required field + format validation + DOB/gender cross-checks + PatientUpdate
  compatibility (Task 1), form field + auto-dash + client-side mirror of the cross-checks (Task
  2). All design sections are covered, including the spec's explicit "Out of scope" items (nothing
  in this plan touches the edit flow, the booking/login IC fields, or adds passport-format
  structure checks beyond "starts with a letter").
- **Placeholder scan:** no TBDs; every step has complete, runnable code.
- **Type consistency:** `ic_or_passport` is `str` (required) on `PatientCreate` and `str | None =
  None` (optional) on `PatientUpdate`, consumed the same way by the shared `validate_ic_or_passport`
  model_validator (guarded by an early `None` check) in both cases. The JS field name (`name="ic_or_passport"`,
  Task 2) matches the schema field name (Task 1) exactly, and `collectPayload`'s conditional-include
  pattern for `ic_or_passport` matches the existing pattern already used for `email`/`address` in
  the same function.
- **Cross-cutting risk caught during planning:** `PatientUpdate` currently inherits directly from
  `PatientCreate` with zero field overrides. Making `ic_or_passport` required on `PatientCreate`
  without the `PatientUpdate` override in Task 1 Step 3 would have silently broken every patient
  edit (422 "field required" on every `PUT /api/patients/{id}`, since the edit form has no IC
  input to source that value from). The plan's Global Constraints section calls this out
  explicitly so it isn't missed during implementation.
