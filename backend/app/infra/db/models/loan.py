from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import (
    GUID,
    JSONB,
    AuditMixin,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Loan(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "loans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # Personal, Education, etc.
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    apr: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    processing_fees: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    emi: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    remaining_tenure: Mapped[int] = mapped_column(Integer, nullable=False)  # in months
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    collateral: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ACTIVE"
    )  # ACTIVE, PAID_OFF, DEFAULTED
    payment_history: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<Loan id={self.id} user_id={self.user_id} name={self.name} "
            f"balance={self.outstanding_balance}>"
        )
