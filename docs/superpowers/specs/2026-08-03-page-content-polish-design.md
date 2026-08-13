# Page Content Polish — Design

## Context

The "Modern Slate" redesign ([2026-08-03-modern-slate-ui-redesign-design.md](2026-08-03-modern-slate-ui-redesign-design.md)) replaced the top navbar with a sidebar shell and established design tokens, but most page *content* still renders with default Bootstrap styling underneath the new shell — it still "feels like stock Bootstrap." This is a follow-up pass: extend the same design language into the page content itself, fix content centering, shore up responsiveness, and add a logout confirmation.

**Not a new visual direction.** No new mockups were needed — the target look (card treatment, section-title spacing, badge/pill styling) was already validated during the first redesign (the approved Patient Registration and Patients List mockups). This spec applies that look more broadly and fixes concrete gaps.

**Scope:** visual/CSS polish, minor markup additions (a confirmation modal, stat-card wrappers), and responsive fixes. No route, permission, or business-logic changes, consistent with the first redesign's constraint.

## Issues Being Addressed

1. **Content not centered.** `.app-content` (`static/css/app.css`) has `max-width: 1200px` but no auto margins, so on wide screens content pins to the left with an empty gutter on the right (visible on the Reports page screenshot). Fix: `margin-inline: auto`.

2. **Inconsistent responsive behavior.** Only Staff List (`staff_list.css`) has a mobile card-view fallback for its table. Patients List, Doctor Schedule's day-detail table, and Pharmacy's medication table just get Bootstrap's default horizontal scroll on narrow screens — functional but not designed. Fix: apply the same table→stacked-card breakpoint pattern already proven in `staff_list.css` to these tables (via shared CSS rather than duplicating the pattern four times — see Implementation Approach).

3. **Logout has no confirmation.** Clicking "Logout" in the sidebar fires immediately (`templates/base.html`'s inline script calls `DELETE /api/auth/session` directly on click). Fix: add a confirmation modal, following the exact pattern already used for destructive actions elsewhere (e.g. `delete-patient-modal` in `patients_details.html`, `cancel-modal` in `doctor_viewSchedule.html`) — a Bootstrap modal with a "Cancel" / "Log Out" button pair, wired so the actual `DELETE` call only fires on confirm.

4. **Stat/summary cards look like default Bootstrap cards.** Pharmacy's three summary cards (Displayed/Low stock/Out of stock) use plain `.card`/`.card-body` with no visual distinction from a content card. Fix: a `.stat-card` component (accent-colored label, large number, consistent with the dashboard-tile look already established) applied to Pharmacy's three cards, reusable anywhere else a single-number summary appears.

5. **Forms read as bare Bootstrap grids.** Book Appointment's form, Pharmacy's Add Medication/Adjust Stock modal forms, and Staff Create (already partially done in the first pass) don't have the section-title grouping + labeled-field rhythm from the approved registration mockup. Fix: a reusable `.form-section` pattern (uppercase label + spacing, matching the mockup) applied to these forms.

6. **Time-slot picker looks like plain text.** Book Appointment's time-slot grid (`#slot-grid`) renders slots as unstyled buttons in a flex-wrap row. Fix: pill-style toggle buttons (rounded, bordered, selected state uses the accent color) — purely a CSS class addition to the existing buttons the JS already generates (`static/js/appointment-form.js` builds the slot buttons; this only needs a CSS class add, not JS logic changes).

7. **Doctor Schedule's date list doesn't match the sidebar's list-item language.** The "Upcoming Dates" list (`list-group-item`) uses default Bootstrap list-group styling. Fix: restyle list-group items with the same hover/active treatment already established for `.sidebar-link` (adapted colors — light background, not the dark sidebar), for visual consistency between the nav and in-page lists.

## Implementation Approach

Everything above is delivered as **CSS additions to `static/css/app.css`** (global, cascades everywhere) plus:
- One new modal block in `templates/base.html` (logout confirmation) + a small JS change to the existing inline script (wire the confirm button instead of firing immediately)
- Three `<div class="card">` → `<div class="stat-card">` markup swaps in `templates/pharmacy/pharmacy_management.html` (class name change only, no structural change)
- A `.form-section` wrapper added around existing field groups in `templates/appointments/receptionist_createAppointment.html` and the two Pharmacy modals in `templates/pharmacy/pharmacy_management.html` (grouping markup only — no new fields, no logic change)
- A CSS class added to the slot-button template string in `static/js/appointment-form.js` (the JS already builds `<button>` elements per slot; this only changes which class string gets applied)

No other templates need markup changes — Patients List, Patient Registration, Login/Reset Password, and Staff List/View already have compatible structure and pick up the CSS-only fixes (centering, table responsiveness, card styling) automatically, the same way 18 of 24 templates needed no changes in the first redesign pass.

## Testing

Same approach as the first redesign: existing `pytest` suite must stay green (this only touches CSS/markup, no assertions in the suite depend on card/table visual classes beyond what the first pass already covers), plus a manual cross-role visual/responsive pass at the end, including the logout confirmation flow specifically (click Logout → modal appears → Cancel keeps the session → Log Out actually calls `DELETE /api/auth/session` and redirects).
