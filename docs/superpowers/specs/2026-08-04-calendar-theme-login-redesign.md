# Calendar Theming + Login Page Redesign — Design

## Context

Two visual-only follow-ups, bundled together since both are CSS/template changes with no backend work:

1. The FullCalendar embed added in the previous round (Doctor Schedule calendar view) uses FullCalendar's own default blue-gray toolbar styling — the event colors already match our status palette, but the chrome around them (buttons, borders, today-highlight) doesn't match Modern Slate.
2. The login page (`templates/auth/login.html` + its `auth-shell`/`auth-card-wrap` treatment from the first redesign round) should adopt the split-panel layout style from the user-provided reference image, while keeping the app's actual login behavior (Staff/Patient tabs) unchanged.

**Scope:** CSS additions + one template restructure. No behavior changes — the calendar's data/interactions and the login form's fields/submission logic are untouched.

## 1. Calendar Theming

FullCalendar 6 exposes CSS custom properties for its chrome. Override these (in `static/css/app.css`, scoped under `#schedule-calendar`) using the existing design tokens:

| FullCalendar variable | Value |
|---|---|
| `--fc-border-color` | `var(--clinic-border)` |
| `--fc-page-bg-color` | `#fff` |
| `--fc-neutral-bg-color` | `var(--clinic-content-bg)` |
| `--fc-list-event-hover-bg-color` | `var(--clinic-content-bg)` |
| `--fc-today-bg-color` | `#eef2ff` (light indigo tint, consistent with other "active/highlighted" surfaces already used elsewhere) |
| `--fc-button-bg-color` | `#fff` |
| `--fc-button-border-color` | `var(--clinic-border)` |
| `--fc-button-text-color` | `var(--clinic-text)` |
| `--fc-button-hover-bg-color` | `var(--clinic-content-bg)` |
| `--fc-button-active-bg-color` | `var(--clinic-accent)` |
| `--fc-button-active-border-color` | `var(--clinic-accent)` |

Plus: toolbar title font-weight/size aligned with the app's existing heading style, and the toolbar buttons' text capitalized to match (FullCalendar's default is lowercase "month"/"week"/etc.).

Event colors (indigo/green/gray by status) are already correct from the prior round and stay as-is.

## 2. Login Page Redesign

Restructure `templates/auth/login.html`'s content and the `auth-shell`/`auth-card-wrap` CSS into a two-panel layout:

- **Left panel:** a dark slate/indigo block (reusing `--clinic-sidebar-bg`) containing a large centered icon (a simple clinic-relevant SVG/icon in the app's palette — not a recreation of the reference's specific stethoscope-and-phone illustration) and the brand name.
- **Right panel:** white background, "Agile Clinic Portal" heading, then the form area containing the **existing, unchanged** Staff/Patient tab toggle and both login forms (email/password for staff; IC+phone for patients), plus the existing "Forgot password?" link.
- **Dropped from the reference:** the carousel prev/next arrows (nothing in this app to cycle through) and the "Create an account! Signup" link (patients don't self-register here — registration is receptionist-driven via `/patients/register`).
- On narrow viewports, the left illustration panel collapses/hides (mobile-first: the form is what matters on a phone), matching how the rest of the app already handles small screens.
- `forgot_password.html` and `reset_password.html` keep their current single-panel centered-card treatment (`auth-card-wrap`) — this redesign is scoped to the login page specifically, since it's the one the reference image shows and the one every user sees first. Extending the split-panel look to the other two auth pages is a natural follow-up, not required now.

## Testing

- No new pytest coverage needed beyond confirming the login page still renders 200 and still contains the existing Staff/Patient tab markup (regression, not new behavior) — the existing `tests/test_auth.py` / `tests/test_base_layout.py` login-related assertions must keep passing unchanged.
- Manual verification: calendar toolbar/grid colors match the app's palette in both List/Calendar toggle states on both schedule pages; login page renders the split layout on desktop and collapses sensibly on mobile; login still works for both staff and patient tabs.
