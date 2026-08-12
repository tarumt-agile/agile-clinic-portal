# Modern Slate UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reskin Agile Clinic Portal with the approved "Modern Slate" visual design (dark sidebar nav, indigo accent, light content area) across every page and role, without changing any route, permission, or business-logic flow.

**Architecture:** `templates/base.html` currently renders one shared Bootstrap top-navbar layout for every page. It's replaced with two shells selected by authentication state: an **app shell** (dark sidebar + content pane) for the 21 authenticated templates, and an **auth shell** (centered white card on a slate background) for the 3 unauthenticated templates (login, forgot password, reset password). All role-based nav logic is preserved exactly, just re-rendered as sidebar links instead of navbar links. Design tokens and component overrides live in `static/css/app.css`, which cascades to every page automatically since 18 of the 24 templates use only Bootstrap classes with no page-specific CSS. The 6 templates with their own CSS file (`staff_list.css`, `staff_create.css`, `staff_view.css`, `pharmacy-management.css`, `reports-dashboard.css`, `prescription-print.css`) get their hardcoded brand colors swapped for the new tokens.

**Tech Stack:** FastAPI + Jinja2 templates, Bootstrap 5.3.3 (CDN), vanilla CSS/JS, pytest + FastAPI TestClient.

## Global Constraints

- No route, permission, business-logic, or page-flow changes — this is markup structure and CSS only (per `docs/superpowers/specs/2026-08-03-modern-slate-ui-redesign-design.md`).
- Design tokens (exact hex values) are fixed by the spec's token table — reuse them verbatim, do not invent new colors.
- Keep Bootstrap 5.3.3 as a dependency; do not remove or replace it.
- Every task must leave `pytest` green before moving to the next task.

---

## File Structure

- `static/css/app.css` — design tokens (CSS custom properties), global Bootstrap component overrides, and the new app-shell/auth-shell layout CSS. Single file, matches the existing convention of one shared stylesheet.
- `templates/base.html` — the two shells (app shell / auth shell), role-based sidebar nav, mobile sidebar toggle script.
- `static/css/prescription-print.css` — print-safe selectors updated for the new shell markup, brand accent applied.
- `static/css/staff_list.css`, `static/css/staff_create.css`, `static/css/staff_view.css`, `static/css/reports-dashboard.css` — hardcoded blue accents swapped for the indigo token.
- `static/js/reports-dashboard.js` — hardcoded chart colors swapped for the indigo token.
- `tests/test_pharmacy.py` — one existing assertion updated for the new sidebar link markup.
- `tests/test_base_layout.py` — new file, covers the app shell vs. auth shell and per-role sidebar link contract.

No other template files need changes — confirmed by inspection that the remaining 18 templates (`patients/*`, `appointments/*`, `consultations/*`, `pharmacy_management.html`) use only Bootstrap classes and inherit the new look entirely through `base.html` + `app.css`.

---

### Task 1: Design tokens and global Bootstrap overrides

**Files:**
- Modify: `static/css/app.css`
- Test: manual — verified visually in Task 10, and indirectly by every later task's pytest run (no markup depends on these rules)

**Interfaces:**
- Produces: CSS custom properties consumed by Tasks 2–8: `--clinic-sidebar-bg`, `--clinic-sidebar-hover`, `--clinic-sidebar-text`, `--clinic-sidebar-border`, `--clinic-accent`, `--clinic-accent-soft`, `--clinic-accent-hover`, `--clinic-content-bg`, `--clinic-border`, `--clinic-table-header-bg`, `--clinic-table-header-text`, `--clinic-text`, `--clinic-input-border`, `--clinic-success-bg`, `--clinic-success-text`, `--clinic-pending-bg`, `--clinic-pending-text`, `--clinic-error`.

- [ ] **Step 1: Append design tokens and component overrides to `app.css`**

Append this to the end of `static/css/app.css` (the existing 14 lines — `.invalid-feedback`, `.medication-suggestions` — stay unchanged above it):

```css

/* ===== Modern Slate design tokens ===== */
:root {
  --clinic-sidebar-bg: #1e293b;
  --clinic-sidebar-hover: #334155;
  --clinic-sidebar-text: #cbd5e1;
  --clinic-sidebar-border: #334155;
  --clinic-accent: #4f46e5;
  --clinic-accent-soft: #6366f1;
  --clinic-accent-hover: #4338ca;
  --clinic-content-bg: #f8fafc;
  --clinic-border: #e2e8f0;
  --clinic-table-header-bg: #f1f5f9;
  --clinic-table-header-text: #475569;
  --clinic-text: #0f172a;
  --clinic-input-border: #dbe0e6;
  --clinic-success-bg: #dcfce7;
  --clinic-success-text: #166534;
  --clinic-pending-bg: #fef9c3;
  --clinic-pending-text: #854d0e;
  --clinic-error: #dc2626;
}

body {
  background-color: var(--clinic-content-bg);
  color: var(--clinic-text);
}

a {
  color: var(--clinic-accent);
}

a:hover {
  color: var(--clinic-accent-hover);
}

.btn-primary {
  --bs-btn-bg: var(--clinic-accent);
  --bs-btn-border-color: var(--clinic-accent);
  --bs-btn-hover-bg: var(--clinic-accent-hover);
  --bs-btn-hover-border-color: var(--clinic-accent-hover);
  --bs-btn-active-bg: var(--clinic-accent-hover);
  --bs-btn-active-border-color: var(--clinic-accent-hover);
  --bs-btn-focus-shadow-rgb: 99, 102, 241;
}

.card {
  border-color: var(--clinic-border);
  border-radius: 0.5rem;
}

.card-header,
.card-footer {
  background-color: #fff;
  border-color: var(--clinic-border);
}

.table thead th {
  background-color: var(--clinic-table-header-bg);
  color: var(--clinic-table-header-text);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border-bottom-width: 1px;
}

.table > :not(caption) > * > * {
  border-bottom-color: var(--clinic-border);
}

.table-hover > tbody > tr:hover > * {
  background-color: var(--clinic-content-bg);
}

.form-control:focus,
.form-select:focus {
  border-color: var(--clinic-accent-soft);
  box-shadow: 0 0 0 0.2rem rgba(99, 102, 241, 0.15);
}

.nav-tabs .nav-link {
  color: #64748b;
}

.nav-tabs .nav-link.active {
  color: var(--clinic-accent);
  border-color: var(--clinic-border) var(--clinic-border) #fff;
}

.badge.bg-success {
  background-color: var(--clinic-success-bg) !important;
  color: var(--clinic-success-text) !important;
}

.badge.bg-warning {
  background-color: var(--clinic-pending-bg) !important;
  color: var(--clinic-pending-text) !important;
}
```

- [ ] **Step 2: Confirm the app still boots and no CSS syntax error breaks page rendering**

Run: `python -m pytest tests/test_app.py -v`
Expected: PASS (this suite hits basic pages; a malformed `app.css` wouldn't fail Jinja rendering, but this confirms nothing else broke while editing the file)

- [ ] **Step 3: Commit**

```bash
git add static/css/app.css
git commit -m "style: add Modern Slate design tokens and Bootstrap overrides"
```

---

### Task 2: Sidebar app shell in base.html

**Files:**
- Modify: `templates/base.html:12-60` (body content, replacing the navbar)
- Modify: `static/css/app.css` (append sidebar layout CSS)
- Test: `tests/test_base_layout.py` (new file, created in this task)

**Interfaces:**
- Consumes: tokens from Task 1 (`--clinic-sidebar-bg`, `--clinic-sidebar-hover`, `--clinic-sidebar-text`, `--clinic-sidebar-border`, `--clinic-accent-soft`, `--clinic-content-bg`)
- Produces: `.sidebar-link` / `.sidebar-link.active` class contract and `#app-sidebar` / `.app-shell` / `.app-content` markup IDs/classes, consumed by Task 9's regression tests and referenced by Task 4's print CSS fix.

- [ ] **Step 1: Write the failing sidebar-contract tests**

Create `tests/test_base_layout.py`:

```python
from __future__ import annotations

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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
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


def create_staff_and_login(client: TestClient, role: str = "receptionist") -> None:
    payload: dict[str, object] = {
        "full_name": "Nora Ibrahim",
        "email": f"{role}@example.com",
        "role": role,
    }
    if role == "doctor":
        payload.update(
            {
                "license_number": "MMC-90001",
                "specialty": "General Medicine",
                "status": "active",
            }
        )
    create_response = client.post("/api/staff", json=payload)
    assert create_response.status_code == 201, create_response.json()

    welcome_email = next(
        message for message in reversed(get_outbox()) if message.to == payload["email"]
    )
    match = re.search(r"temporary password is: (\S+)", welcome_email.body)
    assert match is not None

    login_response = client.post(
        "/api/auth/login",
        json={"email": payload["email"], "password": match.group(1)},
    )
    assert login_response.status_code == 200, login_response.json()


def create_patient_and_login(client: TestClient) -> None:
    created = client.post(
        "/api/patients",
        json={
            "full_name": "Jane Tan",
            "date_of_birth": "1990-05-20",
            "gender": "female",
            "phone_number": "012-3456789",
            "email": "jane.tan@example.com",
            "ic_or_passport": "900520-10-1234",
            "address": "1 Jalan Testing, Kuala Lumpur",
        },
    ).json()

    login_response = client.post(
        "/api/auth/patient-login",
        json={
            "ic_or_passport": created["ic_or_passport"],
            "phone_number": created["phone_number"],
        },
    )
    assert login_response.status_code == 200, login_response.json()


@pytest.mark.parametrize("role", ["receptionist", "nurse"])
def test_receptionist_and_nurse_see_front_desk_sidebar_links(
    client: TestClient, role: str
) -> None:
    create_staff_and_login(client, role)

    response = client.get("/patients")

    assert response.status_code == 200
    assert '<a class="sidebar-link active" href="/patients">Patients</a>' in response.text
    assert (
        '<a class="sidebar-link" href="/patients/register">Register Patient</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/create">Book Appointment</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/doctor-schedule">Doctor Schedule</a>'
        in response.text
    )
    assert 'href="/staff"' not in response.text
    assert 'href="/appointments/consultations"' not in response.text


def test_admin_sees_pharmacy_staff_and_reports_sidebar_links(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert '<a class="sidebar-link" href="/pharmacy">Pharmacy</a>' in response.text
    assert '<a class="sidebar-link" href="/staff">Staff</a>' in response.text
    assert '<a class="sidebar-link" href="/reports">Reports</a>' in response.text


def test_doctor_sees_schedule_and_consultation_sidebar_links(client: TestClient) -> None:
    create_staff_and_login(client, "doctor")

    response = client.get("/appointments/schedule")

    assert response.status_code == 200
    assert (
        '<a class="sidebar-link active" href="/appointments/schedule">My Schedule</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/consultations">Start Consultation</a>'
        in response.text
    )
    assert 'href="/patients"' not in response.text


def test_patient_sees_only_patient_sidebar_links(client: TestClient) -> None:
    create_patient_and_login(client)

    response = client.get("/patients/dashboard")

    assert response.status_code == 200
    assert (
        '<a class="sidebar-link active" href="/patients/dashboard">My Dashboard</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/book">Book My Appointment</a>'
        in response.text
    )
    assert (
        '<a class="sidebar-link" href="/appointments/mine">My Appointments</a>'
        in response.text
    )
    assert 'href="/staff"' not in response.text


def test_app_shell_wraps_authenticated_pages(client: TestClient) -> None:
    create_staff_and_login(client, "admin")

    response = client.get("/patients")

    assert response.status_code == 200
    assert 'id="app-sidebar"' in response.text
    assert 'class="app-shell"' in response.text
```

- [ ] **Step 2: Run the new tests to verify they fail against the current navbar markup**

Run: `python -m pytest tests/test_base_layout.py -v`
Expected: FAIL — none of the `sidebar-link` / `app-sidebar` / `app-shell` markers exist yet (current `base.html` still renders `nav-link`/`navbar`).

- [ ] **Step 3: Replace the navbar with the sidebar app shell in `base.html`**

Replace lines 12–60 of `templates/base.html` (from `<body class="bg-light">` through the closing `</main>`) with:

```html
<body>
  {% set role = request.session.get("role") %}
  {% set is_patient = request.session.get("user_type") == "patient" %}
  {% set authed = role or is_patient %}
  {% set current_path = request.url.path %}
  {% if authed %}
  <div class="app-shell">
    <button
      type="button"
      class="sidebar-toggle"
      id="sidebar-toggle"
      aria-label="Toggle navigation"
      aria-controls="app-sidebar"
      aria-expanded="false"
    >&#9776;</button>
    <aside class="app-sidebar" id="app-sidebar">
      <div class="sidebar-brand">
        {% if role == "doctor" %}
          <a href="/appointments/schedule">Agile Clinic Portal</a>
        {% elif is_patient %}
          <a href="/patients/dashboard">Agile Clinic Portal</a>
        {% else %}
          <a href="/patients">Agile Clinic Portal</a>
        {% endif %}
      </div>
      <nav class="sidebar-nav">
        {% if role in ["receptionist", "nurse", "admin"] %}
          <a class="sidebar-link{{ ' active' if current_path == '/patients' else '' }}" href="/patients">Patients</a>
          <a class="sidebar-link{{ ' active' if current_path == '/patients/register' else '' }}" href="/patients/register">Register Patient</a>
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/create' else '' }}" href="/appointments/create">Book Appointment</a>
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/doctor-schedule' else '' }}" href="/appointments/doctor-schedule">Doctor Schedule</a>
        {% endif %}
        {% if role in ["receptionist", "admin"] %}
          <a class="sidebar-link{{ ' active' if current_path == '/pharmacy' else '' }}" href="/pharmacy">Pharmacy</a>
        {% endif %}
        {% if role == "doctor" %}
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/schedule' else '' }}" href="/appointments/schedule">My Schedule</a>
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/consultations' else '' }}" href="/appointments/consultations">Start Consultation</a>
        {% endif %}
        {% if is_patient %}
          <a class="sidebar-link{{ ' active' if current_path == '/patients/dashboard' else '' }}" href="/patients/dashboard">My Dashboard</a>
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/book' else '' }}" href="/appointments/book">Book My Appointment</a>
          <a class="sidebar-link{{ ' active' if current_path == '/appointments/mine' else '' }}" href="/appointments/mine">My Appointments</a>
        {% endif %}
        {% if role == "admin" %}
          <a class="sidebar-link{{ ' active' if current_path == '/staff' else '' }}" href="/staff">Staff</a>
          <a class="sidebar-link{{ ' active' if current_path == '/reports' else '' }}" href="/reports">Reports</a>
        {% endif %}
      </nav>
      <div class="sidebar-user">
        <a class="sidebar-link" href="#" id="logout-link">Logout</a>
      </div>
    </aside>
    <div class="app-main">
      <main class="app-content">
        {% block content %}{% endblock %}
      </main>
    </div>
  </div>
  {% else %}
  <div class="auth-shell">
    <div class="auth-card-wrap">
      {% block content %}{% endblock %}
    </div>
  </div>
  {% endif %}
```

Leave everything from the `<script src="https://cdn.jsdelivr.net/...bootstrap.bundle.min.js">` line onward (previously lines 62–76) in place for now — Step 5 below adds the sidebar toggle script right after the existing logout script, still before `{% block extra_js %}{% endblock %}`.

- [ ] **Step 4: Append the app-shell and auth-shell layout CSS to `app.css`**

Append this to the end of `static/css/app.css` (after Task 1's rules):

```css

/* ===== App shell (sidebar navigation) ===== */
.app-shell {
  display: flex;
  min-height: 100vh;
}

.app-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 1rem 0;
  background-color: var(--clinic-sidebar-bg);
  color: var(--clinic-sidebar-text);
}

.sidebar-brand {
  padding: 0 1rem 1rem;
  margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--clinic-sidebar-border);
}

.sidebar-brand a {
  color: #fff;
  font-weight: 700;
  font-size: 1rem;
  text-decoration: none;
}

.sidebar-nav {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.sidebar-link {
  display: block;
  padding: 0.6rem 1rem;
  border-right: 3px solid transparent;
  color: var(--clinic-sidebar-text);
  font-size: 0.9rem;
  text-decoration: none;
}

.sidebar-link:hover {
  background-color: var(--clinic-sidebar-hover);
  color: #fff;
}

.sidebar-link.active {
  background-color: var(--clinic-sidebar-hover);
  border-right-color: var(--clinic-accent-soft);
  color: #fff;
  font-weight: 600;
}

.sidebar-user {
  padding: 0.75rem 0 0;
  border-top: 1px solid var(--clinic-sidebar-border);
}

.app-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.app-content {
  flex: 1;
  max-width: 1200px;
  padding: 1.5rem;
}

.sidebar-toggle {
  display: none;
  position: fixed;
  top: 0.75rem;
  left: 0.75rem;
  z-index: 1050;
  width: 2.5rem;
  height: 2.5rem;
  border: none;
  border-radius: 0.4rem;
  background-color: var(--clinic-sidebar-bg);
  color: #fff;
  font-size: 1.25rem;
}

@media (max-width: 768px) {
  .sidebar-toggle {
    display: block;
  }

  .app-sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 1040;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }

  .app-sidebar.is-open {
    transform: translateX(0);
  }

  .app-content {
    padding-top: 4rem;
  }
}

/* ===== Auth shell (login / forgot / reset password) ===== */
.auth-shell {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 1.5rem;
  background-color: var(--clinic-sidebar-bg);
}

.auth-card-wrap {
  width: 100%;
  max-width: 420px;
  padding: 2rem 1.75rem;
  background-color: #fff;
  border-radius: 0.75rem;
  box-shadow: 0 1.25rem 3rem rgba(0, 0, 0, 0.25);
}
```

- [ ] **Step 5: Add the mobile sidebar toggle script**

In `templates/base.html`, immediately after the existing `logoutLink` script block (the one calling `/api/auth/session`) and before `{% block extra_js %}{% endblock %}`, add:

```html
  <script>
    const sidebarToggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("app-sidebar");
    if (sidebarToggle && sidebar) {
      sidebarToggle.addEventListener("click", () => {
        const isOpen = sidebar.classList.toggle("is-open");
        sidebarToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });
    }
  </script>
```

- [ ] **Step 6: Run the sidebar tests again to verify they pass**

Run: `python -m pytest tests/test_base_layout.py -v`
Expected: PASS

- [ ] **Step 7: Run the full test suite to check for regressions**

Run: `python -m pytest -v`
Expected: All PASS except `tests/test_pharmacy.py::test_receptionist_and_admin_can_open_pharmacy_page` (fixed in Task 9) — confirm that is the *only* failure.

- [ ] **Step 8: Commit**

```bash
git add templates/base.html static/css/app.css tests/test_base_layout.py
git commit -m "feat: replace top navbar with Modern Slate sidebar app shell"
```

---

### Task 3: Auth shell for login/forgot/reset password pages

**Files:**
- Test: `tests/test_base_layout.py` (add one test)

**Interfaces:**
- Consumes: `.auth-shell` / `.auth-card-wrap` markup and CSS already produced by Task 2 (base.html and app.css already implement the unauthenticated branch — this task only adds the regression test that locks it in, since `templates/auth/login.html`, `forgot_password.html`, and `reset_password.html` need no changes: they already just fill `{% block content %}` with a centered form, which now renders inside `.auth-card-wrap` automatically).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_base_layout.py`:

```python
def test_login_page_renders_auth_shell_with_no_sidebar(client: TestClient) -> None:
    response = client.get("/auth/login")

    assert response.status_code == 200
    assert 'class="auth-shell"' in response.text
    assert 'class="auth-card-wrap"' in response.text
    assert 'id="app-sidebar"' not in response.text
```

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/test_base_layout.py::test_login_page_renders_auth_shell_with_no_sidebar -v`
Expected: PASS immediately — Task 2 already implemented the `{% else %}` branch in `base.html`. This step is a verification checkpoint, not new production code.

- [ ] **Step 3: Manually confirm the two other auth pages too**

Run: `python -m pytest tests/test_auth.py -v`
Expected: All PASS (confirms `/auth/forgot-password` and `/auth/reset-password` flows still work through the new shell — neither template needed edits since both only use `{% block content %}`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_base_layout.py
git commit -m "test: lock in the auth shell for login/forgot/reset password pages"
```

---

### Task 4: Prescription print page — fix print selectors and restyle to brand

**Files:**
- Modify: `static/css/prescription-print.css`
- Test: `tests/test_prescriptions.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `.app-sidebar`, `.sidebar-toggle`, `.app-content` classes from Task 2.

**Context:** The current `@media print` block hides navigation with `body > nav, .print-actions { display: none !important; }` and resets width with `main.container { ... }`. Task 2's new shell has no `<nav>` as a direct child of `<body>` (it's `.app-sidebar` nested inside `.app-shell`), and `<main>` now has class `app-content`, not `container`. Without this fix, printing a prescription would print the sidebar and hamburger button alongside it, and the prescription sheet would be squeezed into the leftover flex space instead of using the full page width.

- [ ] **Step 1: Fix the print selectors**

In `static/css/prescription-print.css`, replace:

```css
@media print {
  body {
    color: #000;
    background: #fff !important;
  }

  body > nav,
  .print-actions {
    display: none !important;
  }

  main.container {
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0 !important;
  }
```

with:

```css
@media print {
  body {
    color: #000;
    background: #fff !important;
  }

  .app-sidebar,
  .sidebar-toggle,
  .print-actions {
    display: none !important;
  }

  .app-shell {
    display: block;
  }

  main.app-content {
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0 !important;
  }
```

- [ ] **Step 2: Restyle the brand accent from Bootstrap blue to the Modern Slate indigo**

In the same file, replace:

```css
.prescription-clinic-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 3px solid #0d6efd;
}
```

with:

```css
.prescription-clinic-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 3px solid #4f46e5;
}
```

Replace:

```css
.prescription-rx-mark {
  color: #0d6efd;
  font-family: Georgia, serif;
  font-size: 3.5rem;
  font-style: italic;
  line-height: 1;
}
```

with:

```css
.prescription-rx-mark {
  color: #4f46e5;
  font-family: Georgia, serif;
  font-size: 3.5rem;
  font-style: italic;
  line-height: 1;
}
```

Replace:

```css
.prescription-diagnosis {
  padding: 1rem 1.25rem;
  background: #f2f6ff;
  border-left: 4px solid #0d6efd;
}
```

with:

```css
.prescription-diagnosis {
  padding: 1rem 1.25rem;
  background: #eef2ff;
  border-left: 4px solid #4f46e5;
}
```

- [ ] **Step 3: Run the prescription test suite**

Run: `python -m pytest tests/test_prescriptions.py -v`
Expected: All PASS (no markup changed, only CSS — this confirms nothing else regressed).

- [ ] **Step 4: Commit**

```bash
git add static/css/prescription-print.css
git commit -m "style: fix print layout for the sidebar shell and rebrand prescription print to indigo"
```

---

### Task 5: Staff List page tokens

**Files:**
- Modify: `static/css/staff_list.css`
- Test: `tests/test_staff.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `--clinic-accent`, `--clinic-content-bg` from Task 1.

- [ ] **Step 1: Swap the hardcoded blue accent for the indigo token**

In `static/css/staff_list.css`, replace:

```css
.staff-id {
  color: #0d6efd;
  font-weight: 700;
  white-space: nowrap;
}
```

with:

```css
.staff-id {
  color: var(--clinic-accent);
  font-weight: 700;
  white-space: nowrap;
}
```

Replace:

```css
.staff-mobile-card-id {
  margin: 0.2rem 0 0;
  color: #0d6efd;
  font-size: 0.825rem;
  font-weight: 700;
}
```

with:

```css
.staff-mobile-card-id {
  margin: 0.2rem 0 0;
  color: var(--clinic-accent);
  font-size: 0.825rem;
  font-weight: 700;
}
```

- [ ] **Step 2: Swap the row-hover tint to the shared content-background token**

Replace:

```css
.staff-table tbody tr:hover {
  background: #f4f8ff;
}
```

with:

```css
.staff-table tbody tr:hover {
  background: var(--clinic-content-bg);
}
```

- [ ] **Step 3: Run the staff test suite**

Run: `python -m pytest tests/test_staff.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add static/css/staff_list.css
git commit -m "style: apply Modern Slate accent to the staff list page"
```

---

### Task 6: Staff Create (admin form) page tokens

**Files:**
- Modify: `static/css/staff_create.css`
- Test: `tests/test_staff.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `--clinic-accent`, `--clinic-accent-soft` from Task 1.

- [ ] **Step 1: Swap the hover-accent color**

In `static/css/staff_create.css`, replace:

```css
.admin-back-link:hover {
  color: #0d6efd;
  text-decoration: underline;
}
```

with:

```css
.admin-back-link:hover {
  color: var(--clinic-accent);
  text-decoration: underline;
}
```

Replace:

```css
.admin-back-link:hover span:first-child {
  color: #0d6efd;
}
```

with:

```css
.admin-back-link:hover span:first-child {
  color: var(--clinic-accent);
}
```

- [ ] **Step 2: Swap the input focus ring to the indigo token**

Replace:

```css
.form-field input:focus,
.form-field select:focus {
  outline: none;
  border-color: #86b7fe;
  box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.15);
}
```

with:

```css
.form-field input:focus,
.form-field select:focus {
  outline: none;
  border-color: var(--clinic-accent-soft);
  box-shadow: 0 0 0 0.2rem rgba(99, 102, 241, 0.15);
}
```

- [ ] **Step 3: Run the staff test suite**

Run: `python -m pytest tests/test_staff.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add static/css/staff_create.css
git commit -m "style: apply Modern Slate accent to the staff create form"
```

---

### Task 7: Staff View (detail) page tokens

**Files:**
- Modify: `static/css/staff_view.css`
- Test: `tests/test_staff.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `--clinic-accent` from Task 1.

- [ ] **Step 1: Swap the avatar accent color**

In `static/css/staff_view.css`, replace:

```css
.staff-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #e7f1ff;
  color: #0d6efd;
  font-weight: 800;
  font-size: 1.25rem;
}
```

with:

```css
.staff-avatar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #e0e7ff;
  color: var(--clinic-accent);
  font-weight: 800;
  font-size: 1.25rem;
}
```

- [ ] **Step 2: Run the staff test suite**

Run: `python -m pytest tests/test_staff.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add static/css/staff_view.css
git commit -m "style: apply Modern Slate accent to the staff detail page"
```

---

### Task 8: Reports dashboard tokens (CSS + chart canvas colors)

**Files:**
- Modify: `static/css/reports-dashboard.css`
- Modify: `static/js/reports-dashboard.js:333-334,380,398`
- Test: `tests/test_reports.py` (existing suite, run as regression check)

**Interfaces:**
- Consumes: `--clinic-accent`, `--clinic-table-header-text` from Task 1 (the `.js` file draws to a `<canvas>`, which can't read CSS custom properties directly, so its colors are hardcoded to the same hex values as the tokens for consistency).

- [ ] **Step 1: Swap the KPI card gradient from blue to indigo**

In `static/css/reports-dashboard.css`, replace:

```css
.reports-kpi-card {
  border: 0;
  background: linear-gradient(145deg, #17395c, #2463a8);
  color: #ffffff;
}
```

with:

```css
.reports-kpi-card {
  border: 0;
  background: linear-gradient(145deg, #312e81, #4f46e5);
  color: #ffffff;
}
```

- [ ] **Step 2: Swap the range banner from blue to indigo**

Replace:

```css
.reports-range-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  padding: 1rem 1.25rem;
  border: 1px solid #b9d2eb;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #eff6fc, #ffffff);
  color: #24425f;
}

.reports-range-banner span {
  color: #5a7086;
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
```

with:

```css
.reports-range-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
  padding: 1rem 1.25rem;
  border: 1px solid #c7d2fe;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #eef2ff, #ffffff);
  color: #312e81;
}

.reports-range-banner span {
  color: #4338ca;
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
```

- [ ] **Step 3: Swap the chart's hardcoded canvas colors**

In `static/js/reports-dashboard.js`, replace line 333:

```javascript
    chartContext.strokeStyle = "#d9e2ec";
```

with:

```javascript
    chartContext.strokeStyle = "#e2e8f0";
```

Replace line 334:

```javascript
    chartContext.fillStyle = "#62778b";
```

with:

```javascript
    chartContext.fillStyle = "#475569";
```

Replace line 380:

```javascript
      chartContext.fillStyle = "#2463a8";
```

with:

```javascript
      chartContext.fillStyle = "#4f46e5";
```

Replace line 398:

```javascript
        chartContext.fillStyle = "#62778b";
```

with:

```javascript
        chartContext.fillStyle = "#475569";
```

- [ ] **Step 4: Run the reports test suite**

Run: `python -m pytest tests/test_reports.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add static/css/reports-dashboard.css static/js/reports-dashboard.js
git commit -m "style: apply Modern Slate indigo to the reports dashboard and chart"
```

---

### Task 9: Fix the pre-existing navbar-markup test assertion

**Files:**
- Modify: `tests/test_pharmacy.py:368`

**Interfaces:**
- Consumes: `.sidebar-link` markup contract from Task 2.

**Context:** This is the one test in the whole suite that asserts on literal navbar HTML (`<a class="nav-link" href="/pharmacy">Pharmacy</a>`). It started failing as soon as Task 2 landed the sidebar markup and has been failing since — this task fixes it.

- [ ] **Step 1: Update the assertion to match the sidebar link markup**

In `tests/test_pharmacy.py`, replace:

```python
    assert '<a class="nav-link" href="/pharmacy">Pharmacy</a>' in response.text
```

with:

```python
    assert '<a class="sidebar-link" href="/pharmacy">Pharmacy</a>' in response.text
```

- [ ] **Step 2: Run the pharmacy test suite**

Run: `python -m pytest tests/test_pharmacy.py -v`
Expected: All PASS

- [ ] **Step 3: Run the full suite one more time to confirm zero regressions across the whole redesign**

Run: `python -m pytest -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_pharmacy.py
git commit -m "test: update pharmacy nav assertion for the sidebar shell"
```

---

### Task 10: Manual cross-role visual verification

**Files:** none (verification only)

**Interfaces:** none

- [ ] **Step 1: Start the app**

Run: `uvicorn agile_ci_demo.app:app --reload` (or the project's existing `Makefile`/`docker-compose` run target if preferred)

- [ ] **Step 2: Walk through each role in a browser**

For each of receptionist, nurse, admin, doctor, and patient: log in, confirm the sidebar shows the right links highlighted correctly for the active page, and open at least one page per feature area that role can reach (patients list/detail, appointment booking/schedule, consultation start/detail, pharmacy, prescription print preview, reports dashboard, staff list/create/view as admin).

- [ ] **Step 3: Check the login/forgot/reset password pages**

Confirm they render the centered card on the slate background with no sidebar, and that logging in correctly lands on the sidebar shell.

- [ ] **Step 4: Check the mobile collapse**

Resize the browser to a small viewport (or use dev-tools device emulation) and confirm the hamburger toggle shows/hides the sidebar correctly on at least one page.

- [ ] **Step 5: Print-preview a prescription**

Open a prescription print page and use the browser's print preview to confirm the sidebar and hamburger button are hidden and the prescription sheet uses the full page width.

- [ ] **Step 6: Report findings**

If anything looks wrong, note which page/role/viewport and what's off — that becomes a small follow-up fix, not a plan revision (all the structural work is already done and tested by this point).

---

## Self-Review Notes

- **Spec coverage:** every item in the design doc's "Component Styles" and "Layout Architecture" sections maps to a task — design tokens (Task 1), sidebar shell + mobile collapse (Task 2), auth shell (Task 3, verification only since Task 2 already implements it), print page (Task 4), and every CSS file with hardcoded brand colors (Tasks 5–8). The "Role → nav items" table is implemented verbatim in Task 2 and locked in by its tests.
- **Templates needing no changes:** confirmed by grep that only 6 of 24 templates load page-specific CSS; the other 18 (patients, appointments, consultations, pharmacy) inherit the redesign entirely through `base.html` and `app.css` with zero template edits, which is why there's no task touching them individually.
- **Type/class consistency:** `sidebar-link` / `sidebar-link active` (space-separated, matching Bootstrap's own convention) is used identically in Task 2's implementation, Task 2/3's tests, and Task 9's fixed assertion.
- **Known pre-existing failure:** Task 2's Step 7 explicitly calls out that `test_pharmacy.py`'s navbar assertion will be the only failure until Task 9 — this isn't a plan bug, it's flagged so whoever executes the plan doesn't stop and investigate a false alarm.
