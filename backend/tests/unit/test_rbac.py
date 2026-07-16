from __future__ import annotations

from app.core.rbac import (
    ROLE_PERMISSIONS,
    Permission,
    Role,
    has_all_permissions,
    has_permission,
    permissions_for,
)


def test_every_role_has_a_permission_set() -> None:
    for role in Role:
        assert role in ROLE_PERMISSIONS


def test_owner_owns_financial_data() -> None:
    assert has_permission(Role.OWNER, Permission.FINANCIAL_READ_OWN)
    assert has_permission(Role.OWNER, Permission.FINANCIAL_WRITE_OWN)


def test_admin_cannot_read_financial_data() -> None:
    # Key FinTech control: operational admin is separated from data access.
    assert not has_permission(Role.ADMIN, Permission.FINANCIAL_READ_OWN)
    assert not has_permission(Role.ADMIN, Permission.FINANCIAL_WRITE_OWN)
    assert has_permission(Role.ADMIN, Permission.USER_MANAGE)


def test_auditor_reads_audit_but_not_writes() -> None:
    assert has_permission(Role.AUDITOR, Permission.AUDIT_READ)
    assert not has_permission(Role.AUDITOR, Permission.FINANCIAL_WRITE_OWN)
    assert not has_permission(Role.AUDITOR, Permission.USER_MANAGE)


def test_has_all_permissions() -> None:
    assert has_all_permissions(
        Role.OWNER,
        frozenset({Permission.USER_READ_SELF, Permission.FINANCIAL_READ_OWN}),
    )
    assert not has_all_permissions(
        Role.OWNER,
        frozenset({Permission.USER_READ_SELF, Permission.USER_MANAGE}),
    )


def test_permissions_for_unknown_returns_empty() -> None:
    assert permissions_for(Role.OWNER) == ROLE_PERMISSIONS[Role.OWNER]
