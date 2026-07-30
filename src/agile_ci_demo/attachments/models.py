from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agile_ci_demo.core.database import Base
from agile_ci_demo.consultations.models import ConsultationNote
from agile_ci_demo.staff.models import Staff


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    consultation_note_id: Mapped[int] = mapped_column(
        ForeignKey("consultation_notes.id"), index=True
    )

    original_filename: Mapped[str] = mapped_column(String(255))

    # UUID4 + original extension. Never derived from user input, so it is safe to use
    # as an on-disk filename.
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)

    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)

    uploaded_by_staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    consultation_note: Mapped[ConsultationNote] = relationship()
    uploaded_by: Mapped[Staff] = relationship()
