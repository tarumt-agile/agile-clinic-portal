from __future__ import annotations

import datetime as dt

import pytest

from agile_ci_demo.core import rate_limit


@pytest.fixture(autouse=True)
def _reset() -> None:
    rate_limit.reset_all()
    yield
    rate_limit.reset_all()


def test_not_locked_out_initially() -> None:
    assert rate_limit.is_locked_out("alice@example.com") is False


def test_four_failures_do_not_lock_out() -> None:
    for _ in range(4):
        just_locked = rate_limit.record_failure("alice@example.com")
        assert just_locked is False
    assert rate_limit.is_locked_out("alice@example.com") is False


def test_fifth_failure_triggers_lockout() -> None:
    for _ in range(4):
        rate_limit.record_failure("alice@example.com")
    just_locked = rate_limit.record_failure("alice@example.com")
    assert just_locked is True
    assert rate_limit.is_locked_out("alice@example.com") is True


def test_lockout_expires_after_the_configured_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "LOCKOUT_DURATION", dt.timedelta(seconds=-1))
    for _ in range(5):
        rate_limit.record_failure("alice@example.com")
    assert rate_limit.is_locked_out("alice@example.com") is False


def test_success_clears_the_failure_count() -> None:
    for _ in range(4):
        rate_limit.record_failure("alice@example.com")
    rate_limit.record_success("alice@example.com")
    for _ in range(4):
        just_locked = rate_limit.record_failure("alice@example.com")
        assert just_locked is False
    assert rate_limit.is_locked_out("alice@example.com") is False


def test_lockout_is_tracked_per_email() -> None:
    for _ in range(5):
        rate_limit.record_failure("alice@example.com")
    assert rate_limit.is_locked_out("alice@example.com") is True
    assert rate_limit.is_locked_out("bob@example.com") is False
