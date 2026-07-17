"""transaction payment fields and INR currency migration

Revision ID: c3f1a2b4d5e6
Revises: 8af0f88ecea1
Create Date: 2026-07-17 09:14:02.118420
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3f1a2b4d5e6"
down_revision = "8af0f88ecea1"
branch_labels = None
depends_on = None

# Every table that carries a denormalised currency code.
CURRENCY_TABLES = (
    "financial_profiles",
    "incomes",
    "expenses",
    "assets",
    "liabilities",
    "investments",
    "savings_goals",
    "transactions",
)


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "payment_method",
            sa.String(length=50),
            nullable=False,
            server_default="Bank Transfer",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="Completed"),
    )
    op.create_index(
        op.f("ix_transactions_transaction_date"),
        "transactions",
        ["transaction_date"],
        unique=False,
    )

    # The product is India-only; existing rows were written under the old USD default.
    for table in CURRENCY_TABLES:
        op.execute(f"UPDATE {table} SET currency = 'INR' WHERE currency = 'USD'")  # noqa: S608


def downgrade() -> None:
    op.drop_index(op.f("ix_transactions_transaction_date"), table_name="transactions")
    op.drop_column("transactions", "status")
    op.drop_column("transactions", "payment_method")
