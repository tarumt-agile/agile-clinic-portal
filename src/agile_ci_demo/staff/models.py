from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from agile_ci_demo.core.database import Base


class Staff(Base):
    __tablename__ = "staff"

    # Internal auto-increment primary key, used only to derive staff_id.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Public-facing, human-readable unique identifier, e.g. "S00001".
    # Nullable at the DB level only because it is derived from `id` after the
    # initial flush (see staff.service.create_staff) - the service layer
    # guarantees it is always set before commit.
    staff_id: Mapped[str | None] = mapped_column(String(10), unique=True, index=True)

    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(30))
    # Only set when role="doctor" - other roles have no specialty.
    specialty: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )
