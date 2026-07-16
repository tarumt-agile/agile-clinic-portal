from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from agile_ci_demo.core.email import send_email
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.security import generate_temp_password, hash_password
from agile_ci_demo.staff.models import DoctorProfile, Staff
from agile_ci_demo.staff.schemas import DoctorCreate, DoctorOut, DoctorRegister, StaffCreate


class DuplicateStaffEmailError(Exception):
    """Raised when a staff account with the same email already exists."""


class StaffNotFoundError(Exception):
    """Raised when a staff_id does not match any stored staff account."""

class DoctorEmailAlreadyExistsError(Exception):
    """Raised when a staff account with the same email already exists."""
    
class DuplicateDoctorLicenseError(Exception):
    """Raised when a doctor profile with the same license number already exists."""

class DoctorProfileAlreadyExistsError(Exception):
    """Raised when the selected staff account already has a doctor profile."""

class StaffAccountIsNotDoctorError(Exception):
    """Raised when the selected staff account is not using the doctor role."""

class DoctorNotFoundError(Exception):
    """Raised when a doctor_id does not match any doctor profile."""


def create_staff(db: Session, data: StaffCreate) -> Staff:
    """Create a staff account with a generated temporary password and email it to them."""
    existing = db.execute(select(Staff).where(Staff.email == data.email)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateStaffEmailError(f"A staff account with email '{data.email}' already exists")

    temp_password = generate_temp_password()
    staff = Staff(
        full_name=data.full_name,
        email=data.email,
        role=data.role.value,
        password_hash=hash_password(temp_password),
        must_change_password=True,
        is_active=True,
    )
    db.add(staff)

    try:
        db.flush()
        staff.staff_id = f"S{staff.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateStaffEmailError(
            "Staff account could not be created due to a conflict"
        ) from exc

    db.refresh(staff)

    send_email(
        to=staff.email,
        subject="Welcome to Agile Clinic Portal",
        body=(
            f"Hi {staff.full_name},\n\n"
            f"An account has been created for you as {staff.role}.\n"
            f"Your temporary password is: {temp_password}\n\n"
            "Please log in and change your password as soon as possible."
        ),
    )

    return staff


def list_staff(db: Session) -> list[Staff]:
    return list(
        db.execute(
            select(Staff)
            .options(selectinload(Staff.doctor_profile))
            .order_by(Staff.id)
        )
        .scalars()
        .all()
    )


def get_staff_by_staff_id(db: Session, staff_id: str) -> Staff | None:
    return db.execute(
        select(Staff)
        .options(selectinload(Staff.doctor_profile))
        .where(Staff.staff_id == staff_id)
    ).scalar_one_or_none()


def set_staff_active_status(db: Session, staff_id: str, is_active: bool) -> Staff:
    """Activate or deactivate a staff account."""
    staff = get_staff_by_staff_id(db, staff_id)
    if staff is None:
        raise StaffNotFoundError(f"No staff account found with staff_id '{staff_id}'")

    staff.is_active = is_active
    db.commit()
    db.refresh(staff)
    return staff


def list_available_doctor_staff_accounts(db: Session) -> list[Staff]:
    """Return doctor-role staff accounts that are not linked to a doctor profile yet."""
    return list(
        db.execute(
            select(Staff)
            .outerjoin(DoctorProfile, DoctorProfile.staff_account_id == Staff.id)
            .where(Staff.role == Role.DOCTOR.value)
            .where(DoctorProfile.id.is_(None))
            .order_by(Staff.full_name)
        )
        .scalars()
        .all()
    )


def create_doctor_profile(db: Session, data: DoctorCreate) -> DoctorOut:
    """Create a doctor profile linked to an existing staff account."""
    staff = get_staff_by_staff_id(db, data.staff_id)
    if staff is None:
        raise StaffNotFoundError(f"No staff account found with staff_id '{data.staff_id}'")

    if staff.role != Role.DOCTOR.value:
        raise StaffAccountIsNotDoctorError(
            "Doctor profile can only be linked to a staff account with doctor role"
        )

    if staff.doctor_profile is not None:
        raise DoctorProfileAlreadyExistsError(
            f"Staff account '{data.staff_id}' already has a doctor profile"
        )

    existing_license = db.execute(
        select(DoctorProfile).where(DoctorProfile.license_number == data.license_number)
    ).scalar_one_or_none()

    if existing_license is not None:
        raise DuplicateDoctorLicenseError(
            f"Doctor license number '{data.license_number}' already exists"
        )

    doctor = DoctorProfile(
        staff_account_id=staff.id,
        license_number=data.license_number,
        specialty=data.specialty.value,
        department=data.department,
        status=data.status.value,
    )
    db.add(doctor)

    try:
        db.flush()
        doctor.doctor_id = f"D{doctor.id:05d}"
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateDoctorLicenseError(
            "Doctor profile could not be created due to a duplicate license number"
        ) from exc

    db.refresh(doctor)
    db.refresh(staff)

    return DoctorOut(
        doctor_id=doctor.doctor_id or "",
        staff_id=staff.staff_id or "",
        full_name=staff.full_name,
        email=staff.email,
        license_number=doctor.license_number,
        specialty=doctor.specialty,
        department=doctor.department,
        status=doctor.status,
        created_at=doctor.created_at,
    )


def list_doctors(db: Session) -> list[DoctorOut]:
    rows = db.execute(
        select(DoctorProfile, Staff)
        .join(Staff, DoctorProfile.staff_account_id == Staff.id)
        .order_by(Staff.full_name)
    ).all()

    return [
        DoctorOut(
            doctor_id=doctor.doctor_id or "",
            staff_id=staff.staff_id or "",
            full_name=staff.full_name,
            email=staff.email,
            license_number=doctor.license_number,
            specialty=doctor.specialty,
            department=doctor.department,
            status=doctor.status,
            created_at=doctor.created_at,
        )
        for doctor, staff in rows
    ]

def get_doctor_by_doctor_id(
    db: Session,
    doctor_id: str,
) -> DoctorOut:
    """Return one doctor and the linked staff account."""

    row = db.execute(
        select(DoctorProfile, Staff)
        .join(
            Staff,
            DoctorProfile.staff_account_id == Staff.id,
        )
        .where(DoctorProfile.doctor_id == doctor_id)
    ).one_or_none()

    if row is None:
        raise DoctorNotFoundError(
            f"No doctor profile found with doctor_id '{doctor_id}'"
        )

    doctor, staff = row

    return DoctorOut(
        doctor_id=doctor.doctor_id or "",
        staff_id=staff.staff_id or "",
        full_name=staff.full_name,
        email=staff.email,
        license_number=doctor.license_number,
        specialty=doctor.specialty,
        department=doctor.department,
        status=doctor.status,
        created_at=doctor.created_at,
    )

def create_doctor_with_account(db: Session, data: DoctorRegister) -> DoctorOut:
    """Create a doctor staff account and doctor profile together from the admin page."""

    existing_email = db.execute(
        select(Staff).where(Staff.email == data.email)
    ).scalar_one_or_none()

    if existing_email is not None:
        raise DoctorEmailAlreadyExistsError(
            f"A staff account with email '{data.email}' already exists"
        )

    existing_license = db.execute(
        select(DoctorProfile).where(DoctorProfile.license_number == data.license_number)
    ).scalar_one_or_none()

    if existing_license is not None:
        raise DuplicateDoctorLicenseError(
            f"Doctor license number '{data.license_number}' already exists"
        )

    temp_password = generate_temp_password()

    staff = Staff(
        full_name=data.full_name,
        email=str(data.email).lower(),
        role=Role.DOCTOR.value,
        password_hash=hash_password(temp_password),
        must_change_password=True,
        is_active=data.status == DoctorStatus.ACTIVE,
    )

    db.add(staff)

    try:
        db.flush()
        staff.staff_id = f"S{staff.id:05d}"

        doctor = DoctorProfile(
            staff_account_id=staff.id,
            license_number=data.license_number,
            specialty=data.specialty.value,
            department="Clinical Services",
            status=data.status.value,
        )

        db.add(doctor)
        db.flush()
        doctor.doctor_id = f"D{doctor.id:05d}"

        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise DuplicateDoctorLicenseError(
            "Doctor could not be created because the email or license number already exists"
        ) from exc

    db.refresh(staff)
    db.refresh(doctor)

    send_email(
        to=staff.email,
        subject="Welcome to Agile Clinic Portal",
        body=(
            f"Hi {staff.full_name},\n\n"
            "Your doctor account has been created.\n"
            f"Your temporary password is: {temp_password}\n\n"
            "Please log in and change your password as soon as possible."
        ),
    )

    return DoctorOut(
        doctor_id=doctor.doctor_id or "",
        staff_id=staff.staff_id or "",
        full_name=staff.full_name,
        email=staff.email,
        license_number=doctor.license_number,
        specialty=doctor.specialty,
        department=doctor.department,
        status=doctor.status,
        created_at=doctor.created_at,
    )