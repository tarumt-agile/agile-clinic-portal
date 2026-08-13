"""Per-email failed-login tracking and lockout.

An in-memory dict stands in for a real cache (this app has no Redis/memcached
dependency - see pyproject.toml) - fine for a single-process teaching app, but
means this state is lost on restart and isn't shared across worker processes.
"""

from __future__ import annotations

import datetime as dt

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = dt.timedelta(minutes=15)

_failed_attempts: dict[str, int] = {}
_locked_until: dict[str, dt.datetime] = {}


def is_locked_out(email: str) -> bool:
    """Whether email is currently locked out. Clears an expired lockout as a side effect."""
    until = _locked_until.get(email)
    if until is None:
        return False
    if dt.datetime.utcnow() >= until:
        _locked_until.pop(email, None)
        _failed_attempts.pop(email, None)
        return False
    return True


def record_failure(email: str) -> bool:
    """Record a failed login attempt for email.

    Returns True iff this attempt was the one that just triggered the lockout
    (the 5th consecutive failure) - callers use that to fire a one-time alert.
    """
    count = _failed_attempts.get(email, 0) + 1
    if count >= MAX_FAILED_ATTEMPTS:
        _locked_until[email] = dt.datetime.utcnow() + LOCKOUT_DURATION
        _failed_attempts.pop(email, None)
        return True
    _failed_attempts[email] = count
    return False


def record_success(email: str) -> None:
    """Clear a successful login's failure count (lockouts already block login attempts)."""
    _failed_attempts.pop(email, None)


def reset_all() -> None:
    """Test-only: clear all tracked attempts and lockouts between tests."""
    _failed_attempts.clear()
    _locked_until.clear()
