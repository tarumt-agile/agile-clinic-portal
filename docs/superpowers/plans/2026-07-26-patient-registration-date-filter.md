# Filter Patient List by Registration Date Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a receptionist narrow the patient list by registration date, combined with the existing name/patient-ID search.

**Architecture:** `search_patients()` gains two optional date parameters filtering the existing `Patient.created_at` column; `GET /api/patients` exposes them as query params; the patient list page gets two date inputs plus a "Registered on" column, following the exact pattern the existing search box already uses.

**Tech Stack:** FastAPI, SQLAlchemy (SQLite), Jinja2 templates, vanilla JS, pytest.

## Global Constraints

- Commit messages: plain-language, non-technical (this is graded university coursework read by non-technical reviewers).
- Commit directly - never add a `Co-Authored-By` trailer or any AI-attribution line to any commit.
- Keep code as simple as possible: no new libraries, no new endpoints beyond the two new query parameters on the existing `GET /api/patients`.
- Full check suite (`ruff check . && black --check . && mypy src && pytest --disable-warnings -q`) must pass before every commit.
- A date range with `registered_from` after `registered_to` needs no special handling - it naturally returns zero rows.

---

### Task 1: Backend - registered_from/registered_to filtering

**Files:**
- Modify: `src/agile_ci_demo/patients/service.py`
- Modify: `src/agile_ci_demo/patients/router.py`
- Test: `tests/test_patients.py`

**Interfaces:**
- Produces: `search_patients(db, query, page, page_size, registered_from: dt.date | None = None, registered_to: dt.date | None = None) -> tuple[list[Patient], int]` - Task 2 doesn't consume this directly (it's a frontend-only task calling the already-updated API), but this is the signature the router now calls.

- [ ] **Step 1: Write the failing tests**

In `tests/test_patients.py`, add (these build their own isolated in-memory database and call
`search_patients` directly, bypassing the `client` fixture, because they need to set exact
`created_at` timestamps that the registration API doesn't allow the caller to control):

```python
def _build_isolated_patients_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from agile_ci_demo.core.database import Base
    import agile_ci_demo.patients.models  # noqa: F401 - registers Patient with Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _make_patient(patient_id: str, full_name: str, created_at: dt.datetime):
    from agile_ci_demo.patients.models import Patient

    return Patient(
        patient_id=patient_id,
        full_name=full_name,
        date_of_birth=dt.date(1990, 1, 1),
        gender="female",
        phone_number="012-0000000",
        ic_or_passport=f"900101-01-{patient_id[-4:]}",
        created_at=created_at,
    )


def test_search_patients_filters_by_registered_from() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all([
        _make_patient("P00001", "Old Patient", dt.datetime(2026, 1, 1, 10, 0, 0)),
        _make_patient("P00002", "New Patient", dt.datetime(2026, 1, 15, 10, 0, 0)),
    ])
    db.commit()

    items, total = search_patients(db, None, 1, 10, registered_from=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00002"
    db.close()


def test_search_patients_filters_by_registered_to() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all([
        _make_patient("P00001", "Old Patient", dt.datetime(2026, 1, 1, 10, 0, 0)),
        _make_patient("P00002", "New Patient", dt.datetime(2026, 1, 15, 10, 0, 0)),
    ])
    db.commit()

    items, total = search_patients(db, None, 1, 10, registered_to=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()


def test_search_patients_registered_from_and_to_are_inclusive_of_the_whole_day() -> None:
    """A patient registered at 23:59 on the boundary date must still match when that
    same date is used for both registered_from and registered_to - the range must
    cover the whole day, not just midnight."""
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add(_make_patient("P00001", "Late Patient", dt.datetime(2026, 1, 10, 23, 59, 0)))
    db.commit()

    items, total = search_patients(
        db, None, 1, 10, registered_from=dt.date(2026, 1, 10), registered_to=dt.date(2026, 1, 10)
    )
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()


def test_search_patients_inverted_date_range_returns_empty() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add(_make_patient("P00001", "Some Patient", dt.datetime(2026, 1, 10, 10, 0, 0)))
    db.commit()

    items, total = search_patients(
        db, None, 1, 10, registered_from=dt.date(2026, 1, 15), registered_to=dt.date(2026, 1, 1)
    )
    assert total == 0
    assert items == []
    db.close()


def test_search_patients_combines_date_range_with_text_query() -> None:
    from agile_ci_demo.patients.service import search_patients

    db = _build_isolated_patients_db()
    db.add_all([
        _make_patient("P00001", "Jane Tan", dt.datetime(2026, 1, 15, 10, 0, 0)),
        _make_patient("P00002", "Jane Wong", dt.datetime(2026, 1, 1, 10, 0, 0)),
    ])
    db.commit()

    items, total = search_patients(db, "jane", 1, 10, registered_from=dt.date(2026, 1, 10))
    assert total == 1
    assert items[0].patient_id == "P00001"
    db.close()
```

Also add two tests at the API level, using the normal `client` fixture, confirming the query
params round-trip correctly (these don't need to control exact timestamps, since every patient
registered in a fresh test database is registered "now"):

```python
def test_list_patients_registered_today_matches_when_filtered_to_today(client: TestClient) -> None:
    from datetime import date

    _register_sample_patients(client)
    today = date.today().isoformat()

    r = client.get("/api/patients", params={"registered_from": today, "registered_to": today})
    assert r.status_code == 200
    assert r.json()["total"] == 4


def test_list_patients_registered_today_excluded_when_filtered_to_yesterday(
    client: TestClient,
) -> None:
    from datetime import date, timedelta

    _register_sample_patients(client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    r = client.get("/api/patients", params={"registered_to": yesterday})
    assert r.status_code == 200
    assert r.json()["total"] == 0
```

At the top of `tests/test_patients.py`, confirm `import datetime as dt` is present (it already is,
used by other tests in this file) - the new tests above rely on it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_patients.py -v -k "registered_from or registered_to or registered_today or inverted_date or combines_date"`
Expected: FAIL - `search_patients()` doesn't accept `registered_from`/`registered_to` yet
(`TypeError: search_patients() got an unexpected keyword argument`), and the API-level tests get
`total == 4` regardless of the date filter since it's silently ignored (query params FastAPI
doesn't know about are simply dropped, not errors).

- [ ] **Step 3: Add the filtering to search_patients**

In `src/agile_ci_demo/patients/service.py`, add `import datetime as dt` to the top of the file if
not already present (check first - `generate_ic` already uses `dt.date`, so it should already be
imported).

Change `search_patients`:

```python
def search_patients(
    db: Session, query: str | None, page: int, page_size: int
) -> tuple[list[Patient], int]:
    """Search patients by name or patient_id (case-insensitive, partial match).

    Returns (page of results ordered by registration order, total matching count).
    """
    conditions = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        conditions.append(or_(Patient.full_name.ilike(pattern), Patient.patient_id.ilike(pattern)))

    count_stmt = select(func.count()).select_from(Patient)
    items_stmt = select(Patient).order_by(Patient.id)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        items_stmt = items_stmt.where(condition)

    total = db.execute(count_stmt).scalar_one()
    items_stmt = items_stmt.offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(items_stmt).scalars().all())
    return items, total
```

to:

```python
def search_patients(
    db: Session,
    query: str | None,
    page: int,
    page_size: int,
    registered_from: dt.date | None = None,
    registered_to: dt.date | None = None,
) -> tuple[list[Patient], int]:
    """Search patients by name or patient_id (case-insensitive, partial match), optionally
    narrowed to a registration date range.

    Returns (page of results ordered by registration order, total matching count).
    """
    conditions = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        conditions.append(or_(Patient.full_name.ilike(pattern), Patient.patient_id.ilike(pattern)))
    if registered_from is not None:
        conditions.append(Patient.created_at >= dt.datetime.combine(registered_from, dt.time.min))
    if registered_to is not None:
        conditions.append(Patient.created_at <= dt.datetime.combine(registered_to, dt.time.max))

    count_stmt = select(func.count()).select_from(Patient)
    items_stmt = select(Patient).order_by(Patient.id)
    for condition in conditions:
        count_stmt = count_stmt.where(condition)
        items_stmt = items_stmt.where(condition)

    total = db.execute(count_stmt).scalar_one()
    items_stmt = items_stmt.offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(items_stmt).scalars().all())
    return items, total
```

- [ ] **Step 4: Add the query parameters to the API endpoint**

In `src/agile_ci_demo/patients/router.py`, add `import datetime as dt` to the top of the file
(not currently imported - the file currently starts with `from math import ceil`).

Change `list_patients`:

```python
@api_router.get("", response_model=PaginatedPatients)
def list_patients(
    q: str | None = Query(default=None, description="Search by name or patient ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedPatients:
    items, total = search_patients(db, q, page, page_size)
    total_pages = max(1, ceil(total / page_size))
    return PaginatedPatients(
        items=[PatientOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
```

to:

```python
@api_router.get("", response_model=PaginatedPatients)
def list_patients(
    q: str | None = Query(default=None, description="Search by name or patient ID"),
    registered_from: dt.date | None = Query(
        default=None, description="Only include patients registered on or after this date"
    ),
    registered_to: dt.date | None = Query(
        default=None, description="Only include patients registered on or before this date"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedPatients:
    items, total = search_patients(db, q, page, page_size, registered_from, registered_to)
    total_pages = max(1, ceil(total / page_size))
    return PaginatedPatients(
        items=[PatientOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_patients.py -v -k "registered_from or registered_to or registered_today or inverted_date or combines_date"`
Expected: PASS

- [ ] **Step 6: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/patients/service.py src/agile_ci_demo/patients/router.py tests/test_patients.py
git commit -m "Let the patient list be filtered by registration date"
```

---

### Task 2: Frontend - date filter fields and Registered On column

**Files:**
- Modify: `templates/patients/receptionist_viewPatients.html`
- Modify: `static/js/patients_list.js`

**Interfaces:**
- Consumes: `GET /api/patients` with `registered_from`/`registered_to` query params (Task 1);
  `PatientOut.created_at` (already present on every item in the response, an ISO datetime string
  like `"2026-01-15T10:00:00"`).

- [ ] **Step 1: Add the date input fields and table column**

In `templates/patients/receptionist_viewPatients.html`, change the card header (currently just the
search box):

```html
  <div class="card-header">
    <label for="search-input" class="visually-hidden">Search by name or patient ID</label>
    <input
      type="search"
      id="search-input"
      class="form-control"
      placeholder="Search by name or patient ID (e.g. Jane or P00001)"
      autocomplete="off"
    >
  </div>
```

to:

```html
  <div class="card-header">
    <div class="row g-2 align-items-end">
      <div class="col-md-6">
        <label for="search-input" class="form-label">Search by name or patient ID</label>
        <input
          type="search"
          id="search-input"
          class="form-control"
          placeholder="e.g. Jane or P00001"
          autocomplete="off"
        >
      </div>
      <div class="col-md-3">
        <label for="registered-from-input" class="form-label">Registered from</label>
        <input type="date" id="registered-from-input" class="form-control">
      </div>
      <div class="col-md-3">
        <label for="registered-to-input" class="form-label">Registered to</label>
        <input type="date" id="registered-to-input" class="form-control">
      </div>
    </div>
  </div>
```

Change the table header row:

```html
        <tr>
          <th scope="col">Patient ID</th>
          <th scope="col">Full name</th>
          <th scope="col">Gender</th>
          <th scope="col">Phone</th>
          <th scope="col">Date of birth</th>
        </tr>
```

to:

```html
        <tr>
          <th scope="col">Patient ID</th>
          <th scope="col">Full name</th>
          <th scope="col">Gender</th>
          <th scope="col">Phone</th>
          <th scope="col">Date of birth</th>
          <th scope="col">Registered on</th>
        </tr>
```

Update the loading/empty-state placeholder rows' `colspan` from `5` to `6` (there are two such
rows in this file - the initial "Loading..." row and the "No patients found." row rendered by
`patients_list.js`, though the JS-rendered one lives in the JS file, not this template; in this
template only the initial `<tbody>` "Loading..." row needs its `colspan` updated):

```html
      <tbody id="patients-table-body">
        <tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>
      </tbody>
```

to:

```html
      <tbody id="patients-table-body">
        <tr><td colspan="6" class="text-center text-muted py-4">Loading...</td></tr>
      </tbody>
```

- [ ] **Step 2: Wire up the JS**

In `static/js/patients_list.js`, add the two new input refs after `searchInput`:

```javascript
  const searchInput = document.getElementById("search-input");
  const registeredFromInput = document.getElementById("registered-from-input");
  const registeredToInput = document.getElementById("registered-to-input");
```

Change the `state` object:

```javascript
  let state = { query: "", page: 1 };
```

to:

```javascript
  let state = { query: "", registeredFrom: "", registeredTo: "", page: 1 };
```

In `loadPatients`, change the `URLSearchParams` construction:

```javascript
    const params = new URLSearchParams({
      page: String(state.page),
      page_size: String(pageSize),
    });
    if (state.query) params.set("q", state.query);
```

to:

```javascript
    const params = new URLSearchParams({
      page: String(state.page),
      page_size: String(pageSize),
    });
    if (state.query) params.set("q", state.query);
    if (state.registeredFrom) params.set("registered_from", state.registeredFrom);
    if (state.registeredTo) params.set("registered_to", state.registeredTo);
```

Also update the "Loading..."/"No patients found." colspans inside this file from `5` to `6`:

```javascript
    tableBody.innerHTML =
      '<tr><td colspan="5" class="text-center text-muted py-4">Loading...</td></tr>';
```

to:

```javascript
    tableBody.innerHTML =
      '<tr><td colspan="6" class="text-center text-muted py-4">Loading...</td></tr>';
```

and:

```javascript
      tableBody.innerHTML =
        '<tr><td colspan="5" class="text-center text-muted py-4">No patients found.</td></tr>';
```

to:

```javascript
      tableBody.innerHTML =
        '<tr><td colspan="6" class="text-center text-muted py-4">No patients found.</td></tr>';
```

Change `renderTable`'s row template:

```javascript
    tableBody.innerHTML = items
      .map(
        (p) => `
      <tr class="patient-row" role="button" data-patient-id="${escapeHtml(p.patient_id)}">
        <td class="fw-semibold">${escapeHtml(p.patient_id)}</td>
        <td>${escapeHtml(p.full_name)}</td>
        <td class="text-capitalize">${escapeHtml(p.gender)}</td>
        <td>${escapeHtml(p.phone_number)}</td>
        <td>${escapeHtml(p.date_of_birth)}</td>
      </tr>`
      )
      .join("");
```

to:

```javascript
    tableBody.innerHTML = items
      .map(
        (p) => `
      <tr class="patient-row" role="button" data-patient-id="${escapeHtml(p.patient_id)}">
        <td class="fw-semibold">${escapeHtml(p.patient_id)}</td>
        <td>${escapeHtml(p.full_name)}</td>
        <td class="text-capitalize">${escapeHtml(p.gender)}</td>
        <td>${escapeHtml(p.phone_number)}</td>
        <td>${escapeHtml(p.date_of_birth)}</td>
        <td>${escapeHtml((p.created_at || "").slice(0, 10))}</td>
      </tr>`
      )
      .join("");
```

Add event listeners for the two new date fields, right after the existing `searchInput` listener:

```javascript
  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.query = searchInput.value.trim();
      state.page = 1;
      loadPatients();
    }, 300);
  });

  registeredFromInput.addEventListener("input", () => {
    state.registeredFrom = registeredFromInput.value;
    state.page = 1;
    loadPatients();
  });

  registeredToInput.addEventListener("input", () => {
    state.registeredTo = registeredToInput.value;
    state.page = 1;
    loadPatients();
  });

  loadPatients();
```

(the two new listeners don't need the debounce timer the search box uses - a native
`<input type="date">` only fires its `input` event once a complete date is picked or cleared, not
per keystroke, so there's no rapid-fire typing to debounce.)

- [ ] **Step 3: Run the full check suite**

Run: `ruff check . && black --check . && mypy src && pytest --disable-warnings -q`
Expected: all pass (this task touches no Python, so this just confirms nothing else broke).

- [ ] **Step 4: Manual browser check**

Start the dev server, log in as receptionist, open `/patients`. Confirm: the "Registered on"
column shows a date for every row, picking a "Registered from" date in the future shows zero
results, clearing it restores the full list, picking a narrow "Registered from"/"Registered to"
range that includes today shows today's patients, and combining a name search with a date range
narrows results as expected (e.g. search "Jane" plus a date range that excludes her registration
date returns nothing).

- [ ] **Step 5: Commit**

```bash
git add templates/patients/receptionist_viewPatients.html static/js/patients_list.js
git commit -m "Show a Registered On column and let the patient list be filtered by date"
```

---

## Self-Review Notes

- **Spec coverage:** backend filtering with inclusive whole-day boundaries (Task 1), API query
  params (Task 1), date input fields plus Registered On column composing with the existing search
  (Task 2). All design sections are covered. The spec's "no special validation for an inverted
  range" decision is directly tested (`test_search_patients_inverted_date_range_returns_empty`)
  rather than just asserted in prose.
- **Placeholder scan:** no TBDs; every step has complete, runnable code.
- **Type consistency:** `search_patients(db, query, page, page_size, registered_from:
  dt.date | None = None, registered_to: dt.date | None = None)` is defined once in Task 1 and
  called with the same parameter names and order at its one call site in `list_patients`
  (`router.py`). Task 2 doesn't call `search_patients` directly - it only consumes the JSON shape
  `list_patients` already returns (`PatientOut.created_at`), which is unchanged by this plan (that
  field already existed).
