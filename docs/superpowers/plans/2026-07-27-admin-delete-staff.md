# Admin Delete Staff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin permanently delete a staff account from the staff detail page, per [2026-07-27-admin-delete-staff-design.md](../specs/2026-07-27-admin-delete-staff-design.md).

**Architecture:** A new `DELETE /api/staff/{staff_id}` endpoint, admin-only via the existing `require_role(Role.ADMIN)` dependency, calling a new `delete_staff` service function that hard-deletes the row (doctor profiles cascade automatically via the existing SQLAlchemy relationship). The staff detail page gets a red "Delete Staff" button and a confirmation modal.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Jinja2, Bootstrap 5 (vanilla JS), pytest.

## Global Constraints

- Admin only, no exceptions — same `require_role(Role.ADMIN)` guard already used on `PATCH /api/staff/{staff_id}/status` and `PATCH /api/staff/{staff_id}`. A non-admin or logged-out request is redirected to `/auth/login` (303) before ever reaching the delete logic.
- Hard delete — the row is actually removed, not deactivated. A doctor's `DoctorProfile` is removed too via the existing `cascade="all, delete-orphan"` on `Staff.doctor_profile` — no new cascade code needed.
- No blocking checks against appointment/record/prescription history.
- An admin cannot delete their own account — 400 if the target `staff_id` matches the logged-in admin's own `staff_id`.
- Delete button lives on the staff detail page (`templates/staff/staff_view.html`) only, not the list page.

---

### Task 1: Backend delete endpoint

**Files:**
- Modify: `src/agile_ci_demo/staff/service.py`
- Modify: `src/agile_ci_demo/staff/router.py`
- Test: `tests/test_staff.py`

**Interfaces:**
- Produces: `staff.service.delete_staff(db: Session, staff_id: str) -> None` (raises `StaffNotFoundError` if the `staff_id` doesn't exist — this exception already exists in this file)
- Produces: `DELETE /api/staff/{staff_id}` — 204 on success, 400 if deleting your own account, 404 if the `staff_id` doesn't exist, 303 redirect if not logged in as admin

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_staff.py`, after `test_deactivate_staff_rejects_a_non_admin_login` (end of file):

```python
# --- Delete staff -------------------------------------------------------------


def test_delete_staff_success(client: TestClient) -> None:
    """
    Scenario: Admin permanently deletes a staff account
      Given a staff account exists
      When I DELETE /api/staff/{staff_id}
      Then it's gone - a subsequent GET returns 404
    """
    _login_as_admin(client)
    created = client.post("/api/staff", json=valid_staff_payload()).json()

    r = client.delete(f"/api/staff/{created['staff_id']}")
    assert r.status_code == 204

    r = client.get(f"/api/staff/{created['staff_id']}")
    assert r.status_code == 404


def test_delete_doctor_also_removes_their_doctor_profile(client: TestClient) -> None:
    """Deleting a doctor's staff account cascades to their DoctorProfile too."""
    _login_as_admin(client)
    created = client.post(
        "/api/staff",
        json=valid_staff_payload(
            role="doctor",
            license_number="MMC-12345",
            specialty="General Medicine",
            status="active",
        ),
    ).json()

    r = client.delete(f"/api/staff/{created['staff_id']}")
    assert r.status_code == 204

    doctors = client.get("/api/staff/doctor").json()
    assert all(d["staff_id"] != created["staff_id"] for d in doctors)


def test_delete_unknown_staff_returns_404(client: TestClient) -> None:
    _login_as_admin(client)
    r = client.delete("/api/staff/S99999")
    assert r.status_code == 404


def test_delete_staff_blocks_deleting_your_own_account(client: TestClient) -> None:
    """An admin cannot delete the account they're currently logged in as."""
    from test_auth import _create_staff_and_get_temp_password

    temp_password = _create_staff_and_get_temp_password(
        client, email="admin@example.com", role="admin"
    )
    login_body = client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": temp_password}
    ).json()
    admin_staff_id = login_body["staff_id"]

    r = client.delete(f"/api/staff/{admin_staff_id}")
    assert r.status_code == 400

    r = client.get(f"/api/staff/{admin_staff_id}")
    assert r.status_code == 200


def test_delete_staff_requires_admin_login(client: TestClient) -> None:
    """Matches the existing pattern for PATCH .../status: no session -> redirect to login."""
    created = client.post("/api/staff", json=valid_staff_payload()).json()

    r = client.delete(f"/api/staff/{created['staff_id']}", follow_redirects=False)
    assert r.status_code == 303
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staff.py -k delete_staff -v`
Expected: FAIL with 405 Method Not Allowed (no `DELETE /api/staff/{staff_id}` route exists yet).

- [ ] **Step 3: Add `delete_staff` to `staff/service.py`**

Add after `set_staff_active_status` (which already exists in this file):

```python
def delete_staff(db: Session, staff_id: str) -> None:
    """Permanently remove a staff account (and its doctor profile, if any)."""
    staff = get_staff_by_staff_id(db, staff_id)
    if staff is None:
        raise StaffNotFoundError(f"No staff account found with staff_id '{staff_id}'")
    db.delete(staff)
    db.commit()
```

`get_staff_by_staff_id` and `StaffNotFoundError` already exist in this file - no new imports needed.

- [ ] **Step 4: Add the endpoint to `staff/router.py`**

Add `delete_staff` to the existing `from agile_ci_demo.staff.service import (...)` import block. Add the endpoint after `update_staff_status` (the `PATCH /{staff_id}/status` handler):

```python
# This route permanently deletes a staff account.
@api_router.delete(
    "/{staff_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_staff_endpoint(
    staff_id: str,
    db: Session = Depends(get_db),
    admin: Staff = Depends(require_role(Role.ADMIN)),
) -> None:
    if staff_id == admin.staff_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    try:
        delete_staff(db, staff_id)
    except StaffNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
```

`Staff`, `Role`, `require_role`, `HTTPException`, `status`, `Depends`, `get_db` are all already imported in this file.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest tests/test_staff.py -v`
Expected: PASS (all tests in the file, including the new delete ones).

- [ ] **Step 6: Run mypy and ruff**

Run: `.venv/Scripts/python.exe -m mypy src` and `.venv/Scripts/python.exe -m ruff check .`
Expected: both clean (no new errors).

- [ ] **Step 7: Commit**

```bash
git add src/agile_ci_demo/staff/service.py src/agile_ci_demo/staff/router.py tests/test_staff.py
git commit -m "Add DELETE /api/staff/{staff_id} for admin to permanently remove a staff account"
```

---

### Task 2: Delete button + confirmation modal on the staff detail page

**Files:**
- Modify: `templates/staff/staff_view.html`
- Modify: `static/js/staff_view.js`

**Interfaces:**
- Consumes: `DELETE /api/staff/{staff_id}` (from Task 1) — 204 success, 400 self-delete, 404 not found

- [ ] **Step 1: Add the Delete button and confirmation modal**

In `templates/staff/staff_view.html`, add a "Delete Staff" button next to the existing "Edit Staff" button. Replace:

```html
    <button
      type="button"
      id="edit-staff-button"
      class="btn btn-primary d-none"
    >
      Edit Staff
    </button>
  </header>
```

with:

```html
    <div class="staff-detail-header-actions">
      <button
        type="button"
        id="edit-staff-button"
        class="btn btn-primary d-none"
      >
        Edit Staff
      </button>

      <button
        type="button"
        id="delete-staff-button"
        class="btn btn-danger d-none"
      >
        Delete Staff
      </button>
    </div>
  </header>
```

Add the confirmation modal right before the final `{% endblock %}` of the content block (after the closing `</div>` of `staff-detail-root`):

```html
<div
  class="modal fade"
  id="delete-staff-modal"
  tabindex="-1"
  aria-labelledby="delete-staff-modal-title"
  aria-hidden="true"
>
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">

      <div class="modal-header">
        <h2
          id="delete-staff-modal-title"
          class="modal-title fs-5"
        >
          Delete Staff Account
        </h2>

        <button
          type="button"
          class="btn-close"
          data-bs-dismiss="modal"
          aria-label="Close"
        ></button>
      </div>

      <div class="modal-body">
        <p>Delete this staff account permanently? This cannot be undone.</p>

        <div
          id="delete-staff-modal-alert"
          class="alert alert-danger d-none"
          role="alert"
        ></div>
      </div>

      <div class="modal-footer">
        <button
          type="button"
          class="btn btn-outline-secondary"
          data-bs-dismiss="modal"
        >
          Cancel
        </button>

        <button
          type="button"
          id="confirm-delete-staff-button"
          class="btn btn-danger"
        >
          Delete
        </button>
      </div>
    </div>
  </div>
</div>
```

This mirrors the existing (currently unused) `#staff-status-modal` structure already in `templates/staff/staff_list.html` - same Bootstrap classes, same layout.

- [ ] **Step 2: Wire up the button and modal in `static/js/staff_view.js`**

Add near the top of the file, alongside the other `byId(...)` constant lookups (after the existing `endTimeInput` declaration, before `let currentStaff = null;`):

```js
  const deleteButton = byId("delete-staff-button");
  const deleteModalAlert = byId("delete-staff-modal-alert");
```

Add at the end of the file, right before the final `loadStaff();` call:

```js
  deleteButton.addEventListener("click", function () {
    deleteModalAlert.classList.add("d-none");
    deleteModalAlert.textContent = "";

    const modalElement = byId("delete-staff-modal");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    modal.show();
  });

  byId("confirm-delete-staff-button").addEventListener(
    "click",
    async function () {
      const confirmButton = byId("confirm-delete-staff-button");
      confirmButton.disabled = true;

      try {
        const response = await fetch(
          "/api/staff/" + encodeURIComponent(staffId),
          { method: "DELETE" }
        );

        if (response.status === 204) {
          window.location.href = "/staff";
          return;
        }

        const result = await response.json();
        deleteModalAlert.textContent =
          typeof result.detail === "string"
            ? result.detail
            : "This staff account could not be deleted.";
        deleteModalAlert.classList.remove("d-none");

      } catch (error) {
        deleteModalAlert.textContent =
          "Unable to reach the server. Please try again.";
        deleteModalAlert.classList.remove("d-none");

      } finally {
        confirmButton.disabled = false;
      }
    }
  );
```

Also update `renderStaff(staff)` to reveal the delete button alongside the edit button - find this existing block near the end of `renderStaff`:

```js
    byId(
      "edit-staff-button"
    ).classList.remove("d-none");
```

and change it to:

```js
    byId(
      "edit-staff-button"
    ).classList.remove("d-none");

    deleteButton.classList.remove("d-none");
```

- [ ] **Step 3: Manually verify in the browser**

Start the dev server if not already running, log in as admin, open a staff member's detail page (`/staff/{staff_id}`), confirm the red "Delete Staff" button appears next to "Edit Staff". Click it, confirm the modal opens with the warning text. Click Cancel, confirm the modal closes and nothing happens. Click Delete again, confirm, and confirm you're redirected to `/staff` and the deleted account no longer appears in the list.

Then test the two error paths: try deleting your own logged-in admin account (should show the "You cannot delete your own account." error in the modal, without redirecting), and manually hit a stale/already-deleted `staff_id` URL and confirm the delete attempt shows a 404-based error rather than crashing the page.

- [ ] **Step 4: Commit**

```bash
git add templates/staff/staff_view.html static/js/staff_view.js
git commit -m "Add Delete Staff button with confirmation modal on the staff detail page"
```
