# Sprint 2 - consultation attachments, IC autocomplete, admin patient delete, password-email logging - design

## Goal

Four independent Sprint 2 items, bundled into one spec since they're being built together:

1. Doctor can attach a file (e.g. lab results) to a consultation record.
2. Receptionist booking a visit sees matching patients as they type an IC number, instead of
   needing the full IC before anything resolves.
3. Only admins can permanently delete a patient record.
4. Password-reset emails that fail to send are logged server-side instead of vanishing silently.

Items 1-3 are net-new capability. Item 4 is a bug-visibility fix for the existing forgot-password
flow (`auth/service.py`) - see [2026-07-27-sprint2-auth-stories-design.md](2026-07-27-sprint2-auth-stories-design.md)
for how that flow itself was built.

None of the four touch each other's code, so they can be implemented and tested independently.

---

## 1. Consultation attachments

### Data model

New module `src/agile_ci_demo/attachments/` (mirrors `records/`, `prescription/`). New table via
`attachments/models.py`:

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `consultation_note_id` | int, FK -> `consultation_notes.id` | |
| `original_filename` | str | shown to the user |
| `stored_filename` | str | UUID4 + original extension; collision-proof, never derived from user input |
| `content_type` | str | from the upload, re-validated server-side (see below) |
| `size_bytes` | int | |
| `uploaded_by_staff_id` | int, FK -> `staff.id` | |
| `created_at` | datetime | |

`core/database.py` `init_db()` gains one import line:
`from agile_ci_demo.attachments import models as _attachments_models  # noqa: F401`, alongside the
other per-module imports already there, so `create_all` picks up the new table.

### Storage

Files are saved to a new local folder `uploads/consultation_attachments/`, outside `static/`, so
they are never reachable through the existing `StaticFiles` mount - the only way to fetch one is
the authenticated download route below. On-disk filename is `{uuid4}{ext}`; the original filename
is preserved only in the DB, for display and for the `Content-Disposition` header on download.

Validation (before anything is written to disk):
- Content type must be one of `application/pdf`, `image/jpeg`, `image/png`.
- Size must be <= 5 MB (`5 * 1024 * 1024` bytes).
- Both checks run against the actual `UploadFile` (content-type header + streamed size), not just
  the filename extension.

### Backend

New `attachments/service.py`:
- `save_attachment(db, consultation_record_id, upload, uploaded_by_staff_id)` - looks up the
  `ConsultationNote` by its public `record_id` (404 if missing via `ConsultationNoteNotFoundError`),
  validates type/size (`InvalidAttachmentError` on failure), writes the file, inserts the row,
  commits, returns it.
- `list_attachments(db, consultation_record_id)` - all attachments for a note, newest first.
- `get_attachment(db, attachment_id)` - single row or `None`, used by the download route.

New `attachments/router.py`, `api_router = APIRouter(prefix="/api/attachments", tags=["attachments"])`:
- `POST /api/attachments` - multipart form (`consultation_record_id: str`, `file: UploadFile`),
  gated by `require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)` (same set as the
  records pages), returns the created attachment's metadata (201).
- `GET /api/attachments?record_id=...` - list for a note, same role gate.
- `GET /api/attachments/{attachment_id}/download` - streams the file (`FileResponse`, original
  filename in `Content-Disposition`), same role gate; 404 if the row or the underlying file is
  missing.

`app.py` gains two lines: importing and `include_router`-ing the new `api_router`, alongside the
existing eleven router registrations.

### Frontend

`templates/records/detail.html` gets a new "Attachments" `<section class="card mb-4">`, inserted
after the existing Diagnoses section, with an upload form (file input + submit button) and a list
container for existing attachments (name, size, uploaded-by, a Download link). One new
`<script src="/static/js/consultation-attachments.js">` tag is added alongside the existing
`record_detail.js` include. No existing lines in this file or in `record_detail.js` are changed.

New `static/js/consultation-attachments.js` (standalone, reads `record-detail-root`'s
`data-record-id` the same way `record_detail.js` does): loads the attachment list on page load,
handles the upload form's submit (client-side type/size pre-check for fast feedback, real
enforcement is server-side), re-renders the list on success, shows inline errors on 422/404.

### Testing

New `tests/test_attachments.py`, same fixture pattern as `test_records.py` (in-memory SQLite,
`TestClient`, direct model imports):
- Valid PDF/JPG/PNG upload succeeds (201) and appears in the list.
- Oversized file (>5 MB) rejected (422), no DB row, no file written.
- Disallowed content type (e.g. `text/plain`) rejected (422).
- Unknown `consultation_record_id` returns 404.
- Download returns the file with the original filename in `Content-Disposition`.
- Download of an unknown `attachment_id` returns 404.

---

## 2. IC autocomplete on the booking form

Today `templates/appointments/receptionist_createAppointment.html` + `static/js/appointment-form.js`
only do an exact-match lookup (`GET /api/patients/by-ic/{ic}`) fired on blur, once the full
formatted IC has been typed.

### Backend

New endpoint in the existing `patients/router.py`:
`GET /api/patients/search-ic?q=...` -> new `search_patients_by_ic_prefix(db, prefix, limit=8)` in
the existing `patients/service.py`, using `Patient.ic_or_passport.like(f"{prefix}%")` (prefix
match on the raw digits/characters typed so far). Returns up to 8
`{patient_id, full_name, ic_or_passport}` results. No role gate beyond normal staff auth (same as
the existing `by-ic` lookup, which is also unauthenticated at the route level today).

### Frontend

`appointment-form.js` gains a debounced (`~250ms`) `input` listener on `#patient_ic`: once 3 or
more characters have been typed, it calls `search-ic` and renders a suggestion dropdown (same
list-group pattern already used for ICD-10 suggestions in `consultation-note-form.js`). Clicking a
suggestion fills `#patient_ic` and the hidden `#patient_id`, and hides the dropdown - identical
end state to today's successful blur lookup. The existing blur-triggered exact lookup is
unchanged and still runs as the final check before submit (covers the case where a receptionist
pastes or types a full IC without ever seeing/using a suggestion).

`receptionist_createAppointment.html` gains one new empty container,
`<div id="patient-ic-suggestions" class="list-group position-absolute d-none"></div>`, placed
right after the existing `#patient_ic` input. No existing markup in this file changes.

### Testing

New tests in `tests/test_patients.py` (existing file, additions only):
- `search-ic` with a 3+ digit prefix returns only patients whose IC starts with it.
- A prefix matching zero patients returns an empty list (200, not 404 - it's a suggestion feed, not
  a lookup).
- Results are capped at 8 even when more patients match.

---

## 3. Admin-only patient delete

No delete-patient capability exists today (confirmed - no endpoint, no button, anywhere). This
follows the same shape as the existing admin-only staff delete
([2026-07-27-admin-delete-staff-design.md](2026-07-27-admin-delete-staff-design.md)), with one
difference: staff delete leaves dangling references; **patient delete cascades**, per product
decision - a patient's appointments, consultation notes, diagnoses, and prescriptions are medical
history that shouldn't be left half-orphaned if the patient row itself is gone.

### Access control

**Admin only, no exceptions.** New endpoint uses `require_role(Role.ADMIN)`, same as staff delete.
The patient detail page itself (`GET /patients/{patient_id}`) stays open to
`RECEPTIONIST, NURSE, DOCTOR, ADMIN` as it is today - only the delete action is admin-restricted,
both server-side (route dependency) and in the UI (button hidden for non-admins via
`{% if request.session.get('role') == 'admin' %}`, the same session-role check already used
elsewhere in this template).

### Delete semantics

**Hard delete, cascading**, in FK-safe order (SQLite doesn't enforce foreign keys in this app, but
explicit ordering keeps the intent clear and works unchanged if that ever changes):

1. `PrescriptionHistory` rows for any `Prescription` belonging to the patient.
2. `Prescription` rows for the patient (`patient_id`).
3. `Diagnosis` rows for any `ConsultationNote` belonging to the patient.
4. `ConsultationNote` rows for the patient (`patient_id`).
5. `Appointment` rows for the patient (`patient_id`).
6. The `Patient` row itself.

All in one transaction (single commit after all deletes).

### Backend

New `delete_patient(db: Session, patient_id: str) -> None` in `patients/service.py`:

```python
def delete_patient(db: Session, patient_id: str) -> None:
    """Permanently remove a patient and all of their appointments, consultation
    notes, diagnoses, and prescriptions."""
    patient = get_patient_by_patient_id(db, patient_id)
    if patient is None:
        raise PatientNotFoundError(f"No patient found with patient_id '{patient_id}'")

    prescription_ids = db.execute(
        select(Prescription.id).where(Prescription.patient_id == patient.id)
    ).scalars().all()
    if prescription_ids:
        db.execute(delete(PrescriptionHistory).where(PrescriptionHistory.prescription_id.in_(prescription_ids)))
        db.execute(delete(Prescription).where(Prescription.id.in_(prescription_ids)))

    note_ids = db.execute(
        select(ConsultationNote.id).where(ConsultationNote.patient_id == patient.id)
    ).scalars().all()
    if note_ids:
        db.execute(delete(Diagnosis).where(Diagnosis.consultation_note_id.in_(note_ids)))
        db.execute(delete(ConsultationNote).where(ConsultationNote.id.in_(note_ids)))

    db.execute(delete(Appointment).where(Appointment.patient_id == patient.id))
    db.delete(patient)
    db.commit()
```

(Imports `Prescription`, `PrescriptionHistory` from `prescription.models`; `ConsultationNote`,
`Diagnosis` from `records.models`; `Appointment` from `appointments.models` - all new imports into
`patients/service.py`, no changes to those other modules.)

New endpoint in `patients/router.py`:

```python
@api_router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient_endpoint(
    patient_id: str,
    db: Session = Depends(get_db),
    _admin=Depends(require_role(Role.ADMIN)),
) -> None:
    try:
        delete_patient(db, patient_id)
    except PatientNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
```

### Frontend

`templates/patients/patients_details.html` gets a "Delete Patient" button (`btn btn-danger`) and a
confirmation modal - same structure as the staff-delete modal - both wrapped in the admin-only
`{% if %}` block. Wording: "Delete this patient permanently? This will also permanently delete
their appointments, consultation records, and prescriptions. This cannot be undone."

New `static/js/patient-delete.js` (one new `<script>` tag added to the template, `patient_detail.js`
untouched): opens the modal on click, sends `DELETE /api/patients/{patient_id}` on confirm, redirects
to `/patients` on success, shows the error inline on failure (404 - already deleted/unknown).

### Testing

New tests in `tests/test_patients.py`:
- Deleting a patient with no history succeeds (204); subsequent `GET` returns 404.
- Deleting a patient with appointments/consultation notes/diagnoses/prescriptions succeeds and all
  of those rows are gone afterward too (verified via direct queries or their own list endpoints).
- A non-admin (or logged-out) request is redirected to `/auth/login` (303), same pattern as the
  existing staff-delete role test.
- Deleting an unknown `patient_id` returns 404.

---

## 4. Password-reset email failures: log instead of silently swallowing

`auth/service.py`'s `request_password_reset` already wraps `send_email(...)` in
`except Exception: pass`, deliberately, so the API response never reveals whether an email exists
or whether delivery succeeded (see the existing docstring). That reasoning still holds for the
*response* - it does not need to change. What's missing is any server-side record that a send
failed at all.

**Change:** add `import logging` and `logger = logging.getLogger(__name__)` at module level in
`auth/service.py` (no logging exists anywhere in the codebase yet, so this introduces the
standard-library pattern, not a new dependency). In the existing `except Exception:` block, add one
line before `pass`:

```python
except Exception:
    logger.exception("Password reset email failed to send to %s", staff.email)
```

No response, status code, or timing changes - purely additive server-side visibility.

Note: this makes the *next* failure diagnosable, it does not fix the current one. The most likely
cause found during investigation is the configured Gmail SMTP account being throttled/over its
daily quota (per commit `9dbc301`, which hit the same limit during testing the day before this bug
was reported) - that's an account-level issue outside what a code change can resolve, and isn't
addressed by this spec.

### Testing

One new test in `tests/test_auth.py` (existing file): mock `send_email` to raise, call
`request_password_reset`, assert it doesn't raise (existing silent-failure behavior preserved) and
that a log record was emitted (`caplog`).

---

## Out of scope

- Object/cloud storage for attachments (S3, Azure Blob, etc.) - the app has no cloud storage
  integration today; local disk matches how it already serves `static/`.
- Deleting or replacing individual attachments after upload.
- Patients viewing/downloading their own attachments (self-service) - staff-only, matching how the
  rest of the consultation record is staff-only today.
- IC autocomplete on the patient self-service booking page - that page has no IC field (it uses
  the logged-in patient's own record via `/api/patients/me`).
- Fuzzy/substring IC matching - prefix-only, per product decision.
- Blocking patient delete based on history - the opposite choice was made (cascade), unlike staff
  delete's "leave dangling references, block nothing" approach.
- Actually resolving the Gmail quota/throttling issue, or switching email providers.
- Extending password reset to patient accounts.
