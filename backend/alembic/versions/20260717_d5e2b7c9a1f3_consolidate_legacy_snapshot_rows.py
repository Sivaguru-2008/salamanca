"""consolidate legacy dashboard-snapshot rows onto the financial data records

The retired "Save Snapshot" panel wrote rows named 'Primary Income',
'Living Expenses' and 'Savings Balance', and could write more than one of each
per user. The Financial Data Upload form reads a single canonical row per
figure, so without this migration an existing user would have their old rows
counted *in addition to* whatever they upload, inflating monthly income and
assets.

For each user: keep the most recently updated legacy row, rename it to the
canonical name, and soft-delete any duplicates.

Revision ID: d5e2b7c9a1f3
Revises: c3f1a2b4d5e6
Create Date: 2026-07-17 10:02:41.775310
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "d5e2b7c9a1f3"
down_revision = "c3f1a2b4d5e6"
branch_labels = None
depends_on = None

# (table, column holding the name, legacy value, canonical value, extra SET clause)
MIGRATIONS = [
    ("incomes", "source", "Primary Income", "Monthly Salary", None),
    ("expenses", "category", "Living Expenses", "Monthly Expenses", None),
    ("assets", "name", "Savings Balance", "Current Savings", ("type", "Savings")),
]


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    for table, column, legacy, canonical, extra in MIGRATIONS:
        rows = conn.execute(
            sa.text(
                f"SELECT id, user_id, updated_at FROM {table} "  # noqa: S608
                f"WHERE {column} = :legacy AND deleted_at IS NULL"
            ),
            {"legacy": legacy},
        ).fetchall()

        by_user: dict[object, list] = {}
        for row in rows:
            by_user.setdefault(row.user_id, []).append(row)

        for group in by_user.values():
            # Most recently updated wins; the rest are retired.
            group.sort(key=lambda r: (r.updated_at is not None, r.updated_at), reverse=True)
            keeper, duplicates = group[0], group[1:]

            for dupe in duplicates:
                conn.execute(
                    sa.text(f"UPDATE {table} SET deleted_at = :now WHERE id = :id"),  # noqa: S608
                    {"now": now, "id": dupe.id},
                )

            sets = f"{column} = :canonical"
            params: dict[str, object] = {"canonical": canonical, "id": keeper.id}
            if extra is not None:
                extra_column, extra_value = extra
                sets += f", {extra_column} = :extra_value"
                params["extra_value"] = extra_value

            conn.execute(
                sa.text(f"UPDATE {table} SET {sets} WHERE id = :id"),  # noqa: S608
                params,
            )


def downgrade() -> None:
    conn = op.get_bind()
    # Restores the legacy names. The duplicates stay soft-deleted: which row was
    # retired is not recoverable, and resurrecting them would re-inflate totals.
    for table, column, legacy, canonical, _extra in MIGRATIONS:
        conn.execute(
            sa.text(
                f"UPDATE {table} SET {column} = :legacy "  # noqa: S608
                f"WHERE {column} = :canonical AND deleted_at IS NULL"
            ),
            {"legacy": legacy, "canonical": canonical},
        )
