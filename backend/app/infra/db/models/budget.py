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


class Budget(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    monthly_budget: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    category_budgets: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # dict[str, float]
    budget_utilization: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # dict[str, float]
    budget_alerts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # dict[str, dict]

    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<Budget id={self.id} user_id={self.user_id} month={self.month} "
            f"total={self.monthly_budget}>"
        )
