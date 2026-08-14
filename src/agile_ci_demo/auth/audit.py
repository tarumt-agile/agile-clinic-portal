from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from agile_ci_demo.auth.models import AuthAuditLog


def log_auth_event(
    db: Session,
    *,
    event: str,
    user_id: str | None = None,
    email: str | None = None,
    ip: str | None = None,
) -> AuthAuditLog:
    entry = AuthAuditLog(event=event, user_id=user_id, email=email, ip_address=ip)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _local_day_bounds_utc(date: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """The UTC datetime range covering a local calendar day.

    AuthAuditLog.created_at is stored in UTC (dt.datetime.utcnow(), like every
    other timestamp column in this codebase), but from_date/to_date come from
    an admin's date picker and mean their own local "today" - not the UTC day,
    which is a different date for several hours around local midnight in any
    timezone ahead of UTC. Converting the boundary (not the stored timestamps)
    keeps created_at's storage convention untouched everywhere else.
    """
    start_local = dt.datetime.combine(date, dt.time.min)
    end_local = dt.datetime.combine(date, dt.time.max)
    # astimezone() on a naive datetime presumes it's in the system's local
    # timezone and resolves the correct UTC offset for that specific date
    # (handling DST correctly, unlike a fixed offset computed from "now").
    start_utc = start_local.astimezone(dt.timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


def get_auth_audit_log(
    db: Session,
    *,
    from_date: dt.date | None = None,
    to_date: dt.date | None = None,
) -> list[AuthAuditLog]:
    """Audit log entries newest-first, optionally restricted to a date range
    (inclusive on both ends)."""
    stmt = select(AuthAuditLog).order_by(AuthAuditLog.created_at.desc())
    if from_date is not None:
        start, _ = _local_day_bounds_utc(from_date)
        stmt = stmt.where(AuthAuditLog.created_at >= start)
    if to_date is not None:
        _, end = _local_day_bounds_utc(to_date)
        stmt = stmt.where(AuthAuditLog.created_at <= end)
    return list(db.execute(stmt).scalars().all())
