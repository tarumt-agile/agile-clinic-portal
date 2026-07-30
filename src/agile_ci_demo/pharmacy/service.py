from __future__ import annotations

from sqlalchemy import (
    func,
    or_,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agile_ci_demo.pharmacy.models import (
    Medication,
    StockTransaction,
)
from agile_ci_demo.pharmacy.schemas import (
    MedicationCreate,
    MedicationUpdate,
    StockAdjustmentCreate,
)
from agile_ci_demo.staff.models import Staff

DEFAULT_MEDICATIONS = [
    ("Amoxicillin", "Capsule", "250 mg"),
    ("Amoxicillin", "Capsule", "500 mg"),
    ("Azithromycin", "Tablet", "250 mg"),
    ("Cetirizine", "Tablet", "10 mg"),
    ("Chlorpheniramine", "Tablet", "4 mg"),
    ("Diclofenac", "Tablet", "50 mg"),
    ("Ibuprofen", "Tablet", "200 mg"),
    ("Ibuprofen", "Tablet", "400 mg"),
    ("Loratadine", "Tablet", "10 mg"),
    ("Metformin", "Tablet", "500 mg"),
    ("Omeprazole", "Capsule", "20 mg"),
    ("Paracetamol", "Tablet", "500 mg"),
    ("Salbutamol", "Inhaler", "100 mcg"),
    ("Cough Mixture", "Oral liquid", "Product-specific"),
    ("Oral Rehydration Salts", "Sachet", "Product-specific"),
]


class MedicationNotFoundError(Exception):
    """Raised when a medication cannot be found."""


class DuplicateMedicationError(Exception):
    """Raised when a medication with the same identity already exists."""


class InvalidStockAdjustmentError(Exception):
    """Raised when a stock adjustment would produce an invalid balance."""


def build_prescription_value(
    name: str,
    form: str,
    standard_dosage: str,
) -> str:
    if standard_dosage.casefold() == "product-specific":
        return name
    return f"{name} {standard_dosage} {form}"


def seed_default_medications(db: Session) -> None:
    """Insert the bundled medication catalogue without overwriting managed data."""

    existing_values = set(
        db.execute(select(Medication.prescription_value)).scalars().all()
    )
    created: list[Medication] = []

    for name, form, standard_dosage in DEFAULT_MEDICATIONS:
        prescription_value = build_prescription_value(
            name,
            form,
            standard_dosage,
        )

        if prescription_value in existing_values:
            continue

        medication = Medication(
            name=name,
            form=form,
            standard_dosage=standard_dosage,
            prescription_value=prescription_value,
            unit="units",
            stock_quantity=0,
            reorder_level=10,
            is_active=True,
        )
        db.add(medication)
        created.append(medication)

    if not created:
        return

    db.flush()

    for medication in created:
        medication.medication_id = f"M{medication.id:05d}"

    db.commit()


def serialize_low_stock(medication: Medication) -> bool:
    return medication.stock_quantity <= medication.reorder_level


def get_medication_by_public_id(
    db: Session,
    medication_id: str,
) -> Medication | None:
    return db.execute(
        select(Medication).where(
            Medication.medication_id == medication_id,
        )
    ).scalar_one_or_none()


def list_medications(
    db: Session,
    query: str | None = None,
    include_inactive: bool = False,
) -> list[Medication]:
    statement = select(Medication)

    if not include_inactive:
        statement = statement.where(Medication.is_active.is_(True))

    normalized_query = " ".join((query or "").strip().split())
    if normalized_query:
        pattern = f"%{normalized_query}%"
        statement = statement.where(
            or_(
                Medication.medication_id.ilike(pattern),
                Medication.name.ilike(pattern),
                Medication.form.ilike(pattern),
                Medication.standard_dosage.ilike(pattern),
                Medication.prescription_value.ilike(pattern),
            )
        )

    statement = statement.order_by(
        Medication.name.asc(),
        Medication.standard_dosage.asc(),
        Medication.form.asc(),
    )

    return list(db.execute(statement).scalars().all())


def search_active_medications(
    db: Session,
    keyword: str,
    limit: int = 8,
) -> list[Medication]:
    normalized_keyword = " ".join(keyword.strip().split())
    if not normalized_keyword:
        return []

    pattern = f"%{normalized_keyword}%"
    statement = (
        select(Medication)
        .where(Medication.is_active.is_(True))
        .where(
            or_(
                Medication.name.ilike(pattern),
                Medication.form.ilike(pattern),
                Medication.standard_dosage.ilike(pattern),
                Medication.prescription_value.ilike(pattern),
            )
        )
        .order_by(
            Medication.name.asc(),
            Medication.standard_dosage.asc(),
            Medication.form.asc(),
        )
        .limit(limit)
    )

    return list(db.execute(statement).scalars().all())


def create_medication(
    db: Session,
    data: MedicationCreate,
    staff: Staff,
) -> Medication:
    prescription_value = build_prescription_value(
        data.name,
        data.form,
        data.standard_dosage,
    )

    duplicate = db.execute(
        select(Medication).where(
            func.lower(Medication.prescription_value)
            == prescription_value.casefold()
        )
    ).scalar_one_or_none()

    if duplicate is not None:
        raise DuplicateMedicationError(
            "A medication with the same name, form, and standard dosage already exists."
        )

    medication = Medication(
        name=data.name,
        form=data.form,
        standard_dosage=data.standard_dosage,
        prescription_value=prescription_value,
        unit=data.unit,
        stock_quantity=data.initial_stock,
        reorder_level=data.reorder_level,
        is_active=data.is_active,
    )
    db.add(medication)

    try:
        db.flush()
        medication.medication_id = f"M{medication.id:05d}"

        if data.initial_stock:
            transaction = StockTransaction(
                medication_id=medication.id,
                transaction_type="initial_stock",
                quantity_change=data.initial_stock,
                balance_after=data.initial_stock,
                reason="Initial stock entered when the medication was created.",
                performed_by_staff_id=staff.id,
                performed_by_staff_public_id=staff.staff_id or "",
                performed_by_staff_name=staff.full_name,
            )
            db.add(transaction)
            db.flush()
            transaction.transaction_id = f"ST{transaction.id:07d}"

        db.commit()
        db.refresh(medication)

    except IntegrityError as exc:
        db.rollback()
        raise DuplicateMedicationError(
            "A medication with the same name, form, and standard dosage already exists."
        ) from exc

    return medication


def update_medication(
    db: Session,
    medication_id: str,
    data: MedicationUpdate,
) -> Medication:
    medication = get_medication_by_public_id(
        db,
        medication_id,
    )
    if medication is None:
        raise MedicationNotFoundError("Medication not found.")

    name = data.name if data.name is not None else medication.name
    form = data.form if data.form is not None else medication.form
    dosage = (
        data.standard_dosage
        if data.standard_dosage is not None
        else medication.standard_dosage
    )
    prescription_value = build_prescription_value(
        name,
        form,
        dosage,
    )

    duplicate = db.execute(
        select(Medication)
        .where(
            func.lower(Medication.prescription_value)
            == prescription_value.casefold()
        )
        .where(Medication.id != medication.id)
    ).scalar_one_or_none()
    if duplicate is not None:
        raise DuplicateMedicationError(
            "A medication with the same name, form, and standard dosage already exists."
        )

    medication.name = name
    medication.form = form
    medication.standard_dosage = dosage
    medication.prescription_value = prescription_value

    if data.unit is not None:
        medication.unit = data.unit
    if data.reorder_level is not None:
        medication.reorder_level = data.reorder_level
    if data.is_active is not None:
        medication.is_active = data.is_active

    try:
        db.commit()
        db.refresh(medication)
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateMedicationError(
            "A medication with the same name, form, and standard dosage already exists."
        ) from exc

    return medication


def adjust_stock(
    db: Session,
    medication_id: str,
    data: StockAdjustmentCreate,
    staff: Staff,
) -> tuple[Medication, StockTransaction]:
    medication = db.execute(
        select(Medication)
        .where(Medication.medication_id == medication_id)
        .with_for_update()
    ).scalar_one_or_none()
    if medication is None:
        raise MedicationNotFoundError("Medication not found.")

    balance_after = medication.stock_quantity + data.quantity_change
    if balance_after < 0:
        raise InvalidStockAdjustmentError(
            "Stock cannot be reduced below zero."
        )

    medication.stock_quantity = balance_after
    transaction = StockTransaction(
        medication_id=medication.id,
        transaction_type=(
            "stock_in"
            if data.quantity_change > 0
            else "stock_out"
        ),
        quantity_change=data.quantity_change,
        balance_after=balance_after,
        reason=data.reason,
        performed_by_staff_id=staff.id,
        performed_by_staff_public_id=staff.staff_id or "",
        performed_by_staff_name=staff.full_name,
    )
    db.add(transaction)

    try:
        db.flush()
        transaction.transaction_id = f"ST{transaction.id:07d}"
        db.commit()
        db.refresh(medication)
        db.refresh(transaction)
    except IntegrityError as exc:
        db.rollback()
        raise InvalidStockAdjustmentError(
            "The stock adjustment could not be saved."
        ) from exc

    return medication, transaction


def list_stock_transactions(
    db: Session,
    medication_id: str,
) -> list[StockTransaction]:
    medication = get_medication_by_public_id(
        db,
        medication_id,
    )
    if medication is None:
        raise MedicationNotFoundError("Medication not found.")

    statement = (
        select(StockTransaction)
        .where(StockTransaction.medication_id == medication.id)
        .order_by(
            StockTransaction.created_at.desc(),
            StockTransaction.id.desc(),
        )
    )
    return list(db.execute(statement).scalars().all())
