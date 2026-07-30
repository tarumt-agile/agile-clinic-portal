# Filter Patient List by Registration Date - Design

## Goal

Let a receptionist (or anyone with access to the patient list) narrow the patient list by
registration date, alongside the existing name/patient-ID search. Combine, not replace: a search
query and a date range can be active together.

## Background

The patient list page (`templates/patients/receptionist_viewPatients.html`,
`static/js/patients_list.js`) already has a debounced search box, backed by
`GET /api/patients?q=...&page=...&page_size=...`, which calls
`search_patients(db, query, page, page_size)` in `src/agile_ci_demo/patients/service.py`. That
function builds a list of SQL conditions from `query` and applies them to both a count query and
the paginated items query. `Patient.created_at` (a `DateTime` column, set at registration and
never updated for this purpose) already exists and is already exposed on the `PatientOut` schema -
no new column or schema field is needed for the underlying data.

## Backend changes

`search_patients` gains two new optional parameters:

```python
def search_patients(
    db: Session,
    query: str | None,
    page: int,
    page_size: int,
    registered_from: dt.date | None = None,
    registered_to: dt.date | None = None,
) -> tuple[list[Patient], int]:
```

Each, if provided, adds one more condition to the same `conditions` list the function already
builds from `query` (so it composes with the existing search, not replaces it):

- `registered_from`: `Patient.created_at >= dt.datetime.combine(registered_from, dt.time.min)`
  (inclusive from the start of that day).
- `registered_to`: `Patient.created_at <= dt.datetime.combine(registered_to, dt.time.max)`
  (inclusive through the end of that day - so picking the same date for both fields correctly
  matches "everyone registered today," not zero rows).

If `registered_from` is after `registered_to`, no special-case handling is needed - the query
naturally returns zero rows, which is the correct and self-explanatory result.

`GET /api/patients` (`list_patients` in `src/agile_ci_demo/patients/router.py`) gains two matching
optional query parameters, `registered_from: dt.date | None` and `registered_to: dt.date | None`
(FastAPI parses `YYYY-MM-DD` query strings into `dt.date` automatically, same as it already does
for `PastDateError`-style date parameters elsewhere in this codebase), passed straight through to
`search_patients`.

## Frontend changes

Two new `<input type="date">` fields are added to the search card in
`templates/patients/receptionist_viewPatients.html`, next to the existing search box, labelled
"Registered from" and "Registered to." A new "Registered on" column is added to the results table,
after "Date of birth."

`static/js/patients_list.js`'s existing `state` object (`{ query, page }`) gains
`registeredFrom`/`registeredTo`, following the exact pattern already used for `query`: an `input`
event listener on each new date field updates `state` and calls `loadPatients()` with `page` reset
to 1 (matching the existing search box's debounce-and-reset behaviour - date pickers don't need the
debounce timer itself, since browsers only fire `input` on a date field once a full date is picked,
not per keystroke, but resetting to page 1 on change is still needed). `loadPatients()`'s
`URLSearchParams` construction adds `registered_from`/`registered_to` to the request only when set,
mirroring how `q` is already conditionally added. `renderTable` adds one more `<td>` per row,
formatting `p.created_at` (an ISO datetime string) down to just its date portion for display
(`p.created_at.slice(0, 10)`), matching how `date_of_birth` is already rendered as a plain date
string with no reformatting.

## Testing

- `search_patients`: `registered_from` alone, `registered_to` alone, both together, both combined
  with a text `query`, an inverted range returning zero rows, and the existing no-date-filter
  behaviour unchanged (regression coverage for the current search-only tests).
- `GET /api/patients`: query params round-trip correctly to filtered results; omitting both date
  params behaves exactly as it does today.
- Manual browser check: the "Registered on" column renders, both date fields filter correctly
  alone and together, and combining a name search with a date range narrows results as expected.

## Out of scope

- Filtering by anything other than registration date (e.g. date of birth range) - not requested.
- Preset quick ranges (today/this week/this month) - the from/to pickers cover this need directly.
- Special validation or an error message for an inverted date range - it already resolves itself
  to zero rows, which is correct and requires no extra code.
