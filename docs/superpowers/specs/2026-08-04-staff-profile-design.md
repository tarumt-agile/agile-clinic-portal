# Staff Self-Service Profile — Design

## Context

There is currently no way for a logged-in staff member (doctor, receptionist, nurse, or admin) to view or edit their own account, or change their own password. Every staff-mutating endpoint (`PATCH /api/staff/{staff_id}`, status changes, deletion) is admin-only, gated to managing *other* staff. Password changes today only happen via the admin-driven welcome email (temp password) or the forgot-password token-link flow — neither lets a logged-in user change their password by supplying their current one.

**Scope:** a self-service profile page + two new API endpoints + one new auth dependency. No changes to admin-facing staff management (`/staff`, `/staff/create`, `/staff/{staff_id}` admin views and their endpoints stay exactly as they are).

**Out of scope, flagged separately, not fixed here:** `POST /api/staff`, `GET /api/staff`, and `GET /api/staff/{staff_id}` currently have no auth dependency at all (a pre-existing gap unrelated to this feature).

## What's Being Added

### Backend

1. **`require_staff` dependency** (`auth/deps.py`) — any authenticated staff member regardless of role, mirroring the existing `require_patient` (which has no role list, just checks session presence). `require_role(*roles)` requires an explicit role list; this feature needs "any staff role."

2. **`GET /api/staff/me`** — returns the logged-in staff member's own `StaffOut` record (same shape already used by the admin view).

3. **`PATCH /api/staff/me`** — self-edit, via a new `StaffSelfUpdate` schema restricted to `full_name` and `email` only. Deliberately excludes `specialty`/`license_number` (professional credentials — should stay admin-verified) and `is_active` (admin-only account status). This is a narrower schema than the admin's `StaffUpdate`, not a reuse of it.

4. **`POST /api/auth/change-password`** — new capability. Payload: `current_password`, `new_password`, `confirm_password`. Verifies `current_password` against the stored hash before accepting the change (unlike `reset-password`, which is reached via an emailed token and doesn't check the old password). Staff-only (`require_staff`) — not extended to patients, per explicit scope.

### Frontend

- New page `GET /staff/profile` → `templates/staff/staff_profile.html`, reachable by any logged-in staff role.
- Visually reuses the admin `staff_view.css` card pattern (avatar, detail card, edit-form card) already styled to Modern Slate, adapted to: no status badge/toggle, no specialty/license fields in the edit form, plus a new "Change Password" card (current/new/confirm fields).
- A "My Profile" link is added to the sidebar's user area in `base.html` (currently just an avatar + role label + Logout), visible for every authenticated staff role. Not shown for patients.

## Testing

- New pytest coverage: `GET /api/staff/me` returns the logged-in staff's own record and 401s when unauthenticated; `PATCH /api/staff/me` updates `full_name`/`email` and rejects attempts to smuggle `is_active`/`specialty` changes through it (schema-level exclusion, verified by asserting those fields are unaffected even if sent); `POST /api/auth/change-password` succeeds with the correct current password, rejects an incorrect one, and rejects a mismatched confirm.
- Manual verification: profile page loads for each staff role, edit saves correctly, password change actually allows logging in with the new password afterward.
