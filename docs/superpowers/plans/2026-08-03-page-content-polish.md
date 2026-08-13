# Page Content Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Modern Slate design language into page content (stat cards, forms, buttons, lists), fix content centering and add a logout confirmation, without changing any route, permission, or business logic.

**Architecture:** Nearly everything is new CSS added to `static/css/app.css` (global, cascades automatically), plus small, scoped markup changes: swapping `.card` → `.stat-card` classes in Pharmacy's three summary tiles, wrapping existing form fields in `.form-section` groups in the two appointment-booking templates and Pharmacy's two modals, and adding a logout confirmation modal to `base.html`. No JavaScript rendering logic changes — the JS files involved (`appointment-form.js`, `doctor-schedule.js`, `pharmacy-management.js`) already attach the CSS hooks this plan needs (`.slot-btn`, `.date-list-item`) or select elements by ID rather than by class, so they're untouched by the class/wrapper changes.

**Scope adjustment from the design spec:** the spec described applying Staff List's mobile table→card JS pattern to Patients List, Doctor Schedule, and Pharmacy's tables. On inspection, that pattern requires each page's JS to render a second, parallel card-based markup from the same data — a much larger, riskier lift than the rest of this "CSS polish" pass, and out of proportion with it. This plan keeps those three tables on Bootstrap's existing `.table-responsive` horizontal-scroll behavior (already present on all of them) rather than building three new mobile-card renderers. Flagging this now rather than silently under-delivering against the spec.

**Tech Stack:** FastAPI + Jinja2 templates, Bootstrap 5.3.3 (CDN), vanilla CSS/JS, pytest + FastAPI TestClient.

## Global Constraints

- No route, permission, or business-logic changes — CSS and markup only, except the logout flow, which gains a confirmation step (a deliberate, spec'd behavior change) but keeps the same underlying `DELETE /api/auth/session` call.
- Reuse the existing design tokens in `static/css/app.css` (`--clinic-accent`, `--clinic-accent-soft`, `--clinic-border`, `--clinic-content-bg`, `--clinic-table-header-text`, `--clinic-text`) — no new colors.
- pytest must be green after every task.

---

## File Structure

- `static/css/app.css` — new component CSS: content centering, `.stat-card`, `.form-section`, `.slot-btn` pill styling, `.date-list-item` hover treatment.
- `templates/base.html` — logout confirmation modal + updated inline script.
- `tests/test_base_layout.py` — new test for the logout confirmation markup contract.
- `templates/pharmacy/pharmacy_management.html` — stat-card class swap + form-section wrappers in its two modals.
- `templates/appointments/receptionist_createAppointment.html`, `templates/appointments/patient_bookAppointment.html` — form-section wrappers.

No other templates need changes — Patients List, Patient Registration, Login/Reset Password, Staff List/Create/View, and Doctor Schedule's date list all pick up the CSS-only fixes (centering, `.slot-btn` n/a, `.date-list-item` already present in `doctor-schedule.js`'s generated markup) with zero markup edits.

---

### Task 1: Global CSS — centering, stat cards, form sections, pill buttons, date-list styling

**Files:**
- Modify: `static/css/app.css`
- Test: manual — verified visually in Task 5; no pytest assertion depends on these rules

**Interfaces:**
- Produces: `.stat-card` / `.stat-card-label` / `.stat-card-value`, `.form-section` / `.form-section-title`, and styling for the already-existing `.slot-btn` (from `static/js/appointment-form.js:178-179`) and `.date-list-item` (from `static/js/doctor-schedule.js:111`) classes — consumed by Tasks 2-4.

- [ ] **Step 1: Fix content centering**

In `static/css/app.css`, replace:

```css
.app-content {
  flex: 1;
  max-width: 1200px;
  padding: 1.5rem;
}
```

with:

```css
.app-content {
  flex: 1;
  max-width: 1200px;
  margin-inline: auto;
  padding: 1.5rem;
}
```

- [ ] **Step 2: Append the new component CSS**

Append to the end of `static/css/app.css`:

```css

/* ===== Stat cards (single-number summary tiles) ===== */
.stat-card {
  padding: 1.1rem 1.25rem;
  background-color: #fff;
  border: 1px solid var(--clinic-border);
  border-radius: 0.65rem;
}

.stat-card-label {
  margin: 0 0 0.35rem;
  color: var(--clinic-table-header-text);
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.stat-card-value {
  display: block;
  font-size: 1.9rem;
  font-weight: 700;
  color: var(--clinic-text);
}

/* ===== Form sections (grouped field labels inside forms) ===== */
.form-section {
  margin-bottom: 1.5rem;
}

.form-section:last-of-type {
  margin-bottom: 0;
}

.form-section-title {
  margin: 0 0 0.9rem;
  color: var(--clinic-table-header-text);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* ===== Time-slot picker (Book Appointment) ===== */
.slot-btn {
  min-width: 4.5rem;
  border-radius: 999px;
}

/* ===== Doctor Schedule date list ===== */
.date-list-item {
  border-left: 3px solid transparent;
}

.date-list-item:hover {
  background-color: var(--clinic-content-bg);
  border-left-color: var(--clinic-accent-soft);
}
```

- [ ] **Step 3: Run a quick regression check**

Run: `python -m pytest tests/test_app.py tests/test_pharmacy.py tests/test_appointments.py -v`
Expected: All PASS (CSS-only change, no markup touched yet)

- [ ] **Step 4: Commit**

```bash
git add static/css/app.css
git commit -m "style: add stat-card, form-section, and remaining Modern Slate component styles"
```

---

### Task 2: Logout confirmation modal

**Files:**
- Modify: `templates/base.html:99-127` (add modal markup, update inline script)
- Test: `tests/test_base_layout.py` (add one test)

**Interfaces:**
- Consumes: none new (uses Bootstrap's existing modal JS, already loaded via `bootstrap.bundle.min.js`)
- Produces: `#logout-confirm-modal` / `#confirm-logout-btn` markup contract, consumed by Task 2's own test only.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_base_layout.py`:

```python
def test_logout_link_requires_confirmation(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert 'id="logout-confirm-modal"' in response.text
    assert 'id="confirm-logout-btn"' in response.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_base_layout.py::test_logout_link_requires_confirmation -v`
Expected: FAIL — the modal markup doesn't exist yet.

- [ ] **Step 3: Add the confirmation modal to `base.html`**

In `templates/base.html`, replace:

```html
  {% else %}
    </div>
  </div>
  {% endif %}

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
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

with:

```html
  {% else %}
    </div>
  </div>
  {% endif %}

  {% if authed %}
  <div class="modal fade" id="logout-confirm-modal" tabindex="-1" aria-labelledby="logout-confirm-modal-label" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="logout-confirm-modal-label">Log Out</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <p class="mb-0">Are you sure you want to log out?</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
          <button type="button" class="btn btn-primary" id="confirm-logout-btn">Log Out</button>
        </div>
      </div>
    </div>
  </div>
  {% endif %}

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    const logoutLink = document.getElementById("logout-link");
    const logoutConfirmModalEl = document.getElementById("logout-confirm-modal");
    const logoutConfirmModal =
      logoutConfirmModalEl && window.bootstrap ? new bootstrap.Modal(logoutConfirmModalEl) : null;
    const confirmLogoutBtn = document.getElementById("confirm-logout-btn");

    async function performLogout() {
      await fetch("/api/auth/session", { method: "DELETE" });
      localStorage.removeItem("clinicSessionToken");
      window.location.href = "/auth/login";
    }

    if (logoutLink) {
      logoutLink.addEventListener("click", (event) => {
        event.preventDefault();
        if (logoutConfirmModal) {
          logoutConfirmModal.show();
        } else {
          performLogout();
        }
      });
    }

    if (confirmLogoutBtn) {
      confirmLogoutBtn.addEventListener("click", performLogout);
    }
  </script>
```

- [ ] **Step 4: Run the test again to verify it passes**

Run: `python -m pytest tests/test_base_layout.py::test_logout_link_requires_confirmation -v`
Expected: PASS

- [ ] **Step 5: Run the full base-layout suite to check for regressions**

Run: `python -m pytest tests/test_base_layout.py tests/test_auth.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add templates/base.html tests/test_base_layout.py
git commit -m "feat: add a confirmation modal before logging out"
```

---

### Task 3: Pharmacy page polish — stat cards and form sections

**Files:**
- Modify: `templates/pharmacy/pharmacy_management.html`
- Test: `tests/test_pharmacy.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `.stat-card` / `.stat-card-label` / `.stat-card-value` and `.form-section` / `.form-section-title` from Task 1.

- [ ] **Step 1: Swap the three summary cards from `.card` to `.stat-card`**

In `templates/pharmacy/pharmacy_management.html`, replace:

```html
  <section class="row g-3 mb-4">
    <div class="col-sm-4">
      <div class="card h-100">
        <div class="card-body">
          <p class="text-muted mb-1">
            Displayed medications
          </p>
          <strong
            id="medication-total"
            class="fs-3"
          >
            0
          </strong>
        </div>
      </div>
    </div>

    <div class="col-sm-4">
      <div class="card h-100">
        <div class="card-body">
          <p class="text-muted mb-1">
            Low stock
          </p>
          <strong
            id="low-stock-total"
            class="fs-3 text-warning-emphasis"
          >
            0
          </strong>
        </div>
      </div>
    </div>

    <div class="col-sm-4">
      <div class="card h-100">
        <div class="card-body">
          <p class="text-muted mb-1">
            Out of stock
          </p>
          <strong
            id="out-of-stock-total"
            class="fs-3 text-danger"
          >
            0
          </strong>
        </div>
      </div>
    </div>
  </section>
```

with:

```html
  <section class="row g-3 mb-4">
    <div class="col-sm-4">
      <div class="stat-card h-100">
        <p class="stat-card-label mb-0">
          Displayed medications
        </p>
        <strong
          id="medication-total"
          class="stat-card-value"
        >
          0
        </strong>
      </div>
    </div>

    <div class="col-sm-4">
      <div class="stat-card h-100">
        <p class="stat-card-label mb-0">
          Low stock
        </p>
        <strong
          id="low-stock-total"
          class="stat-card-value text-warning-emphasis"
        >
          0
        </strong>
      </div>
    </div>

    <div class="col-sm-4">
      <div class="stat-card h-100">
        <p class="stat-card-label mb-0">
          Out of stock
        </p>
        <strong
          id="out-of-stock-total"
          class="stat-card-value text-danger"
        >
          0
        </strong>
      </div>
    </div>
  </section>
```

- [ ] **Step 2: Group the Add Medication modal's fields into form sections**

In the same file, replace:

```html
        <div class="modal-body">
          <div
            id="medication-form-alert"
            class="alert alert-danger d-none"
          ></div>

          <input
            type="hidden"
            id="medication-edit-id"
          >

          <div class="mb-3">
            <label
              for="medication-name"
              class="form-label"
            >
              Medication name *
            </label>
            <input
              type="text"
              id="medication-name"
              class="form-control"
              maxlength="120"
              required
            >
          </div>

          <div class="row g-3 mb-3">
            <div class="col-sm-6">
              <label
                for="medication-form-type"
                class="form-label"
              >
                Form *
              </label>
              <select
                id="medication-form-type"
                class="form-select"
                required
              >
                <option value="">Select form</option>
                {% for option in medication_form_options %}
                  <option value="{{ option }}">
                    {{ option }}
                  </option>
                {% endfor %}
              </select>
            </div>

            <div class="col-sm-6">
              <label
                for="medication-standard-dosage"
                class="form-label"
              >
                Standard dosage *
              </label>
              <select
                id="medication-standard-dosage"
                class="form-select"
                required
              >
                <option value="">Select dosage</option>
                {% for option in standard_dosage_options %}
                  <option value="{{ option }}">
                    {{ option }}
                  </option>
                {% endfor %}
              </select>
            </div>
          </div>

          <div class="row g-3 mb-3">
            <div class="col-sm-6">
              <label
                for="medication-unit"
                class="form-label"
              >
                Stock unit *
              </label>
              <select
                id="medication-unit"
                class="form-select"
                required
              >
                {% for option in stock_unit_options %}
                  <option
                    value="{{ option }}"
                    {% if option == "units" %}selected{% endif %}
                  >
                    {{ option }}
                  </option>
                {% endfor %}
              </select>
            </div>

            <div class="col-sm-6">
              <label
                for="medication-reorder-level"
                class="form-label"
              >
                Reorder level *
              </label>
              <input
                type="number"
                id="medication-reorder-level"
                class="form-control"
                min="0"
                value="10"
                required
              >
            </div>
          </div>

          <div
            id="initial-stock-group"
            class="mb-3"
          >
            <label
              for="medication-initial-stock"
              class="form-label"
            >
              Initial stock
            </label>
            <input
              type="number"
              id="medication-initial-stock"
              class="form-control"
              min="0"
              value="0"
            >
          </div>

          <div class="form-check">
            <input
              type="checkbox"
              id="medication-active"
              class="form-check-input"
              checked
            >
            <label
              for="medication-active"
              class="form-check-label"
            >
              Available for prescribing
            </label>
          </div>
        </div>
```

with:

```html
        <div class="modal-body">
          <div
            id="medication-form-alert"
            class="alert alert-danger d-none"
          ></div>

          <input
            type="hidden"
            id="medication-edit-id"
          >

          <div class="form-section">
            <p class="form-section-title">Medication Details</p>

            <div class="mb-3">
              <label
                for="medication-name"
                class="form-label"
              >
                Medication name *
              </label>
              <input
                type="text"
                id="medication-name"
                class="form-control"
                maxlength="120"
                required
              >
            </div>

            <div class="row g-3 mb-3">
              <div class="col-sm-6">
                <label
                  for="medication-form-type"
                  class="form-label"
                >
                  Form *
                </label>
                <select
                  id="medication-form-type"
                  class="form-select"
                  required
                >
                  <option value="">Select form</option>
                  {% for option in medication_form_options %}
                    <option value="{{ option }}">
                      {{ option }}
                    </option>
                  {% endfor %}
                </select>
              </div>

              <div class="col-sm-6">
                <label
                  for="medication-standard-dosage"
                  class="form-label"
                >
                  Standard dosage *
                </label>
                <select
                  id="medication-standard-dosage"
                  class="form-select"
                  required
                >
                  <option value="">Select dosage</option>
                  {% for option in standard_dosage_options %}
                    <option value="{{ option }}">
                      {{ option }}
                    </option>
                  {% endfor %}
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <p class="form-section-title">Stock Settings</p>

            <div class="row g-3 mb-3">
              <div class="col-sm-6">
                <label
                  for="medication-unit"
                  class="form-label"
                >
                  Stock unit *
                </label>
                <select
                  id="medication-unit"
                  class="form-select"
                  required
                >
                  {% for option in stock_unit_options %}
                    <option
                      value="{{ option }}"
                      {% if option == "units" %}selected{% endif %}
                    >
                      {{ option }}
                    </option>
                  {% endfor %}
                </select>
              </div>

              <div class="col-sm-6">
                <label
                  for="medication-reorder-level"
                  class="form-label"
                >
                  Reorder level *
                </label>
                <input
                  type="number"
                  id="medication-reorder-level"
                  class="form-control"
                  min="0"
                  value="10"
                  required
                >
              </div>
            </div>

            <div
              id="initial-stock-group"
              class="mb-3"
            >
              <label
                for="medication-initial-stock"
                class="form-label"
              >
                Initial stock
              </label>
              <input
                type="number"
                id="medication-initial-stock"
                class="form-control"
                min="0"
                value="0"
              >
            </div>

            <div class="form-check">
              <input
                type="checkbox"
                id="medication-active"
                class="form-check-input"
                checked
              >
              <label
                for="medication-active"
                class="form-check-label"
              >
                Available for prescribing
              </label>
            </div>
          </div>
        </div>
```

- [ ] **Step 3: Group the Adjust Stock modal's fields into a form section**

In the same file, replace:

```html
        <div class="modal-body">
          <div
            id="stock-form-alert"
            class="alert alert-danger d-none"
          ></div>

          <input
            type="hidden"
            id="stock-medication-id"
          >

          <div class="row g-3 mb-4">
            <div class="col-sm-5">
              <label
                for="stock-quantity-change"
                class="form-label"
              >
                Quantity change *
              </label>
              <input
                type="number"
                id="stock-quantity-change"
                class="form-control"
                placeholder="+50 or -5"
                required
              >
              <div class="form-text">
                Positive adds stock; negative removes stock.
              </div>
            </div>

            <div class="col-sm-7">
              <label
                for="stock-reason"
                class="form-label"
              >
                Reason *
              </label>
              <input
                type="text"
                id="stock-reason"
                class="form-control"
                minlength="3"
                maxlength="255"
                placeholder="Received delivery, damaged stock..."
                required
              >
            </div>
          </div>

          <h3 class="h6">Recent stock history</h3>
          <div
            id="stock-history"
            class="stock-history border rounded"
          ></div>
        </div>
```

with:

```html
        <div class="modal-body">
          <div
            id="stock-form-alert"
            class="alert alert-danger d-none"
          ></div>

          <input
            type="hidden"
            id="stock-medication-id"
          >

          <div class="form-section">
            <p class="form-section-title">Adjustment</p>

            <div class="row g-3 mb-4">
              <div class="col-sm-5">
                <label
                  for="stock-quantity-change"
                  class="form-label"
                >
                  Quantity change *
                </label>
                <input
                  type="number"
                  id="stock-quantity-change"
                  class="form-control"
                  placeholder="+50 or -5"
                  required
                >
                <div class="form-text">
                  Positive adds stock; negative removes stock.
                </div>
              </div>

              <div class="col-sm-7">
                <label
                  for="stock-reason"
                  class="form-label"
                >
                  Reason *
                </label>
                <input
                  type="text"
                  id="stock-reason"
                  class="form-control"
                  minlength="3"
                  maxlength="255"
                  placeholder="Received delivery, damaged stock..."
                  required
                >
              </div>
            </div>
          </div>

          <h3 class="h6">Recent stock history</h3>
          <div
            id="stock-history"
            class="stock-history border rounded"
          ></div>
        </div>
```

- [ ] **Step 4: Run the pharmacy test suite**

Run: `python -m pytest tests/test_pharmacy.py -v`
Expected: All PASS (field IDs/names unchanged, only wrapper markup added)

- [ ] **Step 5: Commit**

```bash
git add templates/pharmacy/pharmacy_management.html
git commit -m "style: apply stat-card and form-section polish to the pharmacy page"
```

---

### Task 4: Book Appointment form-section wrapper (both booking templates)

**Files:**
- Modify: `templates/appointments/receptionist_createAppointment.html`
- Modify: `templates/appointments/patient_bookAppointment.html`
- Test: `tests/test_appointments.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `.form-section` / `.form-section-title` from Task 1.

- [ ] **Step 1: Wrap the staff booking form's fields into sections**

In `templates/appointments/receptionist_createAppointment.html`, replace:

```html
    <form id="appointment-form" novalidate>
      <div class="row g-3">
        <div class="col-md-6 position-relative">
          <label for="patient_ic" class="form-label">Patient IC *</label>
          <input type="text" class="form-control" id="patient_ic" name="patient_ic" required
                 pattern="\d{6}-\d{2}-\d{4}"
                 placeholder="e.g. xxxxxx-xx-xxxx"
                 autocomplete="off">
          <input type="hidden" id="patient_id" name="patient_id">
          <div class="invalid-feedback">A valid, registered patient IC is required.</div>
          <div id="patient-lookup-feedback" class="form-text"></div>
          <div id="patient-ic-suggestions" class="list-group position-absolute w-100 d-none" style="z-index: 1000;"></div>
        </div>

        <div class="col-md-3">
          <label for="specialty" class="form-label">Specialty</label>
          <select class="form-select" id="specialty">
            <option value="">All specialties</option>
          </select>
        </div>

        <div class="col-md-3">
          <label for="doctor_id" class="form-label">Doctor *</label>
          <select class="form-select" id="doctor_id" name="doctor_id" required>
            <option value="" selected disabled>Loading doctors...</option>
          </select>
          <div class="invalid-feedback">Please select a doctor.</div>
        </div>

        <div class="col-md-6">
          <label for="appointment_date" class="form-label">Date *</label>
          <input type="date" class="form-control" id="appointment_date" name="appointment_date" required>
          <div class="invalid-feedback">Please choose a date that is not in the past.</div>
        </div>

        <div class="col-12">
          <label class="form-label d-block">Time slot *</label>
          <input type="hidden" id="start_time" name="start_time" required>
          <div id="slot-grid" class="d-flex flex-wrap gap-2">
            <p class="text-muted mb-0" id="slot-placeholder">Select a doctor and date to see available time slots.</p>
          </div>
          <div class="invalid-feedback" id="slot-error">Please select an available time slot.</div>
        </div>

        <div class="col-md-8">
          <label for="reason" class="form-label">Reason for visit *</label>
          <input type="text" class="form-control" id="reason" name="reason" required minlength="2" maxlength="255"
                 placeholder="e.g. Fever and cough">
          <div class="invalid-feedback">Reason for visit is required.</div>
        </div>
      </div>

      <div class="mt-4 d-flex gap-2">
        <button type="submit" class="btn btn-primary" id="submit-btn">Book Appointment</button>
        <button type="reset" class="btn btn-outline-secondary">Clear</button>
      </div>
    </form>
```

with:

```html
    <form id="appointment-form" novalidate>
      <div class="form-section">
        <p class="form-section-title">Patient</p>
        <div class="row g-3">
          <div class="col-md-6 position-relative">
            <label for="patient_ic" class="form-label">Patient IC *</label>
            <input type="text" class="form-control" id="patient_ic" name="patient_ic" required
                   pattern="\d{6}-\d{2}-\d{4}"
                   placeholder="e.g. xxxxxx-xx-xxxx"
                   autocomplete="off">
            <input type="hidden" id="patient_id" name="patient_id">
            <div class="invalid-feedback">A valid, registered patient IC is required.</div>
            <div id="patient-lookup-feedback" class="form-text"></div>
            <div id="patient-ic-suggestions" class="list-group position-absolute w-100 d-none" style="z-index: 1000;"></div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <p class="form-section-title">Appointment Details</p>
        <div class="row g-3">
          <div class="col-md-3">
            <label for="specialty" class="form-label">Specialty</label>
            <select class="form-select" id="specialty">
              <option value="">All specialties</option>
            </select>
          </div>

          <div class="col-md-3">
            <label for="doctor_id" class="form-label">Doctor *</label>
            <select class="form-select" id="doctor_id" name="doctor_id" required>
              <option value="" selected disabled>Loading doctors...</option>
            </select>
            <div class="invalid-feedback">Please select a doctor.</div>
          </div>

          <div class="col-md-6">
            <label for="appointment_date" class="form-label">Date *</label>
            <input type="date" class="form-control" id="appointment_date" name="appointment_date" required>
            <div class="invalid-feedback">Please choose a date that is not in the past.</div>
          </div>

          <div class="col-12">
            <label class="form-label d-block">Time slot *</label>
            <input type="hidden" id="start_time" name="start_time" required>
            <div id="slot-grid" class="d-flex flex-wrap gap-2">
              <p class="text-muted mb-0" id="slot-placeholder">Select a doctor and date to see available time slots.</p>
            </div>
            <div class="invalid-feedback" id="slot-error">Please select an available time slot.</div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <p class="form-section-title">Visit Reason</p>
        <div class="row g-3">
          <div class="col-md-8">
            <label for="reason" class="form-label">Reason for visit *</label>
            <input type="text" class="form-control" id="reason" name="reason" required minlength="2" maxlength="255"
                   placeholder="e.g. Fever and cough">
            <div class="invalid-feedback">Reason for visit is required.</div>
          </div>
        </div>
      </div>

      <div class="mt-4 d-flex gap-2">
        <button type="submit" class="btn btn-primary" id="submit-btn">Book Appointment</button>
        <button type="reset" class="btn btn-outline-secondary">Clear</button>
      </div>
    </form>
```

- [ ] **Step 2: Wrap the patient self-booking form's fields into sections**

In `templates/appointments/patient_bookAppointment.html`, replace:

```html
    <form id="appointment-form" novalidate>
      <div class="row g-3">
        <div class="col-12">
          <label class="form-label">Booking as</label>
          <p class="form-control-plaintext fw-semibold" id="patient-display">Loading your record...</p>
          <input type="hidden" id="patient_id" name="patient_id" required>
        </div>

        <div class="col-md-3">
          <label for="specialty" class="form-label">Specialty</label>
          <select class="form-select" id="specialty">
            <option value="">All specialties</option>
          </select>
        </div>

        <div class="col-md-3">
          <label for="doctor_id" class="form-label">Doctor *</label>
          <select class="form-select" id="doctor_id" name="doctor_id" required>
            <option value="" selected disabled>Loading doctors...</option>
          </select>
          <div class="invalid-feedback">Please select a doctor.</div>
        </div>

        <div class="col-md-6">
          <label for="appointment_date" class="form-label">Date *</label>
          <input type="date" class="form-control" id="appointment_date" name="appointment_date" required>
          <div class="invalid-feedback">Please choose a date that is not in the past.</div>
        </div>

        <div class="col-12">
          <label class="form-label d-block">Time slot *</label>
          <input type="hidden" id="start_time" name="start_time" required>
          <div id="slot-grid" class="d-flex flex-wrap gap-2">
            <p class="text-muted mb-0" id="slot-placeholder">Select a doctor and date to see available time slots.</p>
          </div>
          <div class="invalid-feedback" id="slot-error">Please select an available time slot.</div>
        </div>

        <div class="col-md-8">
          <label for="reason" class="form-label">Reason for visit *</label>
          <input type="text" class="form-control" id="reason" name="reason" required minlength="2" maxlength="255"
                 placeholder="e.g. Fever and cough">
          <div class="invalid-feedback">Reason for visit is required.</div>
        </div>
      </div>

      <div class="mt-4 d-flex gap-2">
        <button type="submit" class="btn btn-primary" id="submit-btn">Book Appointment</button>
        <button type="reset" class="btn btn-outline-secondary">Clear</button>
      </div>
    </form>
```

with:

```html
    <form id="appointment-form" novalidate>
      <div class="form-section">
        <p class="form-section-title">Your Booking</p>
        <div class="row g-3">
          <div class="col-12">
            <label class="form-label">Booking as</label>
            <p class="form-control-plaintext fw-semibold" id="patient-display">Loading your record...</p>
            <input type="hidden" id="patient_id" name="patient_id" required>
          </div>
        </div>
      </div>

      <div class="form-section">
        <p class="form-section-title">Appointment Details</p>
        <div class="row g-3">
          <div class="col-md-3">
            <label for="specialty" class="form-label">Specialty</label>
            <select class="form-select" id="specialty">
              <option value="">All specialties</option>
            </select>
          </div>

          <div class="col-md-3">
            <label for="doctor_id" class="form-label">Doctor *</label>
            <select class="form-select" id="doctor_id" name="doctor_id" required>
              <option value="" selected disabled>Loading doctors...</option>
            </select>
            <div class="invalid-feedback">Please select a doctor.</div>
          </div>

          <div class="col-md-6">
            <label for="appointment_date" class="form-label">Date *</label>
            <input type="date" class="form-control" id="appointment_date" name="appointment_date" required>
            <div class="invalid-feedback">Please choose a date that is not in the past.</div>
          </div>

          <div class="col-12">
            <label class="form-label d-block">Time slot *</label>
            <input type="hidden" id="start_time" name="start_time" required>
            <div id="slot-grid" class="d-flex flex-wrap gap-2">
              <p class="text-muted mb-0" id="slot-placeholder">Select a doctor and date to see available time slots.</p>
            </div>
            <div class="invalid-feedback" id="slot-error">Please select an available time slot.</div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <p class="form-section-title">Visit Reason</p>
        <div class="row g-3">
          <div class="col-md-8">
            <label for="reason" class="form-label">Reason for visit *</label>
            <input type="text" class="form-control" id="reason" name="reason" required minlength="2" maxlength="255"
                   placeholder="e.g. Fever and cough">
            <div class="invalid-feedback">Reason for visit is required.</div>
          </div>
        </div>
      </div>

      <div class="mt-4 d-flex gap-2">
        <button type="submit" class="btn btn-primary" id="submit-btn">Book Appointment</button>
        <button type="reset" class="btn btn-outline-secondary">Clear</button>
      </div>
    </form>
```

- [ ] **Step 3: Run the appointments test suite**

Run: `python -m pytest tests/test_appointments.py -v`
Expected: All PASS (field IDs/names/hrefs unchanged, only wrapper markup added; `appointment-form.js` selects everything by ID and doesn't care about the new wrapper divs)

- [ ] **Step 4: Commit**

```bash
git add templates/appointments/receptionist_createAppointment.html templates/appointments/patient_bookAppointment.html
git commit -m "style: group booking form fields into labeled sections"
```

---

### Task 5: Manual cross-page verification

**Files:** none (verification only)

**Interfaces:** none

- [ ] **Step 1: Start the app**

Use the existing `.claude/launch.json` "api" dev server config (or `uvicorn agile_ci_demo.app:app --reload`).

- [ ] **Step 2: Check centering**

Load the Reports page (or any content-heavy page) on a wide viewport and confirm the content area is now centered, not pinned left.

- [ ] **Step 3: Check the logout confirmation**

Log in as any role, click Logout, confirm a modal appears with Cancel/Log Out buttons, Cancel keeps the session active, and Log Out actually calls `DELETE /api/auth/session` and redirects to `/auth/login`.

- [ ] **Step 4: Check Pharmacy**

Confirm the three summary tiles render as flat stat cards (not default Bootstrap `.card` shadow/border), and that both the Add Medication and Adjust Stock modals show grouped section labels ("Medication Details" / "Stock Settings" / "Adjustment").

- [ ] **Step 5: Check Book Appointment (both staff and patient views)**

Confirm both booking forms show grouped section labels, and the time-slot buttons render as rounded pill buttons.

- [ ] **Step 6: Check Doctor Schedule**

Confirm hovering a date in "Upcoming Dates" shows the new hover/accent-border treatment.

- [ ] **Step 7: Check responsiveness**

Resize to a mobile viewport and confirm: the sidebar collapses behind the hamburger (already verified in the first redesign pass), stat-card grids stack to one column, and data tables scroll horizontally within their existing `.table-responsive` wrapper without breaking page layout.

- [ ] **Step 8: Report findings**

Note anything that looks off (page/role/viewport + what's wrong) for a follow-up fix.

---

## Self-Review Notes

- **Spec coverage:** every item in the design spec maps to a task, except the table→mobile-card JS pattern for Patients/Doctor Schedule/Pharmacy, which is explicitly descoped (see "Scope adjustment" in the Architecture section above) rather than silently dropped.
- **Templates needing no changes:** confirmed Patients List, Patient Registration, Login/Reset Password, and Staff List/Create/View need zero markup edits — they inherit the centering fix automatically, and none of them have stat cards or multi-group forms in scope for this pass.
- **Class/selector consistency:** `.stat-card` / `.stat-card-label` / `.stat-card-value` and `.form-section` / `.form-section-title` are defined once in Task 1 and used identically (same class names) in Tasks 3 and 4.
- **JS safety confirmed by inspection:** `appointment-form.js` and `pharmacy-management.js` select every element by ID (`getElementById`), never by `.card` or by the form's row/column wrapper structure, so wrapping existing fields in new `.form-section` divs and renaming `.card` to `.stat-card` cannot break their behavior. `doctor-schedule.js` already emits a `.date-list-item` class on every generated list item (`static/js/doctor-schedule.js:111`), so its hover styling in Task 1 needs no template or JS change at all.
