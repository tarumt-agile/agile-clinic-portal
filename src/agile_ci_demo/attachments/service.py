from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from agile_ci_demo.attachments.models import Attachment
from agile_ci_demo.core.config import settings
from agile_ci_demo.consultations.service import get_consultation_note_by_record_id

MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class ConsultationNoteNotFoundError(Exception):
    """Raised when a consultation record_id does not match any stored note."""


class InvalidAttachmentError(Exception):
    """Raised when an uploaded file fails type or size validation."""


def _validate_upload(upload: UploadFile, size_bytes: int) -> None:
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidAttachmentError(
            "Unsupported file type. Only PDF, JPG, and PNG files are accepted."
        )
    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        raise InvalidAttachmentError("File is too large. The maximum size is 5 MB.")


def save_attachment(
    db: Session,
    consultation_record_id: str,
    upload: UploadFile,
    uploaded_by_staff_id: int,
) -> Attachment:
    """Validate, store on disk, and record a new attachment for a consultation note."""
    note = get_consultation_note_by_record_id(db, consultation_record_id)
    if note is None:
        raise ConsultationNoteNotFoundError(
            f"No consultation record found with record_id '{consultation_record_id}'"
        )

    contents = upload.file.read()
    _validate_upload(upload, len(contents))

    assert upload.content_type is not None  # guaranteed by _validate_upload above
    extension = ALLOWED_CONTENT_TYPES[upload.content_type]
    stored_filename = f"{uuid.uuid4().hex}{extension}"

    settings.attachments_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.attachments_dir / stored_filename
    destination.write_bytes(contents)

    attachment = Attachment(
        consultation_note_id=note.id,
        original_filename=upload.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=upload.content_type,
        size_bytes=len(contents),
        uploaded_by_staff_id=uploaded_by_staff_id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def list_attachments(db: Session, consultation_record_id: str) -> list[Attachment]:
    note = get_consultation_note_by_record_id(db, consultation_record_id)
    if note is None:
        raise ConsultationNoteNotFoundError(
            f"No consultation record found with record_id '{consultation_record_id}'"
        )
    return list(
        db.execute(
            select(Attachment)
            .where(Attachment.consultation_note_id == note.id)
            .order_by(Attachment.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_attachment(db: Session, attachment_id: int) -> Attachment | None:
    return db.get(Attachment, attachment_id)


def attachment_file_path(attachment: Attachment) -> Path:
    return settings.attachments_dir / attachment.stored_filename
