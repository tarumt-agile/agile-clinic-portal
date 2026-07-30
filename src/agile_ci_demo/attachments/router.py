from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from agile_ci_demo.attachments.models import Attachment
from agile_ci_demo.attachments.schemas import AttachmentOut
from agile_ci_demo.attachments.service import (
    ConsultationNoteNotFoundError,
    InvalidAttachmentError,
    attachment_file_path,
    get_attachment,
    list_attachments,
    save_attachment,
)
from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.staff.models import Staff

api_router = APIRouter(prefix="/api/attachments", tags=["attachments"])

_ALLOWED_ROLES = (Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)


def _serialize(attachment: Attachment) -> AttachmentOut:
    return AttachmentOut(
        id=attachment.id,
        original_filename=attachment.original_filename,
        content_type=attachment.content_type,
        size_bytes=attachment.size_bytes,
        uploaded_by_name=attachment.uploaded_by.full_name,
        created_at=attachment.created_at,
    )


@api_router.post("", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    consultation_record_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(*_ALLOWED_ROLES)),
) -> AttachmentOut:
    try:
        attachment = save_attachment(db, consultation_record_id, file, staff.id)
    except ConsultationNoteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidAttachmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _serialize(attachment)


@api_router.get("", response_model=list[AttachmentOut])
def get_attachments(
    record_id: str = Query(..., description="Consultation record's public record_id"),
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_ALLOWED_ROLES)),
) -> list[AttachmentOut]:
    try:
        attachments = list_attachments(db, record_id)
    except ConsultationNoteNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [_serialize(a) for a in attachments]


@api_router.get("/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_ALLOWED_ROLES)),
) -> FileResponse:
    attachment = get_attachment(db, attachment_id)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    file_path = attachment_file_path(attachment)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found"
        )

    return FileResponse(
        path=file_path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
    )
