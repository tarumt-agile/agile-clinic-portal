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

from agile_ci_demo.auth.deps import require_role
from agile_ci_demo.core.database import get_db
from agile_ci_demo.core.rbac import Role
from agile_ci_demo.core.templates import templates
from agile_ci_demo.pharmacy.models import (
    Medication,
    StockTransaction,
)
from agile_ci_demo.pharmacy.schemas import (
    MedicationCreate,
    MedicationList,
    MedicationOut,
    MedicationUpdate,
    StockAdjustmentCreate,
    StockTransactionOut,
)
from agile_ci_demo.pharmacy.service import (
    DuplicateMedicationError,
    InvalidStockAdjustmentError,
    MedicationNotFoundError,
    adjust_stock,
    create_medication,
    get_medication_by_public_id,
    list_medications,
    list_stock_transactions,
    serialize_low_stock,
    update_medication,
)
from agile_ci_demo.staff.models import Staff

api_router = APIRouter(
    prefix="/api/pharmacy",
    tags=["pharmacy"],
)

pages_router = APIRouter(
    prefix="/pharmacy",
    tags=["pharmacy-pages"],
    include_in_schema=False,
)

_PHARMACY_ROLES = (
    Role.NURSE,
    Role.ADMIN,
)


def serialize_medication(
    medication: Medication,
) -> MedicationOut:
    return MedicationOut(
        medication_id=medication.medication_id or "",
        name=medication.name,
        form=medication.form,
        standard_dosage=medication.standard_dosage,
        prescription_value=medication.prescription_value,
        unit=medication.unit,
        stock_quantity=medication.stock_quantity,
        reorder_level=medication.reorder_level,
        is_active=medication.is_active,
        low_stock=serialize_low_stock(medication),
        created_at=medication.created_at,
        updated_at=medication.updated_at,
    )


def serialize_transaction(
    transaction: StockTransaction,
    medication: Medication,
) -> StockTransactionOut:
    return StockTransactionOut(
        transaction_id=transaction.transaction_id or "",
        medication_id=medication.medication_id or "",
        transaction_type=transaction.transaction_type,
        quantity_change=transaction.quantity_change,
        balance_after=transaction.balance_after,
        reason=transaction.reason,
        performed_by_staff_id=(
            transaction.performed_by_staff_public_id
        ),
        performed_by_staff_name=(
            transaction.performed_by_staff_name
        ),
        created_at=transaction.created_at,
    )


@api_router.get(
    "/medications",
    response_model=MedicationList,
)
def get_medications(
    q: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> MedicationList:
    medications = list_medications(
        db,
        q,
        include_inactive,
    )
    return MedicationList(
        items=[
            serialize_medication(item)
            for item in medications
        ],
        total=len(medications),
    )


@api_router.post(
    "/medications",
    response_model=MedicationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_medication(
    payload: MedicationCreate,
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> MedicationOut:
    try:
        medication = create_medication(
            db,
            payload,
            staff,
        )
    except DuplicateMedicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return serialize_medication(medication)


@api_router.get(
    "/medications/{medication_id}",
    response_model=MedicationOut,
)
def get_medication(
    medication_id: str,
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> MedicationOut:
    medication = get_medication_by_public_id(
        db,
        medication_id,
    )
    if medication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )
    return serialize_medication(medication)


@api_router.patch(
    "/medications/{medication_id}",
    response_model=MedicationOut,
)
def edit_medication(
    medication_id: str,
    payload: MedicationUpdate,
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> MedicationOut:
    try:
        medication = update_medication(
            db,
            medication_id,
            payload,
        )
    except MedicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateMedicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return serialize_medication(medication)


@api_router.post(
    "/medications/{medication_id}/stock-adjustments",
    response_model=MedicationOut,
)
def add_stock_adjustment(
    medication_id: str,
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> MedicationOut:
    try:
        medication, _transaction = adjust_stock(
            db,
            medication_id,
            payload,
            staff,
        )
    except MedicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvalidStockAdjustmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return serialize_medication(medication)


@api_router.get(
    "/medications/{medication_id}/transactions",
    response_model=list[StockTransactionOut],
)
def get_stock_transactions(
    medication_id: str,
    db: Session = Depends(get_db),
    _staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> list[StockTransactionOut]:
    try:
        transactions = list_stock_transactions(
            db,
            medication_id,
        )
    except MedicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    medication = get_medication_by_public_id(
        db,
        medication_id,
    )
    if medication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication not found.",
        )

    return [
        serialize_transaction(
            transaction,
            medication,
        )
        for transaction in transactions
    ]


@pages_router.get(
    "",
    response_class=HTMLResponse,
)
def pharmacy_page(
    request: Request,
    _staff: Staff = Depends(require_role(*_PHARMACY_ROLES)),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pharmacy/pharmacy_management.html",
        {},
    )
