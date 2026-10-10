"""Policy history snapshots and fail-closed restoration.

Legacy snapshots retain name-based lookup. Missing/unsupported scope is rejected
before mutation, never downgraded to Any. History is not rewritten. Supplemental
restoration blockers preserve unresolved live IDs and unsupported tree status in
new snapshots; they are not a complete tree-versioning implementation.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models.command_set import CommandSet
from ..models.device import NetworkDevice
from ..models.device_group import DeviceGroup
from ..models.group import TacacsGroup
from ..models.policy import Policy
from ..models.policy_condition import PolicyCondition
from ..models.policy_condition_group import PolicyConditionGroup
from ..models.policy_command_set import PolicyCommandSet
from ..models.policy_version import PolicyVersion


class PolicyRestoreError(ValueError):
    def __init__(self, diagnostics):
        super().__init__('This policy version cannot be restored faithfully.')
        self.diagnostics = diagnostics


def restore_diagnostic(code, path, reason, object_type=None, object_name=None, object_id=None):
    return dict(code=code, path=path, dimension=path, reason=reason,
                object_type=object_type, object_name=object_name,
                object_id=str(object_id) if object_id is not None else None)


def build_snapshot(db: Session, policy: Policy) -> dict:
    group = db.query(TacacsGroup).filter(TacacsGroup.id == policy.condition_group_id).first() if policy.condition_group_id else None
    device = db.query(NetworkDevice).filter(NetworkDevice.id == policy.condition_device_id).first() if policy.condition_device_id else None
    device_group = db.query(DeviceGroup).filter(DeviceGroup.id == policy.condition_device_group_id).first() if policy.condition_device_group_id else None

    joins = (
        db.query(PolicyCommandSet)
        .filter(PolicyCommandSet.policy_id == policy.id)
        .order_by(PolicyCommandSet.order.asc())
        .all()
    )
    blockers = []
    for field, kind, target in (
        ('condition_group_id', 'user_group', group),
        ('condition_device_id', 'device', device),
        ('condition_device_group_id', 'device_group', device_group),
    ):
        ref = getattr(policy, field)
        if ref is not None and target is None:
            blockers.append(restore_diagnostic('policy.restore.reference_missing', field,
                'The referenced object was missing when this version was recorded.', kind, object_id=ref))
    if db.query(PolicyConditionGroup).filter(PolicyConditionGroup.policy_id == policy.id).first():
        blockers.append(restore_diagnostic('policy.restore.tree_unsupported', 'tree',
            'This version uses a condition tree that legacy restoration cannot reproduce.'))
    command_set_names = []
    for j in joins:
        cs = db.query(CommandSet).filter(CommandSet.id == j.command_set_id).first()
        if cs:
            command_set_names.append(cs.name)
        else:
            blockers.append(restore_diagnostic('policy.restore.reference_missing', 'command_set_ids',
                'A referenced command set was missing when this version was recorded.',
                'command_set', object_id=j.command_set_id))

    external = [g for g in db.query(TacacsGroup).all() if getattr(g, 'authority', 'LEGACY') == 'EXTERNAL']
    references = {policy.condition_group_id}
    if external:
        tree_ids = {g.id for g in db.query(PolicyConditionGroup).filter(PolicyConditionGroup.policy_id == policy.id).all()}
        references.update(c.referenced_object_id for c in db.query(PolicyCondition).all()
                          if c.group_id in tree_ids and c.object_type == 'user_group')
    bindings = [{'group_id': str(g.id), 'name': g.name, 'authority': g.authority,
                 'source_id': str(g.external_source_id), 'directory_cn': g.ad_group_name}
                for g in external if g.id in references]
    return {
        **({'restoration_blockers': blockers} if blockers else {}),
        **({'external_scope_bindings': bindings} if bindings else {}),
        "name": policy.name,
        "description": policy.description,
        "enabled": policy.enabled,
        "priority": policy.priority,
        "condition_group_name": group.name if group else None,
        "condition_device_name": device.name if device else None,
        "condition_device_group_name": device_group.name if device_group else None,
        "default_priv_lvl": policy.default_priv_lvl,
        "default_action": policy.default_action,
        "command_set_names": command_set_names,
    }


def record_version(
    db: Session,
    policy: Policy,
    *,
    created_by: str | None,
    change_description: str | None = None,
) -> PolicyVersion:
    """
    Called after `policy` has an id (post-flush) and its
    PolicyCommandSet rows are already written for this save. Flushes
    but does NOT commit -- the caller's own commit() covers this row
    too, so a version and the policy state it describes are always
    persisted atomically together, never one without the other.
    """
    last = (
        db.query(PolicyVersion)
        .filter(PolicyVersion.policy_id == policy.id)
        .order_by(PolicyVersion.version_number.desc())
        .first()
    )
    next_number = (last.version_number + 1) if last else 1

    version = PolicyVersion(
        policy_id=policy.id,
        version_number=next_number,
        snapshot=json.dumps(build_snapshot(db, policy)),
        change_description=change_description,
        created_by=created_by,
    )
    db.add(version)
    db.flush()
    return version


def resolve_snapshot_for_restore(db: Session, snapshot: dict) -> tuple[dict, list[str]]:
    """Validate the whole snapshot before returning any resolved references.

    A rejection leaves the current policy and historical snapshot untouched.
    The empty warnings list is retained for successful-response compatibility.
    """
    diagnostics = []
    def invalid(path, reason, code='policy.restore.snapshot_invalid', **context):
        diagnostics.append(restore_diagnostic(code, path, reason, **context))
    if not isinstance(snapshot, dict):
        raise PolicyRestoreError([restore_diagnostic('policy.restore.snapshot_invalid', 'snapshot',
            'The stored policy snapshot is not an object.')])
    if snapshot.get('external_scope_bindings'):
        raise PolicyRestoreError([restore_diagnostic('policy.restore.external_unsupported', 'external_scope_bindings',
            'Restoring EXTERNAL policy scope remains unsupported. Edit the explicit scope instead.')])
    allowed = {'name', 'description', 'enabled', 'priority', 'condition_group_name',
               'condition_device_name', 'condition_device_group_name', 'default_priv_lvl',
               'default_action', 'command_set_names', 'external_scope_bindings', 'restoration_blockers'}
    if set(snapshot) - allowed:
        invalid('snapshot', 'This snapshot contains fields unsupported by legacy restoration.',
                'policy.restore.snapshot_unsupported')
    blockers = snapshot.get('restoration_blockers', [])
    if not isinstance(blockers, list) or any(not isinstance(d, dict) for d in blockers):
        invalid('restoration_blockers', 'Stored restoration blockers are malformed.')
    elif blockers:
        for d in blockers:
            diagnostics.append(restore_diagnostic(
                d.get('code', 'policy.restore.snapshot_invalid'), d.get('path', 'snapshot'),
                d.get('reason', 'This snapshot was recorded with unresolved scope.'),
                d.get('object_type'), d.get('object_name'), d.get('object_id')))
    # All historical snapshots written by build_snapshot contain these keys.
    # Absence is not a declaration of Any. Explicit JSON null remains supported.
    resolved = dict(condition_group_id=None, condition_device_id=None,
                    condition_device_group_id=None, command_set_ids=[])
    for field, model, kind in (
        ('condition_group', TacacsGroup, 'user_group'),
        ('condition_device', NetworkDevice, 'device'),
        ('condition_device_group', DeviceGroup, 'device_group'),
    ):
        key = field + '_name'
        if key not in snapshot:
            invalid(key, 'The stored scope dimension is missing.'); continue
        name = snapshot[key]
        if name is None:
            continue
        if not isinstance(name, str) or not name.strip():
            invalid(key, 'A reference must be a non-empty name or explicit null.'); continue
        matches = db.query(model).filter(model.name == name).all()
        if len(matches) != 1:
            invalid(key, 'The historical reference no longer resolves uniquely.',
                    'policy.restore.reference_missing' if not matches else 'policy.restore.reference_ambiguous',
                    object_type=kind, object_name=name)
        elif kind == 'user_group' and getattr(matches[0], 'authority', 'LEGACY') == 'EXTERNAL':
            invalid(key, 'Legacy restoration cannot bind an EXTERNAL group.',
                    'policy.restore.external_unsupported', object_type=kind, object_name=name)
        else:
            resolved[field + '_id'] = str(matches[0].id)
    names = snapshot.get('command_set_names')
    if not isinstance(names, list) or any(not isinstance(n, str) or not n.strip() for n in names):
        invalid('command_set_names', 'Command-set references must be a list of non-empty names.')
    else:
        for index, name in enumerate(names):
            matches = db.query(CommandSet).filter(CommandSet.name == name).all()
            if len(matches) != 1:
                invalid(f'command_set_names[{index}]', 'The historical command set no longer resolves uniquely.',
                        'policy.restore.reference_missing' if not matches else 'policy.restore.reference_ambiguous',
                        object_type='command_set', object_name=name)
            else:
                resolved['command_set_ids'].append(str(matches[0].id))
    for key, expected in (('enabled', bool), ('priority', int), ('default_priv_lvl', int)):
        if key in snapshot and type(snapshot[key]) is not expected:
            invalid(key, 'The stored policy value has an invalid type.')
    if snapshot.get('default_action', 'deny') not in ('permit', 'deny'):
        invalid('default_action', 'The stored policy action is unsupported.')
    if diagnostics:
        raise PolicyRestoreError(diagnostics)
    return resolved, []
