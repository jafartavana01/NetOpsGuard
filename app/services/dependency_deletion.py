"""Dependency-aware desired-state deletion. Never applies/reloads AAA configuration.

All entry points re-inspect under reference_lock and own exactly one commit.
Only whole directly dependent policies are eligible for automatic cleanup.
"""
import hashlib
import json
import logging
import uuid
from fastapi import HTTPException
from pydantic import ValidationError
from ..database import Base
from ..models.device import NetworkDevice
from ..models.device_group import DeviceGroup
from ..models.user import TacacsUser
from ..models.group import TacacsGroup
from ..models.command_set import CommandSet
from ..models.command_category import CommandCategory
from ..models.command_rule import CommandRule
from ..models.policy import Policy
from ..models.radius_policy import RadiusPolicy, RadiusPolicyAttribute
from ..models.policy_command_set import PolicyCommandSet
from ..models.policy_condition import PolicyCondition
from ..models.policy_condition_group import PolicyConditionGroup
from ..models.dependency_audit import DependencyAudit
from . import config_compiler, policy_scope, policy_versioning
from .reference_lock import guard

logger = logging.getLogger('netopsguard.dependency_mutation')
MODELS = {'device': NetworkDevice, 'device_group': DeviceGroup, 'user': TacacsUser,
          'user_group': TacacsGroup, 'command_set': CommandSet, 'command_category': CommandCategory,
          'policy': Policy, 'radius_policy': RadiusPolicy}
PERMISSIONS = {'device': 'devices', 'device_group': 'devices', 'user': 'tacacs_users',
               'user_group': 'groups', 'command_set': 'policies', 'command_category': 'policies',
               'policy': 'policies', 'radius_policy': 'policies'}
LEGACY = {'device': 'condition_device_id', 'device_group': 'condition_device_group_id', 'user_group': 'condition_group_id'}
WARNING = 'Deleting this policy may change effective network authorization after configuration is applied.'


def _checkpoint(stage):
    """Failure-injection seam; no production action."""


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _row(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _id(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(400, detail={'code': 'dependency.invalid_id', 'message': 'Invalid object identifier.'}) from None


def _targets(db, targets):
    if not targets or len(targets) > 200:
        raise HTTPException(400, detail='Select between 1 and 200 objects.')
    resolved = {}
    for t in targets:
        kind = t['type']
        if kind not in MODELS:
            raise HTTPException(400, detail='Unsupported object type.')
        key = (kind, _id(t['id']))
        row = db.get(MODELS[kind], key[1])
        if row is None:
            raise HTTPException(409, detail={'code': 'dependency.object_missing', 'message': 'An object no longer exists. Refresh the inventory.'})
        resolved[key] = row
    return resolved


def policy_revision(db, policy):
    groups = db.query(PolicyConditionGroup).filter_by(policy_id=policy.id).all() if isinstance(policy, Policy) else []
    gids = {g.id for g in groups}
    leaves = [c for c in db.query(PolicyCondition).all() if c.group_id in gids]
    joins = db.query(PolicyCommandSet).filter_by(policy_id=policy.id).all() if isinstance(policy, Policy) else []
    csids = {j.command_set_id for j in joins}
    if isinstance(policy, Policy) and policy.manual_default_command_set_id:
        csids.add(policy.manual_default_command_set_id)
    rules = [r for r in db.query(CommandRule).all() if r.command_set_id in csids]
    sets = [s for s in db.query(CommandSet).all() if s.id in csids]
    attributes = db.query(RadiusPolicyAttribute).filter_by(policy_id=policy.id).all() if isinstance(policy, RadiusPolicy) else []
    return _hash([_row(policy), sorted([_row(x) for x in groups + leaves + joins + rules + sets + attributes], key=lambda x: str(x['id']))])


def inspect(db, targets):
    resolved = _targets(db, targets)
    from ..models.audit_run import AuditRun, AuditFinding
    audit_status = dict(db.query(AuditRun.id, AuditRun.status).all())
    from ..models.ncm import NcmBackupJob, NcmBackupJobTarget, NcmDeployment
    from ..models.command_job import CommandJob, CommandJobTarget
    backup_status = dict(db.query(NcmBackupJob.id, NcmBackupJob.status).all())
    command_status = {i: value.lower() for i, value in db.query(CommandJob.id, CommandJob.status).all()}
    terminal = {'completed', 'partial', 'failed', 'blocked', 'cancelled', 'success', 'succeeded', 'rolled_back', 'rollback_failed'}
    dependencies = []
    policy_rows = [('tacacs', p) for p in db.query(Policy).all()] + [('radius', p) for p in db.query(RadiusPolicy).all()]
    groups = {g.id: g for g in db.query(PolicyConditionGroup).all()}
    conditions = db.query(PolicyCondition).all()
    joins = db.query(PolicyCommandSet).all()
    policies = {}

    def add(kind, oid, target, ref_type, ref_id, name, location, blocking=True, cleanup=False, enabled=None, protocol=None, dtype='direct'):
        dependencies.append(dict(object_type=kind, object_id=str(oid), object_name=getattr(target, 'name', getattr(target, 'username', kind)),
            dependency_type=dtype, referencing_type=ref_type, referencing_id=str(ref_id), referencing_name=name,
            reference_location=location, blocks_deletion=blocking, automated_cleanup=cleanup, enabled=enabled, protocol=protocol))

    for (kind, oid), target in resolved.items():
        for protocol, p in policy_rows:
            locations = []
            if kind in LEGACY and getattr(p, LEGACY[kind]) == oid:
                locations.append('legacy.' + LEGACY[kind])
            if protocol == 'tacacs':
                locations.extend(f'tree.groups[{c.group_id}].conditions[{c.id}]' for c in conditions
                    if c.object_type == kind and c.referenced_object_id == oid and c.group_id in groups and groups[c.group_id].policy_id == p.id)
                if kind == 'command_set':
                    locations.extend(f'command_sets[{j.id}]' for j in joins if j.policy_id == p.id and j.command_set_id == oid)
                    if p.manual_default_command_set_id == oid:
                        locations.append('manual_default_command_set_id')
            for location in locations:
                add(kind, oid, target, 'policy', p.id, p.name, location, enabled=p.enabled, cleanup=True, protocol=protocol)
                policies[(protocol, str(p.id))] = dict(id=str(p.id), name=p.name, enabled=p.enabled, protocol=protocol, revision=policy_revision(db, p))

        # Discover actual inbound FKs instead of assuming only policy references.
        for mapper in sorted(Base.registry.mappers, key=lambda m: m.local_table.name):
            model = mapper.class_
            if model in (Policy, RadiusPolicy, PolicyCommandSet):
                continue
            for column in mapper.local_table.columns:
                if not any(fk.column.table.name == target.__tablename__ for fk in column.foreign_keys):
                    continue
                for row in db.query(model).filter(getattr(model, column.name) == oid).all():
                    # Policy internals are removed whole; historical versions survive SET NULL.
                    if kind in ('policy', 'radius_policy') and mapper.local_table.name in ('policy_condition_groups', 'policy_versions', 'radius_policy_attributes'):
                        continue
                    if kind == 'command_set' and model == CommandRule:
                        continue  # owned rules, displayed by the command-set detail/confirmation
                    # Audit evidence is history, not authorization scope. Keep
                    # its rows and name snapshots after inventory deletion.
                    history = kind == 'device' and column.name == 'device_id' and (
                        (model == AuditFinding and audit_status.get(row.audit_run_id) in ('completed', 'failed')) or
                        (model == AuditRun and row.status in ('completed', 'failed')) or
                        (model == NcmBackupJobTarget and backup_status.get(row.job_id) in terminal) or
                        (model == NcmDeployment and row.status in terminal) or
                        (model == CommandJobTarget and command_status.get(row.job_id) in terminal))
                    informational = history or (model == NetworkDevice and kind == 'device_group') or (model == TacacsUser and kind == 'user_group') or (model == CommandRule and kind == 'command_category')
                    add(kind, oid, target, mapper.local_table.name, row.id,
                        getattr(row, 'name', getattr(row, 'username', getattr(row, 'device_name', mapper.local_table.name))),
                        column.name, blocking=not informational, dtype='membership' if model in (NetworkDevice, TacacsUser) else 'association')

        # NCM schedules persist comma-separated UUIDs, not FKs.
        from ..models.ncm import NcmBackupSchedule
        field = {'device': 'device_ids', 'device_group': 'device_group_ids'}.get(kind)
        if field:
            for schedule in db.query(NcmBackupSchedule).all():
                if str(oid) in [x.strip() for x in (getattr(schedule, field) or '').split(',')]:
                    add(kind, oid, target, 'ncm_schedule', schedule.id, schedule.name, field, blocking=kind != 'device', dtype='configuration')

    # Evaluate membership consequences collectively (bulk may remove the final two members).
    inventory = config_compiler._scope_inventory(db)
    after = policy_scope.ScopeInventory(**vars(inventory))
    removed_devices = {oid for (kind, oid) in resolved if kind == 'device'}
    removed_users = {oid for (kind, oid) in resolved if kind == 'user'}
    after.devices = [x for x in inventory.devices if x.id not in removed_devices]
    after.users = [x for x in inventory.users if x.id not in removed_users]
    for protocol, p in policy_rows:
        if not p.enabled:
            continue
        before_errors = {(d.code, d.path) for d in policy_scope.resolve_scope(p, protocol, inventory).diagnostics}
        for d in policy_scope.resolve_scope(p, protocol, after).diagnostics:
            if d.code not in ('scope.empty_group', 'scope.identity_membership_unknown') or (d.code, d.path) in before_errors:
                continue
            for (kind, oid), target in resolved.items():
                membership = target.device_group_id if kind == 'device' else target.group_id if kind == 'user' else None
                if membership is not None and str(membership) == d.object_id:
                    add(kind, oid, target, 'policy', p.id, p.name, d.path, enabled=p.enabled, protocol=protocol, dtype='empty_group')

    dependencies.sort(key=lambda d: (d['object_type'], d['object_id'], d['referencing_id'], d['reference_location']))
    object_list = [dict(type=k, id=str(i), name=getattr(r, 'name', getattr(r, 'username', k)), enabled=getattr(r, 'enabled', None)) for (k, i), r in resolved.items()]
    blocked_ids = {(d['object_type'], d['object_id']) for d in dependencies if d['blocks_deletion']}
    report = dict(objects=object_list, dependencies=dependencies, policies=sorted(policies.values(), key=lambda p: (p['protocol'], p['id'])),
        total_selected=len(resolved), safe_to_delete=len(resolved)-len(blocked_ids), blocked=len(blocked_ids),
        warning=WARNING, deployed_configuration_changed=False)
    if all(kind == 'device' for kind, _ in resolved):
        affected = {(d['protocol'], d['referencing_id']) for d in dependencies if d['referencing_type'] == 'policy'}
        report['device_policies'] = [dict(id=str(p.id), name=p.name, enabled=p.enabled, protocol=protocol,
                                          revision=policy_revision(db, p)) for protocol, p in policy_rows
                                     if (protocol, str(p.id)) in affected]
        report['device_policies'].sort(key=lambda p: (p['protocol'], p['id']))
    owned_state = []
    for (kind, oid), obj in resolved.items():
        if kind in ('policy', 'radius_policy'):
            owned_state.append(policy_revision(db, obj))
        elif kind == 'command_set':
            owned_state.append(_hash(sorted([_row(r) for r in db.query(CommandRule).filter_by(command_set_id=oid).all()], key=lambda r: str(r['id']))))
    report['revision'] = _hash([report, sorted([_row(x) for x in resolved.values()], key=lambda r: str(r['id'])), sorted(owned_state)])
    return report


def _candidate(db):
    try:
        config_compiler.compile_candidate(db)
        return {'applicable': True, 'diagnostics': []}
    except config_compiler.UncompilablePolicyError as exc:
        return {'applicable': False, 'diagnostics': exc.diagnostics, 'message': str(exc)}


def _validate_change(db, before):
    _checkpoint('validation')
    after = _candidate(db)
    prior = {_hash(d) for d in before['diagnostics']}
    if not after['applicable'] and (not after['diagnostics'] or any(_hash(d) not in prior for d in after['diagnostics'])):
        raise HTTPException(409, detail={'code': 'dependency.invalid_candidate', 'message': 'Deletion would introduce invalid configuration. No changes were saved.', 'diagnostics': after['diagnostics']})
    return after


def _audit(db, actor, operation, result):
    _checkpoint('audit')
    db.add(DependencyAudit(actor=actor.username, operation=operation, details=json.dumps(result, default=str)))
    db.flush()


def _delete_policy(db, protocol, pid, actor):
    p = db.get(Policy if protocol == 'tacacs' else RadiusPolicy, _id(pid))
    if p is None:
        raise HTTPException(409, detail='Policy no longer exists; refresh.')
    if protocol == 'tacacs':
        policy_versioning.record_version(db, p, created_by=actor.username, change_description='Explicit dependency cleanup: policy deleted')
    db.delete(p)
    db.flush()
    _checkpoint('policy_delete')


def execute(db, targets, operation, revision, confirmation, actor):
    from contextlib import nullcontext
    from . import ncm_lock
    try:
        # Collection holds this cross-process lock across SSH and commits.
        # Do not detach inventory while a backup writer still owns the device.
        lock = ncm_lock.hold(db, 'backup-writer') if any(t['type'] == 'device' for t in targets) else nullcontext()
        with lock:
            return _execute(db, targets, operation, revision, confirmation, actor)
    except ncm_lock.Busy:
        raise HTTPException(409, detail='A configuration backup is active. Wait for it to finish, then retry deletion.') from None


def _execute(db, targets, operation, revision, confirmation, actor):
    if operation not in ('delete', 'cleanup', 'cleanup_delete', 'device_delete') or confirmation != 'DELETE':
        raise HTTPException(400, detail='Explicit DELETE confirmation and a supported operation are required.')
    logger.warning('dependency request actor=%s operation=%s targets=%s', actor.username, operation, json.dumps(targets))
    try:
        guard(db)
        report = inspect(db, targets)
        if any(t['type'] == 'device' for t in targets):
            from sqlalchemy import inspect as inspect_schema
            from ..ncm_history_migration import TABLES
            connection = db.connection()
            schema = inspect_schema(connection)
            schema_name = connection.get_execution_options().get('schema_translate_map', {}).get(None)
            if any(fk['referred_table'] == 'network_devices' and fk['constrained_columns'] == ['device_id']
                   for name in TABLES for fk in schema.get_foreign_keys(name, schema=schema_name)):
                raise HTTPException(409, detail='NCM history protection upgrade is required. Restart the upgraded application before deleting devices.')
        if revision is not None and revision != report['revision']:
            raise HTTPException(409, detail={'code': 'dependency.stale', 'message': 'Dependencies or objects changed. Review the refreshed preview.', 'report': report})
        if operation == 'delete' and report['blocked']:
            raise HTTPException(409, detail={'code': 'dependency.blocked', 'message': 'Resolve dependencies before deleting.', 'report': report})
        if operation == 'cleanup_delete' and any(d['blocks_deletion'] and not d['automated_cleanup'] for d in report['dependencies']):
            raise HTTPException(409, detail={'code': 'dependency.unsupported_cleanup', 'message': 'Non-policy dependencies require explicit resolution.', 'report': report})
        if operation == 'device_delete':
            if not all(t['type'] == 'device' for t in targets):
                raise HTTPException(400, detail='Device deletion accepts only device targets.')
            if any(d['blocks_deletion'] and d['referencing_type'] != 'policy' for d in report['dependencies']):
                raise HTTPException(409, detail={'code': 'dependency.blocked', 'message': 'An active job or other configuration still requires this device.', 'report': report})
        before = _candidate(db)
        removed_policies = []
        if operation in ('cleanup', 'cleanup_delete', 'device_delete'):
            for p in (report['device_policies'] if operation == 'device_delete' else report['policies']):
                _delete_policy(db, p['protocol'], p['id'], actor)
                removed_policies.append(p)
        deleted_objects = []
        if operation in ('delete', 'cleanup_delete', 'device_delete'):
            # Fresh reinspection after the complete policy cleanup.
            current = inspect(db, targets)
            if current['blocked']:
                raise HTTPException(409, detail={'code': 'dependency.blocked', 'message': 'Blocking dependencies remain.', 'report': current})
            for (kind, oid), obj in _targets(db, targets).items():
                if kind in ('policy', 'radius_policy'):
                    _delete_policy(db, 'tacacs' if kind == 'policy' else 'radius', oid, actor)
                else:
                    if kind == 'device':
                        # Explicitly preserve history even on SQLite connections
                        # where FK actions are not enabled. Never detach policy scope.
                        from ..models.audit_run import AuditRun, AuditFinding
                        from ..models.ncm import NcmBackupJobTarget, NcmDeployment
                        from ..models.command_job import CommandJobTarget
                        for history_model in (AuditFinding, AuditRun, NcmBackupJobTarget, NcmDeployment, CommandJobTarget):
                            db.query(history_model).filter(history_model.device_id == oid).update(
                                {'device_id': None}, synchronize_session='fetch')
                    db.delete(obj)
                    db.flush()
                _checkpoint('object_delete')
                deleted_objects.append({'type': kind, 'id': str(oid)})
        candidate = _validate_change(db, before)
        result = dict(operation=operation, deleted_objects=deleted_objects, deleted_policies=removed_policies,
            candidate=candidate, deployed_configuration_changed=False, warning=WARNING)
        _audit(db, actor, operation, result)
        _checkpoint('commit')
        db.commit()
        logger.info('dependency committed actor=%s operation=%s', actor.username, operation)
        return result
    except BaseException as exc:
        db.rollback()
        code = exc.detail.get('code') if isinstance(exc, HTTPException) and isinstance(exc.detail, dict) else type(exc).__name__
        logger.warning('dependency rollback actor=%s operation=%s reason=%s', actor.username, operation, code)
        raise


def delete_direct(db, kind, object_id, actor):
    """Existing DELETE endpoints retain their shape but cannot bypass inspection."""
    from ..api.deps import require_permission
    # Structured blockers contain policy names/locations, so even a direct
    # legacy DELETE needs the same visibility as the dependency dialog.
    require_permission('policies:view')(actor, db)
    return execute(db, [{'type': kind, 'id': object_id}], 'delete', None, 'DELETE', actor)


def orphans(db):
    result = []
    groups = {g.id: g for g in db.query(PolicyConditionGroup).all()}
    leaves = db.query(PolicyCondition).all()
    for protocol, model in [('tacacs', Policy), ('radius', RadiusPolicy)]:
        for p in db.query(model).all():
            missing = []
            for kind, field in LEGACY.items():
                ref = getattr(p, field)
                if ref is not None and db.get(MODELS[kind], ref) is None:
                    missing.append(dict(field=field, condition_id=None, object_type=kind, object_id=str(ref), path='legacy.'+field))
            if protocol == 'tacacs':
                for c in leaves:
                    if c.group_id in groups and groups[c.group_id].policy_id == p.id and c.object_type in ('user', 'user_group', 'device', 'device_group'):
                        if c.referenced_object_id is None or db.get(MODELS[c.object_type], c.referenced_object_id) is None:
                            missing.append(dict(field=None, condition_id=str(c.id), object_type=c.object_type, object_id=str(c.referenced_object_id) if c.referenced_object_id else None, path=f'tree.groups[{c.group_id}].conditions[{c.id}]'))
            if missing:
                result.append(dict(id=str(p.id), name=p.name, protocol=protocol, enabled=p.enabled, missing=missing, revision=policy_revision(db, p)))
    return result


def repair(db, policy_id, revision, replacements, actor):
    """Replace missing IDs only; all operators/Boolean structure remain unchanged.

    Reuses the authoritative full-state atomic TACACS+ mutation. RADIUS repairs
    validate equivalent persisted fields and the complete candidate transaction.
    """
    logger.warning('dependency repair requested actor=%s policy=%s', actor.username, policy_id)
    try:
        guard(db)
        matches = [x for x in orphans(db) if x['id'] == policy_id]
        if len(matches) != 1 or matches[0]['revision'] != revision:
            raise HTTPException(409, detail='Policy or missing references changed. Refresh repair details.')
        info = matches[0]
        p = db.get(Policy if info['protocol'] == 'tacacs' else RadiusPolicy, _id(policy_id))
        allowed = {(m['condition_id'], m['field']): m for m in info['missing']}
        if not replacements:
            raise HTTPException(400, detail='Select replacements for the missing references.')
        changes = {}
        for item in replacements:
            key = (item.get('condition_id'), item.get('field'))
            if key not in allowed or key in changes:
                raise HTTPException(400, detail='Only currently missing references can be repaired once.')
            replacement = db.get(MODELS[allowed[key]['object_type']], _id(item['replacement_id']))
            if replacement is None:
                raise HTTPException(409, detail='The replacement object no longer exists.')
            changes[key] = replacement
        if set(changes) != set(allowed):
            raise HTTPException(400, detail='Replace every missing reference in this policy together.')
        before = _candidate(db)
        if info['protocol'] == 'tacacs':
            from ..api.routes_policies import policy_to_out, _mutate_policy
            from ..api.routes_policy_conditions import _group_to_dict
            from ..schemas.policy import PolicyUpdate
            dto = policy_to_out(db, p)
            data = {f: getattr(dto, f) for f in ('name', 'description', 'enabled', 'priority', 'default_priv_lvl', 'default_action', 'requires_manual_approval', 'manual_default_command_set_id', 'condition_device_id', 'condition_group_id', 'condition_device_group_id')}
            # Keep unresolved associations too: atomic mutation must reject
            # them, not silently omit a missing command set during repair.
            data['command_set_ids'] = [str(j.command_set_id) for j in db.query(PolicyCommandSet).filter_by(policy_id=p.id).order_by(PolicyCommandSet.order).all()]
            roots = db.query(PolicyConditionGroup).filter_by(policy_id=p.id, parent_group_id=None).all()
            has_groups = db.query(PolicyConditionGroup).filter_by(policy_id=p.id).count()
            if has_groups:
                if len(roots) != 1:
                    raise HTTPException(409, detail='Malformed tree requires full policy editing; no restrictions were removed.')
                # Verify graph before using existing recursive serializer.
                nodes = db.query(PolicyConditionGroup).filter_by(policy_id=p.id).all()
                node_ids = {g.id for g in nodes}
                if any(g.parent_group_id in node_ids and g.policy_id != p.id for g in db.query(PolicyConditionGroup).all()):
                    raise HTTPException(409, detail='Foreign tree children require explicit policy review.')
                reachable = {roots[0].id}
                for _ in range(40):
                    reachable.update(g.id for g in nodes if g.parent_group_id in reachable)
                if len(reachable) != len(nodes):
                    raise HTTPException(409, detail='Disconnected tree requires full policy editing.')
                tree = _group_to_dict(db, roots[0])
                def replace(node, depth=0):
                    if depth > 40:
                        raise HTTPException(409, detail='Tree exceeds supported repair depth.')
                    for c in node['conditions']:
                        key = (c.pop('id'), None)
                        c.pop('value_type', None)
                        if key in changes:
                            c['referenced_object_id'] = str(changes[key].id)
                        # Cached text is recomputed by the authoritative builder.
                    node.pop('id', None)
                    for child in node['child_groups']:
                        replace(child, depth+1)
                replace(tree)
                data.update(scope_mode='tree', condition_tree=tree)
                # Latent legacy fields must not be silently dropped by repair.
                if any(data[f] is not None for f in LEGACY.values()):
                    raise HTTPException(409, detail='Tree plus legacy fields requires explicit full policy editing.')
            else:
                data['scope_mode'] = 'legacy'
                for (_, field), row in changes.items():
                    data[field] = str(row.id)
            data['change_description'] = 'Explicit missing-reference repair'
            _mutate_policy(db, PolicyUpdate(**data), actor, policy_id=policy_id, commit=False)
        else:
            for (_, field), row in changes.items():
                setattr(p, field, row.id)
            db.flush()
        candidate = _validate_change(db, before)
        result = dict(policy_id=policy_id, candidate=candidate, deployed_configuration_changed=False)
        _audit(db, actor, 'repair', result)
        _checkpoint('commit')
        db.commit()
        return result
    except ValidationError:
        db.rollback()
        logger.warning('dependency repair rollback actor=%s policy=%s reason=invalid_policy_structure', actor.username, policy_id)
        raise HTTPException(409, detail='The policy contains invalid structure that cannot be repaired by replacing IDs alone. Use the full policy editor; no changes were saved.') from None
    except BaseException as exc:
        db.rollback()
        logger.warning('dependency repair rollback actor=%s policy=%s exception=%s', actor.username, policy_id, type(exc).__name__)
        raise
