"""Authoritative preflight, cleanup, bulk deletion and missing-reference repair."""
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.admin import AdminUser
from ..services import dependency_deletion as service
from .deps import require_permission, verify_csrf

router = APIRouter(prefix='/api/dependencies', tags=['dependencies'])


class Target(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['device', 'device_group', 'user', 'user_group', 'command_set', 'command_category', 'policy', 'radius_policy']
    id: str


class Preview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    targets: list[Target] = Field(min_length=1, max_length=200)


class Mutation(Preview):
    operation: Literal['delete', 'cleanup', 'cleanup_delete', 'device_delete']
    revision: str = Field(min_length=64, max_length=64)
    confirmation: Literal['DELETE']


class Replacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    condition_id: str | None = None
    field: str | None = None
    replacement_id: str


class Repair(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: str = Field(min_length=64, max_length=64)
    replacements: list[Replacement] = Field(min_length=1, max_length=200)
    confirmation: Literal['REPAIR']


def _authorize(db, admin, targets, action, cleanup=False):
    for resource in {service.PERMISSIONS[t.type] for t in targets}:
        require_permission(resource + ':' + action)(admin, db)
    require_permission('policies:view')(admin, db)
    if cleanup:
        require_permission('policies:write')(admin, db)


def _can(db, admin, permission):
    from fastapi import HTTPException
    try:
        require_permission(permission)(admin, db)
        return True
    except HTTPException:
        return False


@router.post('/inspect', dependencies=[Depends(verify_csrf)])
def inspect_dependencies(payload: Preview, db: Session = Depends(get_db), admin: AdminUser = Depends(require_permission("policies:view"))):
    _authorize(db, admin, payload.targets, 'view')
    report = service.inspect(db, [t.model_dump() for t in payload.targets])
    report['can_delete'] = all(_can(db, admin, service.PERMISSIONS[t.type]+':write') for t in payload.targets)
    report['can_cleanup'] = report['can_delete'] and _can(db, admin, 'policies:write')
    report['can_delete_policy'] = _can(db, admin, 'policies:write')
    return report


@router.post('/execute', dependencies=[Depends(verify_csrf)])
def execute_deletion(payload: Mutation, db: Session = Depends(get_db), admin: AdminUser = Depends(require_permission("policies:view"))):
    _authorize(db, admin, payload.targets, 'write', payload.operation != 'delete')
    return service.execute(db, [t.model_dump() for t in payload.targets], payload.operation, payload.revision, payload.confirmation, admin)


@router.get('/orphans')
def orphaned_references(db: Session = Depends(get_db), admin: AdminUser = Depends(require_permission("policies:view"))):
    return {'policies': service.orphans(db), 'can_repair': _can(db, admin, 'policies:write'), 'deployed_configuration_changed': False}


@router.post('/repair/{policy_id}', dependencies=[Depends(verify_csrf)])
def repair_references(policy_id: str, payload: Repair, db: Session = Depends(get_db), admin: AdminUser = Depends(require_permission("policies:write"))):
    return service.repair(db, policy_id, payload.revision, [r.model_dump() for r in payload.replacements], admin)
