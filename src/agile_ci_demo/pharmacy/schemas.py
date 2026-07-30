from __future__ import annotations

import datetime as dt

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)


class MedicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    form: str = Field(min_length=2, max_length=80)
    standard_dosage: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="units", min_length=1, max_length=40)
    initial_stock: int = Field(default=0, ge=0, le=1_000_000)
    reorder_level: int = Field(default=10, ge=0, le=1_000_000)
    is_active: bool = True

    @field_validator(
        "name",
        "form",
        "standard_dosage",
        "unit",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        value = " ".join(value.strip().split())
        if not value:
            raise ValueError("This field is required.")
        return value


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    form: str | None = Field(default=None, min_length=2, max_length=80)
    standard_dosage: str | None = Field(default=None, min_length=1, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    reorder_level: int | None = Field(default=None, ge=0, le=1_000_000)
    is_active: bool | None = None

    @field_validator(
        "name",
        "form",
        "standard_dosage",
        "unit",
    )
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
