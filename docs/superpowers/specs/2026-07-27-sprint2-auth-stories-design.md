# Sprint 2 auth stories - design

## Goal

Close out four Sprint 2 stories: receptionist login, doctor login, logout, and password reset.
Login/logout for staff already work end-to-end (see
[2026-07-23-real-login-sessions-design.md](2026-07-23-real-login-sessions-design.md)) via cookie
sessions - most of this change is filling gaps (tests, a literal `DELETE` endpoint) rather than new
auth plumbing. Password reset is the one genuinely new feature, and is staff-only: patients don't
have passwords (they log in with IC/passport + phone number), so "forgot password" does not apply
to them.

## Receptionist & doctor login

No behavior change. Both already work via the shared `login.html` staff tab, `POST
/api/auth/login`, and PBKDF2 password verification (`core/security.verify_password`). The only gap
is that the login-to-dashboard redirect is decided client-side, with no test coverage.

**Change:** move the redirect mapping server-side.

- `LoginResponse` (`auth/schemas.py`) gains `redirect_url: str`.
- The router computes it from `staff.role` right after `authenticate_staff` succeeds:
  `admin -> /staff`, `doctor -> /appointments/schedule`, `nurse -> /patients`,
  `receptionist -> /patients`.
- `auth-login.js` uses `body.redirect_url` instead of keeping its own `REDIRECT_BY_ROLE` map (which
  is deleted - one source of truth instead of two).
- New `tests/test_auth_redirect.py`: logs in as each role, asserts `redirect_url` matches the table
  above.

Receptionist's "dashboard" stays `/patients` (the existing patient list) - not a new page.

## Logout

Also already works: the nav's "Logout" link calls `POST /api/auth/logout`, which clears
`request.session`. The story text asks for a `DELETE /auth/session` endpoint and a token cleared
from `localStorage`, which doesn't match this cookie-session architecture. Per product decision,
we add these anyway, alongside the existing mechanism rather than replacing it:

- `POST /api/auth/login` response gains `session_token: str` - a random opaque value
  (`secrets.token_urlsafe(32)`), generated fresh per login. It is not stored or validated
  server-side; the cookie session remains the actual authority. It exists only so the frontend has
  something to hold in `localStorage` and clear on logout, satisfying the story literally.
- `auth-login.js` stores it in `localStorage["clinicSessionToken"]` after a successful staff login.
- New `DELETE /api/auth/session` in `auth/router.py`, functionally identical to the existing `POST
  /api/auth/logout` (calls the same `logout(request)` dependency). The existing `POST
  /api/auth/logout` is untouched and keeps working (it's still what
  `test_logout_clears_the_session` exercises).
- The nav logout handler in `base.html` switches to `DELETE /api/auth/session`, then removes
  `clinicSessionToken` from `localStorage`, then redirects to `/auth/login` - same visible behavior
  as today.

## Password reset (staff only)

### Data model

New `PasswordResetToken` in `auth/models.py` (currently an empty file):

| Column | Type | Notes |
|---|---|---|
| `id` | int, PK | |
| `staff_id` | int, FK -> `staff.id` | |
| `token_hash` | str | SHA-256 of the raw token; only the hash is stored, mirroring how passwords are never stored raw |
| `expires_at` | datetime | `created_at + 30 minutes` |
| `used_at` | datetime, nullable | set on successful reset; makes the token single-use |
| `created_at` | datetime | |

`core/database.py init_db()` gains `from agile_ci_demo.auth import models as _auth_models  #
noqa: F401`, alongside the other per-module model imports, so `create_all` picks up the new table.

### Flow

1. `GET /auth/forgot-password` - new page, one field (email), styled like `login.html`.
2. `POST /api/auth/forgot-password` `{email}` - looks up `Staff` by email.
   - If found: generate `secrets.token_urlsafe(32)`, store its SHA-256 hash + a 30-minute expiry,
     email a reset link (`/auth/reset-password?token=<raw>`) via the existing `send_email`
     (recorded in the in-memory outbox, sent via SMTP if configured - same as the staff welcome
     email).
   - Always returns the same generic message ("If that email is registered, we've sent a reset
     link.") whether or not the email matched, so the endpoint can't be used to discover which
     emails have accounts - consistent with how `authenticate_staff` already avoids leaking
     account status.
3. `GET /auth/reset-password?token=...` - new page, new-password + confirm-password fields. Token
   travels as a query param, submitted with the form.
4. `POST /api/auth/reset-password` `{token, new_password}`:
   - Look up by `token_hash`. Reject (400, generic "This reset link is invalid or has expired")
     if: no match, `used_at` is set, or `expires_at` has passed.
   - Otherwise: hash the new password (`core/security.hash_password`), set it on the `Staff` row,
     clear `must_change_password`, set `used_at = now`, commit.
   - Validation: `new_password` min length 8, must match a `confirm_password` field. No existing
     password-strength rules to align with - there's no change-password flow anywhere yet, so this
     is a new minimum rather than a mismatch with something established.

### New/changed files

- `auth/models.py` - `PasswordResetToken` (file currently empty)
- `auth/schemas.py` - `ForgotPasswordRequest`, `ResetPasswordRequest`; `LoginResponse` gains
  `redirect_url`
- `auth/service.py` - `request_password_reset(db, email)`, `reset_password(db, token,
  new_password)`, `InvalidResetTokenError`
- `auth/router.py` - `POST/GET /forgot-password`, `POST/GET /reset-password`, `DELETE /session`
- `auth/deps.py` - unchanged
- `core/database.py` - one import line added to `init_db()`
- `templates/auth/login.html` - "Forgot password?" link under the staff tab
- `templates/auth/forgot_password.html`, `templates/auth/reset_password.html` - new, same
  Bootstrap structure/classes as `login.html`
- `static/js/auth-login.js` - use `redirect_url`, store `session_token`, delete
  `REDIRECT_BY_ROLE`
- `static/js/auth-forgot-password.js`, `static/js/auth-reset-password.js` - new, same fetch/alert
  pattern as `auth-login.js`
- `templates/base.html` - logout handler calls `DELETE /api/auth/session` and clears
  `localStorage`

## Testing

- `tests/test_auth_redirect.py` (new) - `redirect_url` per role.
- `tests/test_auth.py` (existing file, additions only) - `DELETE /api/auth/session` clears the
  session same as the existing logout test; forgot-password always returns the generic message for
  both a real and an unknown email; reset-password succeeds with a valid token and logs in with
  the new password afterward; reset-password rejects an expired token, a used token, and an
  unknown token; a used token cannot be reused.

## Out of scope

- Patient password reset - patients have no password to reset.
- Any staff-initiated "change my password while logged in" flow - not one of the four stories, and
  nothing in the codebase does this today either.
- Rate-limiting forgot-password requests.
