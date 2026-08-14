# Agile Clinic Portal

A web-based clinic management system built with FastAPI, Jinja2, and SQLAlchemy.
Started as a small teaching project on Agile development, automated testing, and
CI/CD, it has grown into a full clinic portal covering patient records,
appointment booking, consultations, prescriptions, pharmacy stock, and reporting
- with role-based access for admins, doctors, nurses, and receptionists, plus a
self-service portal for patients.

---

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone and create a virtual environment](#2-clone-and-create-a-virtual-environment)
  - [3. Install dependencies](#3-install-dependencies)
  - [4. Set up your `.env` file](#4-set-up-your-env-file)
  - [5. Initialize the database](#5-initialize-the-database)
  - [6. Run the app](#6-run-the-app)
- [Demo accounts](#demo-accounts)
- [Running tests](#running-tests)
- [Linting, formatting, and type checking](#linting-formatting-and-type-checking)
- [Running with Docker](#running-with-docker)
- [Continuous integration](#continuous-integration)

---

## Features

- **Authentication & access control** - session-based login for staff (admin,
  doctor, nurse, receptionist) and a separate self-service login for patients;
  page- and endpoint-level role restrictions; login lockout after repeated
  failures; password reset by email; an audit log of login/logout/access
  events.
- **Patient management** - registration with Malaysian IC/passport validation,
  search and filtering (including by registration date), full medical history,
  and patient self-service dashboard.
- **Appointment scheduling** - booking with live slot availability per doctor's
  working hours, calendar and list views, cancellation, and a one-appointment-
  per-day limit on patient self-service bookings (front-desk staff can still
  book a second same-day appointment for a walk-in).
- **Consultations** - doctors document visits with notes and ICD-10 diagnoses,
  attach files to a consultation, and a "Start Consultation" queue for the
  day's appointments.
- **Prescriptions & pharmacy** - doctors issue prescriptions tied to a
  consultation; pharmacy staff track medication stock and dispensing.
  Prescriptions can be printed to PDF.
- **Staff management** - admin-only staff creation, per-doctor working hours
  (with next-day-effective changes), specialty search, and activate/deactivate
  accounts.
- **Reports & dashboard** - an admin dashboard and reporting views over
  appointments, patients, and clinic activity.
- **Data protection** - patient PII (e.g. IC number, phone, address) is
  encrypted at rest.

## Tech stack

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy 2.0](https://www.sqlalchemy.org/) ORM, [Pydantic](https://docs.pydantic.dev/)
- **Frontend:** server-rendered [Jinja2](https://jinja.palletsprojects.com/) templates, vanilla JavaScript, [Bootstrap](https://getbootstrap.com/), [FullCalendar](https://fullcalendar.io/)
- **Database:** SQLite by default (swappable via `DATABASE_URL`)
- **Auth:** signed session cookies ([Starlette](https://www.starlette.io/) `SessionMiddleware`)
- **PDF generation:** [ReportLab](https://www.reportlab.com/)
- **Encryption:** AES-256-GCM via the [`cryptography`](https://cryptography.io/) package
- **Testing:** [pytest](https://docs.pytest.org/), [pytest-bdd](https://pytest-bdd.readthedocs.io/) (Gherkin BDD), [Hypothesis](https://hypothesis.readthedocs.io/) (property-based)
- **Tooling:** [ruff](https://docs.astral.sh/ruff/) (lint), [black](https://black.readthedocs.io/) (format), [mypy](https://mypy-lang.org/) (types)

## Project structure

```text
.
├── src/agile_ci_demo/
│   ├── app.py              # FastAPI app: middleware, router registration
│   ├── core/                # Settings, database session, security, encryption, email
│   ├── auth/                 # Login, sessions, password reset, audit log
│   ├── patients/             # Patient records
│   ├── appointments/         # Booking, scheduling, slots
│   ├── consultations/        # Consultation notes, diagnoses, attachments
│   ├── prescriptions/        # Prescriptions, PDF printing
│   ├── pharmacy/             # Medication stock
│   ├── staff/                # Staff accounts, doctor profiles, working hours
│   ├── reports/               # Reporting views
│   └── dashboard/             # Admin dashboard
├── templates/                # Jinja2 templates, organized to mirror src/
├── static/                    # CSS and JavaScript
├── tests/                     # pytest test suite (incl. tests/features/*.feature for BDD)
├── scripts/                   # One-off/dev scripts (DB seeding, etc.)
├── pyproject.toml             # Dependencies & tool config
├── Makefile                   # Shortcuts: install, lint, test, run
├── Dockerfile / docker-compose.yml
└── .github/workflows/         # CI: lint, type check, tests, CodeQL
```

## Getting started

### 1. Prerequisites

- Python 3.11 or newer
- `pip`

### 2. Clone and create a virtual environment

```bash
git clone <this-repo-url>
cd agile-clinic-portal
python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Git Bash / cmd)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

This installs the app itself (editable) plus everything needed for testing and
linting. If you only intend to run the app (not develop it), you can drop
`[dev]` and install just the runtime dependencies listed in `pyproject.toml`.

### 4. Set up your `.env` file

The app reads configuration from environment variables, loaded automatically
from a `.env` file in the project root if one exists (see
`src/agile_ci_demo/core/config.py`). Create one by copying the template below
into a new file named `.env` at the repo root:

```dotenv
# --- Clinic identity (shown in emails, printed prescriptions, etc.) ---
CLINIC_NAME=Agile Clinic
CLINIC_ADDRESS=123 Jalan Contoh, 50000 Kuala Lumpur
CLINIC_PHONE=03-1234 5678

# --- Database ---
# Defaults to a local SQLite file if unset - fine for development.
DATABASE_URL=sqlite:///./clinic.db

# --- Session & encryption secrets ---
# REQUIRED for anything beyond local development. Both fall back to fixed
# insecure dev values if left unset, which is fine for running locally or
# running the test suite, but must never be used in production.
#
# Generate a strong random value for each, e.g.:
#   python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-me-to-a-long-random-string
PATIENT_ENCRYPTION_KEY=change-me-to-a-different-long-random-string

# --- Email / SMTP (optional) ---
# If left unset, the app does not send real emails - it records them in an
# in-memory outbox instead (useful for local dev and tests). Set all of the
# SMTP_* variables together to send real emails (e.g. password resets, staff
# welcome emails).
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true

# Optional: send a Bcc copy of every outgoing email to this address, useful
# for verifying sends in a shared dev/staging environment. Leave unset in
# production.
EMAIL_DEV_BCC=
```

Notes:

- Every variable has a safe default for local development except
  `SECRET_KEY` and `PATIENT_ENCRYPTION_KEY`, which fall back to fixed,
  publicly-known dev values - set both to real secrets before deploying
  anywhere other than your own machine.
- `PATIENT_ENCRYPTION_KEY` encrypts patient PII (IC number, phone, address,
  etc.) at rest. Changing it after data has already been saved makes that
  data unreadable, so treat it like any other production secret: generate it
  once, store it securely, and don't rotate it without also re-encrypting
  existing data.
- `.env` is git-ignored - never commit real secrets to the repository.

### 5. Initialize the database

The app creates its SQLite database and tables automatically on first run. If
you'd like it pre-populated with demo staff, patients, and appointments for
local testing, run the seed script instead:

```bash
python scripts/seed_db.py
```

This is safe to re-run - it exits without making changes if clinic data
already exists. Pass `--force` to wipe and regenerate all demo data.

### 6. Run the app

```bash
uvicorn agile_ci_demo.app:app --reload
```

Or via the Makefile shortcut:

```bash
make run
```

The app will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000),
redirecting to the login page.

## Demo accounts

If you ran `scripts/seed_db.py`, the following accounts are available:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@clinic.com` | `admin123` |
| Doctor (General Medicine) | `alan.chua@clinic.com` | `alan123` |
| Doctor (Paediatrics) | `betty.lim@clinic.com` | `betty123` |
| Doctor (Cardiology) | `chandran.raj@clinic.com` | `chandran123` |
| Receptionist | `amy.wong@clinic.com` | `amy123` |
| Receptionist | `siti.rahman@clinic.com` | `siti123` |

Patients log in separately from the same login page, using their IC/passport
number and phone number instead of an email/password.

## Running tests

```bash
pytest
```

Or with coverage (matches what CI runs):

```bash
pytest --cov=src
```

The suite includes unit tests, integration tests against a real (in-memory)
database and HTTP client, and BDD-style scenario tests defined in
`tests/features/*.feature`.

## Linting, formatting, and type checking

```bash
make lint    # ruff check + black --check
make format  # black (auto-fix formatting)
make type    # mypy src
```

## Running with Docker

```bash
docker compose up --build
```

This builds the image from the `Dockerfile` and serves the app on
[http://localhost:8000](http://localhost:8000). Provide configuration the same
way as above - either mount a `.env` file into the container or pass
environment variables through `docker-compose.yml`.

## Continuous integration

Every push and pull request runs through GitHub Actions
(`.github/workflows/ci.yml`): dependency install, `ruff`/`black` linting,
`mypy` type checking, and the full test suite (with coverage and JUnit
reports uploaded as artifacts) across Python 3.11-3.14. `codeql.yml` runs
static security analysis on the same triggers.
