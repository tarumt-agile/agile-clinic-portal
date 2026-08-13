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
        stmt = stmt.where(AuthAuditLog.created_at >= dt.datetime.combine(from_date, dt.time.min))
    if to_date is not None:
        stmt = stmt.where(AuthAuditLog.created_at <= dt.datetime.combine(to_date, dt.time.max))
    return list(db.execute(stmt).scalars().all())
