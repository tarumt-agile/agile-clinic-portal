from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from agile_ci_demo.core.database import Base
from agile_ci_demo.staff.models import Staff


class Medication(Base):
    __tablename__ = "medications"
    __table_args__ = (
        UniqueConstraint(
            "name",
            "form",
            "standard_dosage",
            name="uq_medication_name_form_dosage",
        ),
        CheckConstraint(
            "stock_quantity >= 0",
            name="ck_medication_non_negative_stock",
        ),
        CheckConstraint(
            "reorder_level >= 0",
            name="ck_medication_non_negative_reorder_level",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    medication_id: Mapped[str | None] = mapped_column(
        String(12),
        unique=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        index=True,
    )

    form: Mapped[str] = mapped_column(
        String(80),
        index=True,
    )

    standard_dosage: Mapped[str] = mapped_column(
        String(80),
        index=True,
    )

    prescription_value: Mapped[str] = mapped_column(
        String(180),
        unique=True,
        index=True,
    )

    unit: Mapped[str] = mapped_column(
        String(40),
        default="units",
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    reorder_level: Mapped[int] = mapped_column(
        Integer,
        default=10,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
    )

    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
    )

    stock_transactions: Mapped[list["StockTransaction"]] = relationship(
        back_populates="medication",
        cascade="all, delete-orphan",
        order_by="StockTransaction.created_at.desc()",
    )


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    transaction_id: Mapped[str | None] = mapped_column(
        String(14),
        unique=True,
        index=True,
    )

    medication_id: Mapped[int] = mapped_column(
        ForeignKey("medications.id"),
        index=True,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(30),
        index=True,
    )

    quantity_change: Mapped[int] = mapped_column(
        Integer,
    )

    balance_after: Mapped[int] = mapped_column(
        Integer,
    )

    reason: Mapped[str] = mapped_column(
        String(255),
    )

    performed_by_staff_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "staff.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    performed_by_staff_public_id: Mapped[str] = mapped_column(
        String(12),
    )

    performed_by_staff_name: Mapped[str] = mapped_column(
        String(120),
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        default=dt.datetime.utcnow,
        index=True,
    )

    medication: Mapped[Medication] = relationship(
        back_populates="stock_transactions",
    )

    performed_by_staff: Mapped[Staff | None] = relationship(
        foreign_keys=[performed_by_staff_id],
    )
