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


class Investment(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "investments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # Stocks, Mutual Funds, ETF, PPF, EPF, NPS, Bonds, Crypto, Gold, Other
    amount_invested: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    current_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 6), nullable=True)
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    ticker: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<Investment id={self.id} name={self.name} value={self.current_value}>"
