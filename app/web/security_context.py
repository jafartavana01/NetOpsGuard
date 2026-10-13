"""Security workspace presentation only; existing API authorization is authoritative."""
from fastapi import HTTPException
from ..api.deps import require_permission
from ..database import get_sessionmaker
from ..services.permissions import PERMISSION_CATALOG


def security_permissions(admin):
    allowed = []
    with get_sessionmaker()() as db:
        for permission in PERMISSION_CATALOG:
            if not permission.key.startswith(('security:', 'ncm:', 'devices:')):
                continue
            try:
                require_permission(permission.key)(admin=admin, db=db)
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
            else:
                allowed.append(permission.key)
    return allowed
