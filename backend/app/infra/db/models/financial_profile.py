from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
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


class FinancialProfile(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditMixin, Base):
    __tablename__ = "financial_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    risk_profile: Mapped[str] = mapped_column(
        String(50), nullable=False, default="MEDIUM"
    )  # LOW, MEDIUM, HIGH
    financial_literacy_level: Mapped[str] = mapped_column(
        String(50), nullable=False, default="BEGINNER"
    )  # BEGINNER, INTERMEDIATE, ADVANCED
    personal_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    financial_preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<FinancialProfile id={self.id} user_id={self.user_id}>"
