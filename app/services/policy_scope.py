"""Read-only deployment scope validation shared by TACACS+ and RADIUS.

NULL legacy dimensions retain their existing Any meaning. Historical NULL loss
cannot be recovered here. No database writes, external directory queries, or
native daemon expressions are performed by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import ipaddress
import re
import uuid


class ScopeState(str, Enum):
    UNRESTRICTED = 'UNRESTRICTED'
    RESTRICTED = 'RESTRICTED'
    EMPTY = 'EMPTY'
    INVALID = 'INVALID'


@dataclass(frozen=True)
class ScopeDiagnostic:
    policy_id: str
    policy_name: str
    protocol: str
    dimension: str
    object_type: str | None
    object_id: str | None
    code: str
    path: str
    reason: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Predicate:
    kind: str
    operator: str = 'equal'
    value: str = ''
    object_id: str = ''
    children: tuple[Predicate, ...] = ()


@dataclass(frozen=True)
class ScopeReference:
    dimension: str
    object_type: str
    object_id: str | None
    path: str


@dataclass(frozen=True)
class ScopeResolution:
    state: ScopeState
    predicate: Predicate | None = None
    diagnostics: tuple[ScopeDiagnostic, ...] = ()
    policy_id: str = ''
    policy_name: str = ''
    protocol: str = ''
    references: tuple[ScopeReference, ...] = ()

    @property
    def deployable(self):
        return self.state in (ScopeState.UNRESTRICTED, ScopeState.RESTRICTED)


@dataclass
class ScopeInventory:
    devices: list = field(default_factory=list)
    device_groups: list = field(default_factory=list)
    identity_groups: list = field(default_factory=list)
    users: list = field(default_factory=list)
    tree_groups: list = field(default_factory=list)
    conditions: list = field(default_factory=list)
    external_identity_enabled: bool = False
    external_sources: list = field(default_factory=list)


def external_source_name(source_id):
    """Stable, safe module token independent of user-controlled names."""
    return 'netopsguard_ad_' + uuid.UUID(str(source_id)).hex


def external_binding_diagnostics(group, inventory):
    """Structural validation only. Directory health is not membership authority."""
    errors = []
    def error(code, reason):
        errors.append({'code': code, 'reason': reason})
    authority = getattr(group, 'authority', 'LEGACY')
    if authority not in ('LEGACY', 'EXTERNAL'):
        error('scope.invalid_authority', 'Unsupported identity-group authority.')
        return errors
    if authority != 'EXTERNAL':
        if getattr(group, 'external_source_id', None) is not None:
            error('scope.invalid_binding', 'Unclassified groups cannot carry an external source binding.')
        return errors
    sid = getattr(group, 'external_source_id', None)
    sources = [x for x in inventory.external_sources if x.id == sid]
    if sid is None or len(sources) != 1:
        error('scope.external_source_missing', 'The explicitly bound directory source does not resolve.')
        return errors
    source = sources[0]
    if len(inventory.external_sources) != 1:
        error('scope.external_source_ambiguous', 'Only one configured AD/MAVIS source is supported in this increment.')
    if not source.enabled or not source.host:
        error('scope.external_backend_disabled', 'The bound AD/MAVIS backend is disabled or has no host.')
    if not getattr(source, 'use_memberof', False):
        error('scope.external_membership_disabled', 'The bound backend must report memberOf membership.')
    if getattr(source, 'use_starttls', False):
        error('scope.external_backend_unsupported', 'StartTLS is not represented by the generated MAVIS backend; use configured LDAPS.')
    if not re.fullmatch(r'[A-Za-z0-9.:_-]+', getattr(source, 'host', '') or '') or not 1 <= (getattr(source, 'port', 0) or 0) <= 65535:
        error('scope.external_backend_invalid', 'The backend host or port is not safely representable.')
    if not getattr(source, 'search_base', '') or not getattr(source, 'bind_dn', '') or not getattr(source, 'bind_password_encrypted', None):
        error('scope.external_backend_incomplete', 'A search base and service-account credentials are required for the supported AD backend.')
    template = getattr(source, 'user_filter_template', '') or ''
    if template.count('%s') != 1 or '%' in template.replace('%s', ''):
        error('scope.external_backend_invalid', 'The LDAP user filter must contain exactly one supported %s username placeholder.')
    prefix = getattr(source, 'group_prefix', None) or ''
    if not re.fullmatch(r'[A-Za-z0-9 _-]*', prefix):
        error('scope.external_prefix_unsafe', 'Group prefix must be literal ASCII letters, digits, spaces, underscores or hyphens; regex metacharacters are unsupported.')
    cn = getattr(group, 'ad_group_name', None) or ''
    if not re.fullmatch(r'[A-Za-z0-9 _-]+', cn):
        error('scope.external_cn_unsafe', 'Directory CN contains unsupported or ambiguous DN/parser characters.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', group.name):
        error('scope.external_runtime_unsafe', 'Runtime group must be a supported NetOpsGuard group identifier.')
    if not cn.lower().startswith(prefix.lower()) or cn[len(prefix):] != group.name:
        error('scope.external_mapping_mismatch', 'Directory CN after case-insensitive prefix removal must exactly equal the runtime group name; residual case and spaces are preserved. No alias is applied.')
    for other in inventory.identity_groups:
        if other.id != group.id and getattr(other, 'authority', 'LEGACY') == 'EXTERNAL' and getattr(other, 'external_source_id', None) == sid:
            if (getattr(other, 'ad_group_name', '') or '').casefold() == cn.casefold():
                error('scope.external_mapping_ambiguous', 'Another group binds the same case-insensitive directory CN in this source.')
                break
    local_names = {u.username.casefold() for u in inventory.users if u.enabled and getattr(u, 'auth_source', 'local') == 'local'}
    for user in inventory.users:
        if user.enabled and getattr(user, 'auth_source', 'local') == 'ad':
            # Only explicit bare identities can be compared safely. Do not guess UPN/domain stripping.
            identity = (getattr(user, 'ad_identity', None) or user.username).casefold()
            if identity in local_names:
                error('scope.external_username_collision', 'An explicit AD identity collides with an enabled locally authenticated username. Resolve the collision before applying.')
                break
    return errors


def resolve_scope(policy, protocol: str, inventory: ScopeInventory) -> ScopeResolution:
    """Resolve every restrictive dimension; any failed dimension invalidates all.

    Empty groups are a distinct result but non-deployable in Phase 2A. A group
    with no locally known enabled members and an enabled directory backend has
    UNKNOWN membership for LEGACY groups, not proven emptiness. Explicitly
    bound EXTERNAL groups instead require a valid source plus positive runtime
    membership; local enumeration is not authoritative. No LDAP calls are made.
    """
    diagnostics = []
    references = []
    devices = {r.id: r for r in inventory.devices}
    device_groups = {r.id: r for r in inventory.device_groups}
    identity_groups = {r.id: r for r in inventory.identity_groups}
    users = {r.id: r for r in inventory.users}

    def issue(code, path, kind=None, ref=None, reason='', dimension=None):
        diagnostics.append(ScopeDiagnostic(str(policy.id), policy.name, protocol,
            dimension or (path.split('.')[-1] if path.startswith('legacy.') else kind) or 'tree',
            kind, str(ref) if ref is not None else None,
            code, path, reason))

    def reference(kind, ref, op, path):
        references.append(ScopeReference(path.split('.')[-1] if path.startswith('legacy.') else kind,
                                         kind, str(ref) if ref is not None else None, path))
        table = {'device': devices, 'device_group': device_groups,
                 'user_group': identity_groups, 'user': users}[kind]
        if ref is None or ref not in table:
            issue('scope.reference_missing', path, kind, ref,
                  'The restrictive reference is missing or no longer resolves. Reassign it before applying.')
            return None
        if kind == 'user':
            issue('scope.unsupported_condition', path, kind, ref,
                  'Direct per-user conditions are not supported by the configuration compiler.')
            return None
        if kind == 'device_group':
            members = sorted((d.name for d in inventory.devices if d.device_group_id == ref))
            if not members:
                issue('scope.empty_group', path, kind, ref,
                      'The referenced device group is empty. Add members or explicitly revise the policy.')
                return None
            return Predicate('AND' if op == 'not_equal' else 'OR', children=tuple(
                Predicate('device', op, name) for name in members))
        if kind == 'user_group':
            group = table[ref]
            binding_errors = external_binding_diagnostics(group, inventory)
            for error in binding_errors:
                issue(error['code'], path, kind, ref, error['reason'])
            if binding_errors:
                return None
            if getattr(group, 'authority', 'LEGACY') == 'EXTERNAL':
                if protocol != 'tacacs':
                    issue('scope.external_protocol_unsupported', path, kind, ref, 'EXTERNAL authority is not certified for RADIUS.')
                    return None
                if op != 'equal':
                    issue('scope.external_negation_unsupported', path, kind, ref, 'Negative EXTERNAL membership is unsupported; missing membership is not proven nonmembership.')
                    return None
                return Predicate('AND', children=(
                    Predicate('identity_source', value=external_source_name(group.external_source_id)),
                    Predicate('user_group', value=group.name, object_id=str(ref)),
                    # Both protocols share a ruleset. An EXTERNAL TACACS+
                    # condition must not become a RADIUS selector indirectly.
                    Predicate('aaa_protocol', value='tacacs')))
            members = [u for u in inventory.users if u.group_id == ref and u.enabled]
            if not members:
                unknown = inventory.external_identity_enabled or bool(getattr(table[ref], 'ad_group_name', None))
                issue('scope.identity_membership_unknown' if unknown else 'scope.empty_group',
                      path, kind, ref,
                      'External identity-group membership cannot be established from local inventory.' if unknown else
                      'The referenced identity group has no enabled members. Add members or explicitly revise the policy.')
                return None
        return Predicate(kind, op, table[ref].name, str(ref))

    policy_groups = [g for g in inventory.tree_groups if g.policy_id == policy.id] if protocol == 'tacacs' else []
    predicate = None
    if policy_groups:
        group_ids = {g.id for g in policy_groups}
        roots = [g for g in policy_groups if g.parent_group_id is None]
        if len(roots) != 1:
            issue('scope.invalid_root', 'tree', reason='A condition tree must have exactly one root.')
        for group in policy_groups:
            if group.parent_group_id is not None and group.parent_group_id not in group_ids:
                issue('scope.orphan_group', f'tree.groups[{group.id}]', reason='A condition group has a missing or foreign parent.')
        # A foreign policy's child must not be silently pulled into this tree.
        for group in inventory.tree_groups:
            if group.parent_group_id in group_ids and group.id not in group_ids:
                issue('scope.foreign_child', f'tree.groups[{group.id}]', reason='A child group belongs to another policy.')
        visited = set()
        visiting = set()

        def walk(group, depth=0):
            path = f'tree.groups[{group.id}]'
            if group.id in visiting or depth > 128:
                issue('scope.invalid_tree', path, reason='The condition tree is cyclic or exceeds the supported depth.')
                return None
            visiting.add(group.id)
            visited.add(group.id)
            if group.logical_operator not in ('AND', 'OR'):
                issue('scope.unsupported_operator', path, reason='Only AND and OR groups are currently deployable.')
            children = []
            conditions = sorted((c for c in inventory.conditions if c.group_id == group.id), key=lambda c: c.order)
            groups = sorted((g for g in policy_groups if g.parent_group_id == group.id), key=lambda g: g.order)
            if not conditions and not groups:
                issue('scope.empty_tree_group', path, reason='An empty condition-tree node is incomplete, not unrestricted.')
            for c in conditions:
                cp = f'{path}.conditions[{c.id}]'
                kind, op = c.object_type, c.operator
                if kind in ('device', 'device_group', 'user_group', 'user'):
                    if op not in ('equal', 'not_equal'):
                        issue('scope.unsupported_operator', cp, kind, c.referenced_object_id, 'Unsupported reference operator.')
                        continue
                    node = reference(kind, c.referenced_object_id, op, cp)
                elif kind == 'source_ip':
                    if op not in ('equal', 'not_equal', 'is_in_cidr', 'is_not_in_cidr'):
                        issue('scope.unsupported_operator', cp, kind, reason='Unsupported source-address operator.')
                        continue
                    try:
                        if op in ('is_in_cidr', 'is_not_in_cidr'):
                            ipaddress.ip_network(c.value, strict=False)
                        else:
                            ipaddress.ip_address(c.value)
                    except (ValueError, TypeError):
                        issue('scope.malformed_address', cp, kind, reason='Source address/CIDR is malformed.')
                        continue
                    node = Predicate(kind, op, c.value, str(c.id))
                else:
                    issue('scope.unsupported_condition', cp, kind, getattr(c, 'referenced_object_id', None), 'Unsupported condition type.')
                    continue
                if node is not None:
                    children.append(node)
            for child in groups:
                node = walk(child, depth + 1)
                if node is not None:
                    children.append(node)
            visiting.remove(group.id)
            return Predicate(group.logical_operator, children=tuple(children))

        if len(roots) == 1:
            predicate = walk(roots[0])
        if visited != group_ids:
            issue('scope.unreachable_tree', 'tree', reason='Some condition groups are disconnected from the root.')
    else:
        clauses = []
        for dimension, kind in (('condition_group_id', 'user_group'),
                                ('condition_device_id', 'device'),
                                ('condition_device_group_id', 'device_group')):
            ref = getattr(policy, dimension)
            if ref is not None:
                node = reference(kind, ref, 'equal', 'legacy.' + dimension)
                if node is not None:
                    clauses.append(node)
        if clauses:
            predicate = Predicate('AND', children=tuple(clauses))
    if protocol == 'radius' and policy.condition_service_type:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', policy.condition_service_type):
            issue('scope.malformed_service_type', 'radius.condition_service_type',
                  reason='Service-Type must be a single numeric or named value.', dimension='service_type')
    if diagnostics:
        state = ScopeState.EMPTY if all(d.code == 'scope.empty_group' for d in diagnostics) else ScopeState.INVALID
        return ScopeResolution(state, diagnostics=tuple(diagnostics), policy_id=str(policy.id),
                               policy_name=policy.name, protocol=protocol, references=tuple(references))
    return ScopeResolution(ScopeState.RESTRICTED if predicate is not None else ScopeState.UNRESTRICTED,
                           predicate, policy_id=str(policy.id), policy_name=policy.name,
                           protocol=protocol, references=tuple(references))
