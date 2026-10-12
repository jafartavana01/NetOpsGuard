"""Presentation grants only; API dependencies remain the authorization boundary."""
from fastapi import HTTPException

from ..api.deps import require_permission
from ..database import get_sessionmaker
from ..services.permissions import PERMISSION_CATALOG


def operations_permissions(admin):
    keys = [p.key for p in PERMISSION_CATALOG
            if p.key.startswith(('ncm:', 'network_ops:', 'devices:'))]
    allowed = []
    with get_sessionmaker()() as db:
        for key in keys:
            try:
                require_permission(key)(admin=admin, db=db)
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
            else:
                allowed.append(key)
    return allowed
