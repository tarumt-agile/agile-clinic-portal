"""Auto-classifies tests by type, for the CI job summary's test breakdown.

Adds an "acceptance" or "io" marker to each collected test without any test
file needing to opt in by hand:

- acceptance: BDD/Gherkin scenario tests wired up via pytest-bdd's
  scenarios(...) (see tests/features/*.feature).
- io: tests that exercise a real system boundary - an HTTP request via
  TestClient, or a database session.

Anything matching neither stays unmarked and is reported as "other" -
this stays accurate as new tests are added without needing to be updated
here.
"""

from __future__ import annotations

import inspect

import pytest

_IO_SIGNALS = ("TestClient(", "client.", "db.", "Session", ".execute(", "get_db")


@pytest.fixture(autouse=True)
def _disable_real_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never send real email. Every staff-creation test triggers a
    welcome email (and forgot-password tests trigger a reset email), and a
    developer's local .env may have live SMTP credentials configured for the
    running app - without this, a full test run silently sends dozens of real
    emails through whatever account is configured and can exhaust its daily
    sending limit (this happened during development: repeated full-suite runs
    against a live Gmail account triggered Gmail's 550 5.4.5 daily limit).
    core.email.send_email() always records to the in-memory outbox regardless
    of these settings, so get_outbox()-based assertions are unaffected.
    """
    from agile_ci_demo.core.config import settings

    monkeypatch.setattr(settings, "smtp_host", None)
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_password", None)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if not isinstance(item, pytest.Function):
            continue

        if item.function.__module__ == "pytest_bdd.scenario":
            item.add_marker(pytest.mark.acceptance)
            item.user_properties.append(("category", "acceptance"))
            continue

        if "client" in item.fixturenames:
            item.add_marker(pytest.mark.io)
            item.user_properties.append(("category", "io"))
            continue

        try:
            source = inspect.getsource(item.function)
        except (OSError, TypeError):
            source = ""
        if any(signal in source for signal in _IO_SIGNALS):
            item.add_marker(pytest.mark.io)
            item.user_properties.append(("category", "io"))
