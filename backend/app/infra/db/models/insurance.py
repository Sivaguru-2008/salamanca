from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
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


class Insurance(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "insurances"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    policy_number: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(100), nullable=False)  # Life, Health, Vehicle, etc.
    coverage_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    premium_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    premium_frequency: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # MONTHLY, QUARTERLY, HALF_YEARLY, YEARLY
    renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    beneficiaries: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="ACTIVE"
    )  # ACTIVE, LAPSED, EXPIRED

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<Insurance id={self.id} user_id={self.user_id} "
            f"provider={self.provider} status={self.status}>"
        )
