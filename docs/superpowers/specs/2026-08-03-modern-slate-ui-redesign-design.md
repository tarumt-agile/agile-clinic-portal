# Modern Slate UI/UX Redesign — Design

## Context

Agile Clinic Portal is a Flask app rendering Jinja2 templates, styled with Bootstrap 5.3.3 (CDN) plus a handful of page-specific CSS files (`app.css`, `pharmacy-management.css`, `reports-dashboard.css`, `staff_create.css`, `staff_list.css`, `staff_view.css`, `prescription-print.css`). Navigation today is a single Bootstrap top navbar in `templates/base.html` that conditionally shows links per role.

This is a **visual and structural-shell redesign only**. No routes, no business logic, no page flows, and no role permissions change. Every existing page keeps doing exactly what it does today — this spec covers how it looks.

**Scope:** all 24 templates across 8 feature areas (auth, patients, appointments, consultations, pharmacy, prescriptions, reports, staff), serving 5 roles (doctor, receptionist, nurse, admin, patient).

## Visual Direction: "Modern Slate"

Validated interactively via mockups (dashboard queue cards, a full Patients List page, a Patient Registration form, and the Login page) before writing this spec.

### Design tokens

| Token | Value | Usage |
|---|---|---|
| Sidebar background | `#1e293b` (slate-800) | Sidebar shell, login page background |
| Sidebar hover/active background | `#334155` (slate-700) | Active/hovered nav item |
| Sidebar text | `#cbd5e1` (slate-300) | Nav link text |
| Active nav indicator | `3px solid #6366f1` (indigo-500) | Right border on active nav item |
| Primary accent | `#4f46e5` (indigo-600) | Primary buttons, links, focus rings |
| Avatar accent | `#6366f1` (indigo-500) | User avatar circle in sidebar |
| Content background | `#f8fafc` (slate-50) | Main content area behind cards/tables |
| Card/table background | `#ffffff` | Cards, table body |
| Card/table border | `#e2e8f0` (slate-200) | Card and table borders |
| Table header background | `#f1f5f9` (slate-100) | `<th>` background |
| Table header text | `#475569` (slate-600) | `<th>` text, uppercase, small |
| Body text | `#0f172a` / `#1e293b` | Headings / body copy |
| Input border | `#dbe0e6` | Form inputs, search/filter boxes |
| Focus ring | `#6366f1` border + `rgba(99,102,241,.15)` shadow | Input focus state |
| Success badge | bg `#dcfce7` / text `#166534` | e.g. "Active" status |
| Pending badge | bg `#fef9c3` / text `#854d0e` | e.g. "Pending" status |
| Error/invalid | `#dc2626` | Validation error text/border |

**Typography:** system font stack (`-apple-system, "Segoe UI", Roboto, ...`) — no external webfont. Chosen over a Google Font for zero extra network load and native rendering per device.

**Border radius:** 6–10px on cards/inputs/buttons, 12px on the login card. No sharp corners, no heavy rounding.

**Shadows:** minimal — a soft shadow only on the login card; flat bordered cards elsewhere.

## Layout Architecture

Replaces the current Bootstrap top navbar with a persistent left sidebar shell:

- **Sidebar** (`#1e293b`, ~210px wide): brand/logo at top, role-aware nav links below (see role nav map), user name + avatar pinned at the bottom.
- **Topbar**: page title (left) + primary page action button (right, e.g. "+ Register Patient"), white background, sits above the content area.
- **Content area**: `#f8fafc` background, holds page-specific content (tables, forms, cards) at the existing container width/padding conventions.
- **Unauthenticated pages** (login, forgot/reset password): no sidebar — a centered white card floats on a slate (`#1e293b`) background instead.
- **Mobile/small screens**: sidebar collapses behind a hamburger toggle in a slim topbar (standard collapsible-sidebar pattern) — same nav items, no content or link changes.

### Role → nav items (unchanged from current `base.html` logic, restyled only)

| Role | Nav items |
|---|---|
| receptionist / nurse | Patients, Register Patient, Book Appointment, Doctor Schedule |
| admin | all receptionist/nurse items + Pharmacy, Staff, Reports |
| doctor | My Schedule, Start Consultation |
| patient | My Dashboard, Book My Appointment, My Appointments |
| (all authenticated) | Logout, pinned at sidebar bottom with user name/avatar |
| (unauthenticated) | Login only, no sidebar |

## Component Styles

- **Tables**: light `#f1f5f9` header row (uppercase, small, semibold), white body rows, subtle hover (`#f8fafc`), status pills for state columns, text-link row actions (e.g. "View") in the accent color.
- **Forms**: white card wrapper, section-title groupings for longer forms, labeled fields, indigo focus ring, inline red error text under invalid fields, primary/secondary button pair (solid indigo / outlined gray) right-aligned at the bottom.
- **Buttons**: solid indigo (`#4f46e5`) primary, white-with-border secondary. No other button colors introduced except semantic ones already in use (e.g. destructive actions stay red, consistent with current Bootstrap `btn-danger` usage).
- **Badges/status pills**: rounded, small, color-coded per existing status semantics (map current Bootstrap contextual colors — success/warning/danger — onto the new palette rather than inventing new statuses).
- **Login/auth pages**: centered card, no sidebar, slate background.
- **Prescription print page**: restyled to match the new brand (indigo accents, consistent typography/spacing) rather than left as a bare default print sheet — per explicit preference over the more conservative "leave it plain" option. Still a standalone printable document with no app shell (no sidebar/topbar), since it's meant to be printed physically.

## Implementation Approach

Keep Bootstrap 5.3.3 rather than removing it — it's already a dependency and `bootstrap.bundle.min.js` backs existing interactive bits (dropdowns, etc.). Reskin via:

1. Override Bootstrap's CSS custom properties (`--bs-*`) and add the new design tokens as CSS variables in `static/css/app.css`.
2. Replace the top navbar markup in `templates/base.html` with the new sidebar + topbar shell, keeping the existing Jinja role-conditional logic (just restructured into sidebar link markup instead of navbar link markup).
3. Update each page-specific CSS file (`pharmacy-management.css`, `reports-dashboard.css`, `staff_*.css`, `prescription-print.css`) to consume the new tokens instead of ad-hoc values, rather than rewriting each page from scratch.
4. No JS behavior changes beyond what's needed for the sidebar's mobile collapse toggle (new, small addition) — no changes to any page's business logic JS files.

This is lower-risk than a framework swap or full rewrite, and keeps the "don't change system flow" constraint clean since it touches markup structure and CSS only.

## Out of Scope

- Any change to routes, permissions, business logic, or page-to-page navigation flow.
- Any change to what data is shown or how it's fetched.
- Introducing a new frontend framework/build step (stays server-rendered Jinja2 + vanilla JS + Bootstrap).
- New pages or removed pages.

## Testing / Verification

Since no functional flow changes, verification is manual/visual rather than new automated tests:

- Walk each of the 8 feature areas as each relevant role; confirm sidebar nav, topbar, tables, forms, badges, and login render correctly with the new shell.
- Check sidebar collapse behavior on a small viewport.
- Re-run the existing pytest/Playwright suites (`tests/`) to confirm markup restructuring didn't break any selector-dependent test — fix any that assumed old navbar markup.
