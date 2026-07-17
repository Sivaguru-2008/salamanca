from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
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


class Liability(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "liabilities"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Credit Cards, Personal Loans, etc.
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<Liability id={self.id} user_id={self.user_id} name={self.name} "
            f"balance={self.outstanding_balance}>"
        )
