from __future__ import annotations

import datetime as dt

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

MEDICATION_FORM_OPTIONS = (
    "Tablet",
    "Capsule",
    "Oral liquid",
    "Syrup",
    "Suspension",
    "Inhaler",
    "Sachet",
    "Cream",
    "Ointment",
    "Gel",
    "Drops",
    "Injection",
    "Patch",
    "Suppository",
)

STANDARD_DOSAGE_OPTIONS = (
    "1 mg",
    "2 mg",
    "2.5 mg",
    "4 mg",
    "5 mg",
    "10 mg",
    "15 mg",
    "20 mg",
    "25 mg",
    "30 mg",
    "50 mg",
    "75 mg",
    "100 mg",
    "200 mg",
    "250 mg",
    "400 mg",
    "500 mg",
    "1 g",
    "100 mcg",
    "100 mcg/dose",
    "5 mg/5 mL",
    "100 mg/5 mL",
    "125 mg/5 mL",
    "250 mg/5 mL",
    "Product-specific",
)

STOCK_UNIT_OPTIONS = (
    "units",
    "tablets",
    "capsules",
    "bottles",
    "sachets",
    "inhalers",
    "tubes",
    "vials",
    "ampoules",
    "packs",
)


def _validate_controlled_option(
    value: str,
    *,
    options: tuple[str, ...],
    field_name: str,
) -> str:
    value = " ".join(value.strip().split())
    if value not in options:
        raise ValueError(f"Select a valid {field_name} from the available options.")
    return value


class MedicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    form: str = Field(min_length=2, max_length=80)
    standard_dosage: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="units", min_length=1, max_length=40)
    initial_stock: int = Field(default=0, ge=0, le=1_000_000)
    reorder_level: int = Field(default=10, ge=0, le=1_000_000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("form")
    @classmethod
    def validate_form(cls, value: str) -> str:
        return _validate_controlled_option(
            value,
            options=MEDICATION_FORM_OPTIONS,
            field_name="medication form",
        )

    @field_validator("standard_dosage")
    @classmethod
    def validate_standard_dosage(cls, value: str) -> str:
        return _validate_controlled_option(
            value,
            options=STANDARD_DOSAGE_OPTIONS,
            field_name="standard dosage",
        )

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        return _validate_controlled_option(
            value,
            options=STOCK_UNIT_OPTIONS,
            field_name="stock unit",
        )


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    form: str | None = Field(default=None, min_length=2, max_length=80)
    standard_dosage: str | None = Field(default=None, min_length=1, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("form")
    @classmethod
    def validate_optional_form(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _validate_controlled_option(
            value,
            options=MEDICATION_FORM_OPTIONS,
            field_name="medication form",
        )

    @field_validator("standard_dosage")
    @classmethod
    def validate_optional_standard_dosage(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _validate_controlled_option(
            value,
            options=STANDARD_DOSAGE_OPTIONS,
            field_name="standard dosage",
        )

    @field_validator("unit")
    @classmethod
    def validate_optional_unit(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return _validate_controlled_option(
            value,
            options=STOCK_UNIT_OPTIONS,
            field_name="stock unit",
        )

    @model_validator(mode="after")
    def require_change(self) -> "MedicationUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one medication field must be supplied.")
        return self


class StockAdjustmentCreate(BaseModel):
    quantity_change: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=3, max_length=255)

    @field_validator("quantity_change")
    @classmethod
    def quantity_must_change(cls, value: int) -> int:
        if value == 0:
            raise ValueError("Quantity change cannot be zero.")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("A stock-adjustment reason is required.")
        return value


class MedicationOut(BaseModel):
    medication_id: str
    name: str
    form: str
    standard_dosage: str
    prescription_value: str
    unit: str
    stock_quantity: int
    reorder_level: int
    is_active: bool
    low_stock: bool
    created_at: dt.datetime
    updated_at: dt.datetime


class MedicationList(BaseModel):
    items: list[MedicationOut]
    total: int


class StockTransactionOut(BaseModel):
    transaction_id: str
    medication_id: str
    transaction_type: str
    quantity_change: int
    balance_after: int
    reason: str
    performed_by_staff_id: str
    performed_by_staff_name: str
    created_at: dt.datetime
