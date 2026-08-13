from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from agile_ci_demo.core.database import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    staff_id: Mapped[int] = mapped_column(Integer, ForeignKey("staff.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    used_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class AuthAuditLog(Base):
    __tablename__ = "auth_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # The staff_id/patient_id of the account the event happened to, when known -
    # nullable because e.g. a login attempt against an unknown email has no account.
    user_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    # e.g. "login_success", "login_failed", "account_locked", "logout",
    # "patient_login_success", "patient_login_failed", "password_reset_requested",
    # "password_reset_completed", "password_changed".
    event: Mapped[str] = mapped_column(String(40), index=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, index=True
    )
