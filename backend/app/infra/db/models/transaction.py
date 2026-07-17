from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infra.db.base import (
    GUID,
    AuditMixin,
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class Transaction(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # Income, Expense, Transfer, Investment, Loan Payment, Insurance Premium, Refund
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Bank Transfer"
    )  # UPI, Bank Transfer, Credit Card, Debit Card, Cash, Net Banking, Auto Debit
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Completed"
    )  # Completed, Pending, Failed
    reference_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Links to Loan, Asset, Investment, etc.

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Transaction id={self.id} type={self.type} amount={self.amount}>"
