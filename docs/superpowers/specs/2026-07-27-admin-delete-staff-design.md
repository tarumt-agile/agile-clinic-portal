# Admin delete staff - design

## Goal

Let an admin permanently remove a staff account. Today the only lifecycle action is
deactivate/reactivate (`is_active` toggle via the staff detail page's edit form) - there is no
way to actually remove a mistaken or test account from the system.

## Access control

**Admin only, no exceptions.** The new endpoint uses the same `require_role(Role.ADMIN)`
dependency already guarding `PATCH /api/staff/{staff_id}/status`, `PATCH /api/staff/{staff_id}`,
and the staff pages (`staff/router.py`). A non-admin or logged-out request never reaches the
delete logic - `require_role` raises `NotAuthenticatedError` first, which the app-wide handler
turns into a redirect to `/auth/login` (303), exactly like every other admin-only route today.

## Delete semantics

**Hard delete** - the staff row is removed from the database, not deactivated. If the staff
member is a doctor, their `DoctorProfile` is removed too: `Staff.doctor_profile` already has
`cascade="all, delete-orphan"` (`staff/models.py`), so no new cascade logic is needed.

No blocking checks against appointments/records/prescriptions history - this is meant for
cleaning up mistaken or test accounts, not for staff with a real clinical history. Rows in other
tables that reference the deleted staff (e.g. `appointments.doctor_id`, `records`,
`prescriptions`, this app's new `password_reset_tokens.staff_id`) are left as dangling
references; SQLite does not enforce foreign keys in this app (no `PRAGMA foreign_keys=ON`
anywhere), so this doesn't raise a DB error. Handling those dangling references is out of scope.

**Self-delete is blocked.** An admin cannot delete the account they are currently logged in as.
`require_role(Role.ADMIN)` already returns the logged-in admin's `Staff` object; the router
compares its `staff_id` against the target and rejects with 400 before calling into the service
layer.

## Backend

New `delete_staff(db: Session, staff_id: str) -> None` in `staff/service.py`:

```python
def delete_staff(db: Session, staff_id: str) -> None:
    """Permanently remove a staff account (and its doctor profile, if any)."""
    staff = get_staff_by_staff_id(db, staff_id)
    if staff is None:
        raise StaffNotFoundError(f"No staff account found with staff_id '{staff_id}'")
    db.delete(staff)
    db.commit()
```

Reuses the existing `StaffNotFoundError`. No new exception type needed - the self-delete check
is a router-level concern (it only needs the logged-in admin's ID, already available from the
`require_role` dependency), not a service-layer rule.

New endpoint in `staff/router.py`:

```python
@api_router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

## Frontend

`templates/staff/staff_view.html` gets a "Delete Staff" button (`btn btn-danger`) next to the
existing "Edit Staff" button, plus a confirmation modal - same Bootstrap structure as the (today
unused) `#staff-status-modal` in `staff_list.html`: a message, a Cancel button, and a red Confirm
button. Wording: "Delete this staff account permanently? This cannot be undone."

`static/js/staff_view.js` gets the click handlers: clicking "Delete Staff" opens the modal;
confirming sends `DELETE /api/staff/{staff_id}`, then on success redirects to `/staff` (the list
page reloads its own data on load, so no extra state needs passing); on failure (400 self-delete,
404 not found) shows the error in the existing `staff-detail-alert` box using the same
`showAlert`/`hideAlert` helpers already in the file, and closes the modal.

## Testing

New tests in `tests/test_staff.py`:

- Deleting a staff account succeeds (204) and a subsequent `GET /api/staff/{staff_id}` returns
  404.
- Deleting a doctor also removes their doctor profile (verify via `GET /api/staff/doctor` no
  longer listing them, or a direct DB check).
- An admin attempting to delete their own account gets 400 and the account still exists
  afterward.
- Deleting an unknown `staff_id` returns 404.
- A request without an admin session (no login, or logged in as a non-admin role) is redirected
  to `/auth/login` (303), never reaching the delete logic - matches the existing pattern already
  tested for `PATCH /api/staff/{staff_id}/status`.

## Out of scope

- Blocking delete based on appointment/record/prescription history - deactivate remains the tool
  for staff with real history.
- Cleaning up or cascading dangling references in other tables.
- A delete action on the staff list page - detail page only, per this design.
- Bulk delete.
