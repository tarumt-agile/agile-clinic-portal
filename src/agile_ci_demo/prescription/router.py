from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.service import (
    get_current_doctor,
)
from agile_ci_demo.core.database import get_db
from agile_ci_demo.prescription.models import (
    Prescription,
)
from agile_ci_demo.prescription.schemas import (
    MedicationOption,
    PrescriptionCreate,
    PrescriptionHistoryOut,
    PrescriptionInstructionUpdate,
    PrescriptionList,
    PrescriptionOptionsOut,
    PrescriptionOut,
    PrescriptionStatus,
)
from agile_ci_demo.prescription.service import (
    ConsultationRecordNotFoundError,
    CurrentDoctorNotFoundError,
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

api_router = APIRouter(
    prefix="/api/prescriptions",
    tags=["prescriptions"],
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
def get_available_prescription_options() -> PrescriptionOptionsOut:
    options = get_prescription_options()

    return PrescriptionOptionsOut(
        medications=[MedicationOption(**item) for item in options["medications"]],
        dosages=options["dosages"],
        frequencies=options["frequencies"],
        durations=options["durations"],
    )


# This route creates a prescription for one diagnosis.
@api_router.post(
    "",
    response_model=PrescriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_prescription_endpoint(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
) -> PrescriptionOut:
    try:
        prescription = create_prescription(
            db,
            payload,
        )

    except (
        ConsultationRecordNotFoundError,
        DiagnosisNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except CurrentDoctorNotFoundError as exc:
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

    current_doctor = get_current_doctor(db)

    return serialize_prescription(
        prescription,
        current_doctor.id if current_doctor else None,
    )


# This route returns a patient's prescriptions.
@api_router.get(
    "/patient/{patient_id}",
    response_model=PrescriptionList,
)
def get_patient_prescription_history(
    patient_id: str,
    db: Session = Depends(get_db),
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

    current_doctor = get_current_doctor(db)

    items = [
        serialize_prescription(
            item,
            current_doctor.id if current_doctor else None,
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

    current_doctor = get_current_doctor(db)

    items = [
        serialize_prescription(
            item,
            current_doctor.id if current_doctor else None,
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

    current_doctor = get_current_doctor(db)

    return serialize_prescription(
        prescription,
        current_doctor.id if current_doctor else None,
    )


# This route updates prescription instructions.
@api_router.patch(
    "/{prescription_id}/instructions",
    response_model=PrescriptionOut,
)
@api_router.patch(
    "/{prescription_id}/dosage",
    response_model=PrescriptionOut,
)
def update_prescription_instructions_endpoint(
    prescription_id: str,
    payload: PrescriptionInstructionUpdate,
    db: Session = Depends(get_db),
) -> PrescriptionOut:
    try:
        prescription = update_prescription_instructions(
            db,
            prescription_id,
            payload,
        )

    except PrescriptionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except CurrentDoctorNotFoundError as exc:
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

    current_doctor = get_current_doctor(db)

    return serialize_prescription(
        prescription,
        current_doctor.id if current_doctor else None,
    )
