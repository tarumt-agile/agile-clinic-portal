from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from agile_ci_demo.auth.deps import require_patient, require_role
from agile_ci_demo.core.config import settings
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.pharmacy.service import (
    MedicationNotFoundError,
    search_active_medications,
)
from agile_ci_demo.prescriptions.models import (
    Prescription,
)
from agile_ci_demo.prescriptions.schemas import (
    MedicationOption,
    MedicationSearchResultOut,
    PrescriptionCreate,
    PrescriptionHistoryOut,
    PrescriptionInstructionUpdate,
    PrescriptionList,
    PrescriptionOptionsOut,
    PrescriptionOut,
    PrescriptionStatus,
)
from agile_ci_demo.prescriptions.service import (
    ConsultationRecordNotFoundError,
    DiagnosisNotFoundError,
    PrescriptionConflictError,
    PrescriptionNotFoundError,
    PrescriptionPermissionError,
    create_prescription,
    get_consultation_prescriptions,
    get_patient_prescriptions,
    get_prescription_by_public_id,
    get_prescription_options,
    update_prescription_instructions,
)
from agile_ci_demo.patients.models import Patient
from agile_ci_demo.staff.models import Staff

prescription_doctor = require_role(
    Role.DOCTOR,
    forbidden_for_wrong_role=True,
)
doctor_only_responses: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {
        "description": ("Forbidden: the authenticated staff member does not have the doctor role.")
    }
}

api_router = APIRouter(
    prefix="/api/prescriptions",
    tags=["prescriptions"],
)

pages_router = APIRouter(
    prefix="/prescriptions",
    tags=["prescription-pages"],
    include_in_schema=False,
)


def serialize_prescription(
    prescription: Prescription,
    current_doctor_id: int | None,
) -> PrescriptionOut:
    history = [
        PrescriptionHistoryOut(
            previous_dosage=(item.previous_dosage),
            new_dosage=item.new_dosage,
            previous_frequency=(item.previous_frequency),
            new_frequency=(item.new_frequency),
            previous_duration=(item.previous_duration),
            new_duration=(item.new_duration),
            change_reason=item.change_reason,
            changed_by_doctor_id=(item.changed_by_doctor.staff_id or ""),
            changed_by_doctor_name=(item.changed_by_doctor.full_name),
            changed_at=item.changed_at,
        )
        for item in prescription.history
    ]

    return PrescriptionOut(
        prescription_id=(prescription.prescription_id or ""),
        consultation_record_id=(prescription.consultation_note.record_id or ""),
        diagnosis_id=prescription.diagnosis.id,
        diagnosis_code=(prescription.diagnosis.icd10_code),
        diagnosis_description=(prescription.diagnosis.description),
        patient_id=(prescription.patient.patient_id or ""),
        patient_name=(prescription.patient.full_name),
        prescribing_doctor_id=(prescription.prescribing_doctor.staff_id or ""),
        prescribing_doctor_name=(prescription.prescribing_doctor.full_name),
        medication_id=(
            prescription.medication_record.medication_id
            if prescription.medication_record is not None
            else None
        ),
        medication_name=(
            prescription.medication_record.name
            if prescription.medication_record is not None
            else None
        ),
        medication_form=(
            prescription.medication_record.form
            if prescription.medication_record is not None
            else None
        ),
        medication_standard_dosage=(
            prescription.medication_record.standard_dosage
            if prescription.medication_record is not None
            else None
        ),
        medication=prescription.medication,
        dosage=prescription.dosage,
        frequency=prescription.frequency,
        duration=prescription.duration,
        status=PrescriptionStatus(prescription.status),
        issued_at=prescription.issued_at,
        updated_at=prescription.updated_at,
        can_edit=(
            current_doctor_id is not None
            and prescription.status == "active"
            and (prescription.prescribing_doctor_id == current_doctor_id)
        ),
        history=history,
    )


# This route returns prescription form options.
@api_router.get(
    "/options",
    response_model=PrescriptionOptionsOut,
)
def get_available_prescription_options(
    db: Session = Depends(get_db),
) -> PrescriptionOptionsOut:
    options = get_prescription_options(db)

    return PrescriptionOptionsOut(
        medications=[MedicationOption(**item) for item in options["medications"]],
        dosages=options["dosages"],
        frequencies=options["frequencies"],
        durations=options["durations"],
    )


@api_router.get(
    "/medications",
    response_model=list[MedicationSearchResultOut],
)
def search_medication_catalogue(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
    _doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> list[MedicationSearchResultOut]:
    return [
        MedicationSearchResultOut(
            medication_id=item.medication_id or "",
            name=item.name,
            form=item.form,
            standard_dosage=item.standard_dosage,
            prescription_value=item.prescription_value,
        )
        for item in search_active_medications(
            db,
            q,
            limit,
        )
    ]


# This route creates a prescription for one diagnosis.
@api_router.post(
    "",
    response_model=PrescriptionOut,
    status_code=status.HTTP_201_CREATED,
    responses=doctor_only_responses,
    summary="Create a prescription",
    description=(
        "Issues medication for a consultation diagnosis. Requires an authenticated "
        "staff JWT with the doctor role."
    ),
)
def create_prescription_endpoint(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(prescription_doctor),
) -> PrescriptionOut:
    try:
        prescription = create_prescription(
            db,
            payload,
            doctor,
        )

    except (
        ConsultationRecordNotFoundError,
        DiagnosisNotFoundError,
        MedicationNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PrescriptionPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except PrescriptionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return serialize_prescription(
        prescription,
        doctor.id,
    )


@pages_router.get(
    "/{prescription_id}",
    response_class=HTMLResponse,
)
def prescription_detail_page(
    request: Request,
    prescription_id: str,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(require_role(Role.DOCTOR)),
) -> HTMLResponse:
    prescription = get_prescription_by_public_id(
        db,
        prescription_id,
    )

    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    if prescription.prescribing_doctor_id != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the prescribing doctor can print this prescription.",
        )

    return templates.TemplateResponse(
        request,
        "prescriptions/prescription_print.html",
        {
            "prescription_id": prescription_id,
            "clinic_name": settings.clinic_name,
            "clinic_address": settings.clinic_address,
            "clinic_phone": settings.clinic_phone,
        },
    )


# This route returns a patient's prescriptions.
@api_router.get(
    "/patient/{patient_id}",
    response_model=PrescriptionList,
)
def get_patient_prescription_history(
    patient_id: str,
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> PrescriptionList:
    try:
        prescriptions = get_patient_prescriptions(
            db,
            patient_id,
        )

    except PrescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    current_doctor_id = staff.id if staff.role == Role.DOCTOR.value else None

    items = [
        serialize_prescription(
            item,
            current_doctor_id,
        )
        for item in prescriptions
    ]

    return PrescriptionList(
        items=items,
        total=len(items),
    )


# This route returns prescriptions for one consultation.
@api_router.get(
    "/consultation/{record_id}",
    response_model=PrescriptionList,
)
def get_prescriptions_for_consultation(
    record_id: str,
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> PrescriptionList:
    try:
        prescriptions = get_consultation_prescriptions(
            db,
            record_id,
        )

    except ConsultationRecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    current_doctor_id = staff.id if staff.role == Role.DOCTOR.value else None

    items = [
        serialize_prescription(
            item,
            current_doctor_id,
        )
        for item in prescriptions
    ]

    return PrescriptionList(
        items=items,
        total=len(items),
    )


# This route returns the logged-in patient's own prescriptions. Registered
# before the generic "/{prescription_id}" route below - FastAPI matches
# routes in registration order, so "mine" would otherwise be captured as a
# prescription_id path parameter instead of reaching this handler.
@api_router.get(
    "/mine",
    response_model=PrescriptionList,
)
def get_my_prescriptions(
    db: Session = Depends(get_db),
    patient: Patient = Depends(require_patient),
) -> PrescriptionList:
    try:
        prescriptions = get_patient_prescriptions(
            db,
            patient.patient_id or "",
        )
    except PrescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    items = [
        serialize_prescription(
            item,
            None,
        )
        for item in prescriptions
    ]

    return PrescriptionList(
        items=items,
        total=len(items),
    )


# This route returns one prescription.
@api_router.get(
    "/{prescription_id}",
    response_model=PrescriptionOut,
)
def get_prescription_details(
    prescription_id: str,
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(Role.DOCTOR, Role.NURSE, Role.RECEPTIONIST, Role.ADMIN)),
) -> PrescriptionOut:
    prescription = get_prescription_by_public_id(
        db,
        prescription_id,
    )

    if prescription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prescription not found.",
        )

    current_doctor_id = staff.id if staff.role == Role.DOCTOR.value else None

    return serialize_prescription(
        prescription,
        current_doctor_id,
    )


# This route updates prescription instructions.
@api_router.patch(
    "/{prescription_id}/instructions",
    response_model=PrescriptionOut,
    responses=doctor_only_responses,
    summary="Update prescription instructions",
    description=(
        "Updates dosage, frequency, and duration. Requires the doctor role and the "
        "authenticated doctor must be the original prescriber."
    ),
)
@api_router.patch(
    "/{prescription_id}/dosage",
    response_model=PrescriptionOut,
    responses=doctor_only_responses,
    summary="Update prescription dosage instructions",
    description=(
        "Backward-compatible alias for updating prescription instructions. Requires "
        "the doctor role and the authenticated doctor must be the original prescriber."
    ),
)
def update_prescription_instructions_endpoint(
    prescription_id: str,
    payload: PrescriptionInstructionUpdate,
    db: Session = Depends(get_db),
    doctor: Staff = Depends(prescription_doctor),
) -> PrescriptionOut:
    try:
        prescription = update_prescription_instructions(
            db,
            prescription_id,
            payload,
            doctor,
        )

    except PrescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except PrescriptionPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except PrescriptionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return serialize_prescription(
        prescription,
        doctor.id,
    )
