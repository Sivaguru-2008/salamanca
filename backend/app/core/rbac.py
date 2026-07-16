"""Role-based access control: roles, permissions, and the role→permission map.

``admin`` deliberately has no ``financial:*`` permissions — operational
administration is separated from financial-data access (see 06-api-security §4).
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"
    ADVISOR = "advisor"
    AUDITOR = "auditor"
    ADMIN = "admin"
    SYSTEM = "system"


class Permission(StrEnum):
    USER_READ_SELF = "user:read:self"
    USER_WRITE_SELF = "user:write:self"
    USER_MANAGE = "user:manage"
    FINANCIAL_READ_OWN = "financial:read:own"
    FINANCIAL_WRITE_OWN = "financial:write:own"
    DECISION_READ = "decision:read"
    AUDIT_READ = "audit:read"
    COMPLIANCE_READ = "compliance:read"
    SYSTEM_CONFIG = "system:config"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(
        {
            Permission.USER_READ_SELF,
            Permission.USER_WRITE_SELF,
            Permission.FINANCIAL_READ_OWN,
            Permission.FINANCIAL_WRITE_OWN,
            Permission.DECISION_READ,
        }
    ),
    Role.ADVISOR: frozenset(
        {
            Permission.USER_READ_SELF,
            Permission.DECISION_READ,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.USER_READ_SELF,
            Permission.AUDIT_READ,
            Permission.COMPLIANCE_READ,
            Permission.DECISION_READ,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.USER_READ_SELF,
            Permission.USER_WRITE_SELF,
            Permission.USER_MANAGE,
            Permission.SYSTEM_CONFIG,
        }
    ),
    Role.SYSTEM: frozenset(
        {
            Permission.USER_MANAGE,
            Permission.AUDIT_READ,
            Permission.COMPLIANCE_READ,
            Permission.SYSTEM_CONFIG,
        }
    ),
}


def permissions_for(role: Role) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in permissions_for(role)


def has_all_permissions(role: Role, permissions: frozenset[Permission]) -> bool:
    return permissions <= permissions_for(role)
