"""Read-only Dashboard visibility projection; API dependencies remain authoritative.

Mirrors require_permission's existing superadmin/no-role compatibility behavior.
This does not grant permissions or change authorization semantics.
"""
from ..models.admin_role import AdminRole

DASHBOARD_PERMISSIONS = (
    "devices:view", "devices:write", "accounting:view", "security:view", "security:audit",
    "ncm:view", "ncm:backup", "network_ops:view", "network_ops:execute",
    "policies:view", "policies:write", "config:view", "tacacs_users:view",
)


def dashboard_capabilities(admin, db):
    if admin.is_superadmin or admin.role_id is None:
        allowed = set(DASHBOARD_PERMISSIONS)
    else:
        role = db.query(AdminRole).filter(AdminRole.id == admin.role_id).first()
        allowed = set(role.permissions or []) if role else set()
    return {**{key: key in allowed for key in DASHBOARD_PERMISSIONS},
            "directory:check": bool(admin.is_superadmin)}
