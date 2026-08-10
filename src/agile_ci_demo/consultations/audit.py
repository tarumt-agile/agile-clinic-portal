from __future__ import annotations

import datetime as dt
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agile_ci_demo.consultations.models import ConsultationNote, MedicalAccessLog
from agile_ci_demo.core.email import send_email
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff

logger = logging.getLogger(__name__)

ALERT_THRESHOLD = 50
ALERT_WINDOW = dt.timedelta(hours=1)


def log_medical_access(
    db: Session, *, note: ConsultationNote, accessed_by: Staff, action: str
) -> None:
    entry = MedicalAccessLog(
        consultation_note_id=note.id,
        record_id=note.record_id,
        patient_id=note.patient_id,
        doctor_id=note.doctor_id,
        accessed_by_staff_id=accessed_by.id,
        action=action,
    )
    db.add(entry)
    db.commit()

    if action == "read":
        _check_excessive_reads(db, note)


def _check_excessive_reads(db: Session, note: ConsultationNote) -> None:
    window_start = dt.datetime.utcnow() - ALERT_WINDOW
    count = db.execute(
        select(func.count())
        .select_from(MedicalAccessLog)
        .where(
            MedicalAccessLog.consultation_note_id == note.id,
            MedicalAccessLog.action == "read",
            MedicalAccessLog.created_at >= window_start,
        )
    ).scalar_one()

    # Fire exactly once per crossing of the threshold, on the read that pushes
    # the count from 50 to 51 - not on every read after that, or every doctor
    # re-opening a chronic patient's chart would spam admins' inboxes.
    if count == ALERT_THRESHOLD + 1:
        _send_excessive_access_alert(db, note, count)


def _send_excessive_access_alert(db: Session, note: ConsultationNote, count: int) -> None:
    admins = (
        db.execute(select(Staff).where(Staff.role == Role.ADMIN.value, Staff.is_active.is_(True)))
        .scalars()
        .all()
    )

    for admin in admins:
        try:
            send_email(
                to=admin.email,
                subject="Unusual medical record access volume",
                body=(
                    f"Consultation record {note.record_id} has been read {count} times "
                    "in the past hour. This may indicate inappropriate access."
                ),
            )
        except Exception:
            logger.exception("Excessive-access alert email failed to send to %s", admin.email)


def get_medical_access_log(
    db: Session,
    *,
    patient_id: str | None = None,
    doctor_id: str | None = None,
) -> list[MedicalAccessLog]:
    stmt = select(MedicalAccessLog).order_by(MedicalAccessLog.created_at.desc())

    if patient_id:
        patient = db.execute(
            select(Patient).where(Patient.patient_id == patient_id)
        ).scalar_one_or_none()
        stmt = stmt.where(MedicalAccessLog.patient_id == (patient.id if patient else -1))

    if doctor_id:
        doctor = db.execute(select(Staff).where(Staff.staff_id == doctor_id)).scalar_one_or_none()
        stmt = stmt.where(MedicalAccessLog.doctor_id == (doctor.id if doctor else -1))

    return list(db.execute(stmt).scalars().all())
