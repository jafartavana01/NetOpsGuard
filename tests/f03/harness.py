"""Source-function harness, following the repository's existing AST test pattern.

No application import, credentials, database, service, or network is required.
Function bodies are loaded unchanged. Route decorators/default dependency expressions
are removed ONLY in the test copy. This tests handler logic, not HTTP/DI wiring.
Query/transaction doubles deliberately DO NOT implement foreign keys or cascades.
"""
from __future__ import annotations
import ast
import copy
import ipaddress
import json
import runpy
import sys
import types
import uuid
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

class Field:
    def __init__(self, name): self.name = name
    def __eq__(self, value): return lambda row: getattr(row, self.name, None) == value
    def __ne__(self, value): return lambda row: getattr(row, self.name, None) != value
    def is_(self, value): return self == value
    def asc(self): return self
    def desc(self): return self

class ModelMeta(type):
    def __getattr__(cls, name): return Field(name)

class Record(metaclass=ModelMeta):
    def __init__(self, **values):
        self.id = uuid.uuid4()
        self.__dict__.update(values)

class Query:
    def __init__(self, db, model, rows=None):
        self.db, self.model = db, model
        self.rows = list(db.rows.get(model.__name__, [])) if rows is None else rows
    def filter(self, *predicates):
        return Query(self.db, self.model, [r for r in self.rows if all(p(r) for p in predicates)])
    def order_by(self, *fields):
        # Fixtures are inserted in deterministic priority/order. No ordering emulation.
        return self
    def all(self): return self.rows
    def first(self): return next(iter(self.rows), None)
    def delete(self):
        for row in self.rows: self.db.delete(row)

class DB:
    """A state/commit recorder, NOT a SQLAlchemy or PostgreSQL substitute."""
    def __init__(self, **rows):
        self.rows = rows
        self.commits = 0
        self.deleted = []
        self.saved = copy.deepcopy(rows)
    def query(self, model): return Query(self, model)
    def add(self, row): self.rows.setdefault(type(row).__name__, []).append(row)
    def delete(self, row):
        self.deleted.append(row)
        self.rows[type(row).__name__].remove(row)
    def flush(self): pass
    def refresh(self, row): pass
    def commit(self):
        self.commits += 1
        self.saved = copy.deepcopy(self.rows)
    def rollback(self): self.rows = copy.deepcopy(self.saved)

class HTTPException(Exception):
    def __init__(self, status_code, detail=None):
        self.status_code, self.detail = status_code, detail
        super().__init__(detail)

class Harness:
    def __init__(self):
        self.ns = dict(__package__='_f03.services', ipaddress=ipaddress, json=json,
                       uuid=uuid, TraceStep=lambda *a: a, HTTPException=HTTPException,
                       SimpleNamespace=NS, status=NS(HTTP_400_BAD_REQUEST=400, HTTP_404_NOT_FOUND=404,
                                 HTTP_409_CONFLICT=409), IntegrityError=type('IntegrityError', (Exception,), {}))
        for name in ('Policy PolicyCondition PolicyConditionGroup TacacsGroup NetworkDevice '
                     'DeviceGroup TacacsUser RadiusPolicy RadiusPolicyAttribute DeviceAccessGrant '
                     'MonitoringSettings AdSettings RadiusSettings CommandSet PolicyCommandSet '
                     'PolicyVersion InstallEvent').split():
            self.ns[name] = ModelMeta(name, (Record,), {})
        self.ns['policy_scope'] = NS(**runpy.run_path(str(ROOT / 'app/services/policy_scope.py')))
        self.load('app/services/condition_engine.py',
                  'has_condition_tree get_root_group _object_display_name evaluate_condition evaluate_group')
        self.ns['condition_engine'] = NS(**{n: self.ns[n] for n in ('has_condition_tree', 'get_root_group')})
        self.load('app/services/config_compiler.py',
                  'UncompilablePolicyError _scope_inventory _require_scope _render_scope _validate_scopes _condition_expression _compile_condition_leaf '
                  '_compile_condition_group_tree resolve_condition_expression _ruleset_block '
                  '_radius_policy_blocks compile_candidate get_uncompilable_policies '
                  '_compile_device_override_rule _policy_block _command_pattern_is_safe _UNSAFE_PATTERN_CHARS _quote')
        self.load('app/services/policy_engine.py', 'policy_matches')
        self.load('app/services/policy_versioning.py', 'PolicyRestoreError restore_diagnostic build_snapshot resolve_snapshot_for_restore')
        self.ns['policy_versioning'] = NS(PolicyRestoreError=self.ns['PolicyRestoreError'], restore_diagnostic=self.ns['restore_diagnostic'], build_snapshot=self.ns['build_snapshot'],
            resolve_snapshot_for_restore=self.ns['resolve_snapshot_for_restore'],
            record_version=lambda *a, **k: None)  # unrelated version-number allocation
        self.ns['policy_engine'] = NS(
            get_ordered_policies=lambda db: [p for p in db.rows.get('Policy', []) if p.enabled],
            get_ordered_rules_for_policy=lambda db, p: [])
        # Only unrelated host/authentication/settings renderers are replaced.
        for name in ('_host_block _group_block _user_block _monitoring_host_block '
                     '_device_override_profile_block _mavis_block _lockout_rule_blocks').split():
            self.ns[name] = lambda *a, **k: ''
        self.ns.update(_radius_blocks=lambda r: {}, STATIC_PREAMBLE='{policy_blocks}{ruleset_block}',
                       LOG_DIR='', ACCOUNTING_FIELD_SEPARATOR='')
        self.modules = {}
        for name, attrs in {
            '_f03.models.radius_policy': {n: self.ns[n] for n in ('RadiusPolicy', 'RadiusPolicyAttribute')},
            '_f03.models.radius_settings': {'RadiusSettings': self.ns['RadiusSettings']},
            '_f03.platform_settings': {'load_settings': lambda: {'tacacs_port': 49}},
        }.items():
            module = types.ModuleType(name)
            module.__dict__.update(attrs)
            self.modules[name] = module

    def load(self, path, names, routes=False):
        names = names.split()
        tree = ast.parse((ROOT / path).read_text())
        nodes = []
        found = set()
        for node in tree.body:
            name = getattr(node, 'name', None)
            if isinstance(node, ast.Assign): name = getattr(node.targets[0], 'id', None)
            if name not in names: continue
            found.add(name)
            if routes and isinstance(node, ast.FunctionDef):
                node.decorator_list = []
                node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
                node.args.kw_defaults = [ast.Constant(None) if x is not None else None for x in node.args.kw_defaults]
            nodes.append(node)
        if found != set(names): raise RuntimeError(f'Harness needs updating: {path}: {set(names)-found}')
        module = ast.Module([ast.ImportFrom(module='__future__', names=[ast.alias('annotations')], level=0)] + nodes, [])
        exec(compile(ast.fix_missing_locations(module), str(ROOT / path), 'exec'), self.ns)

    def call(self, name, *a, **kw):
        with patch.dict(sys.modules, self.modules): return self.ns[name](*a, **kw)

    def row(self, model, **kw): return self.ns[model](**kw)

    def policy(self, radius=False, **kw):
        defaults = dict(name='restricted', enabled=True, priority=1, created_at=1,
                        condition_group_id=None, condition_device_id=None,
                        condition_device_group_id=None, condition_service_type=None,
                        default_priv_lvl=15, default_action='deny', action='permit', description=None,
                        requires_manual_approval=False, manual_default_command_set_id=None)
        return self.row('RadiusPolicy' if radius else 'Policy', **(defaults | kw))

    def leaf(self, **kw):
        return self.row('PolicyCondition', **(dict(group_id='root', object_type='device',
            operator='equal', referenced_object_id='d', value='router', value_type='database_id', order=0) | kw))

    def tree_db(self, policy=None, leaf=None, operator='AND', **rows):
        policy = policy or self.policy()
        root = self.row('PolicyConditionGroup', id='root', policy_id=policy.id,
                        parent_group_id=None, logical_operator=operator, order=0)
        return DB(Policy=[policy], PolicyConditionGroup=[root],
                  PolicyCondition=[leaf or self.leaf()], **rows)

    def inventory(self):
        return dict(TacacsGroup=[self.row('TacacsGroup', id='g', name='ops')],
            DeviceGroup=[self.row('DeviceGroup', id='dg', name='edge')],
            NetworkDevice=[self.row('NetworkDevice', id='d', name='router', device_group_id='dg', enabled=True)],
            TacacsUser=[self.row('TacacsUser', id='u', username='alice', group_id='g', enabled=True, auth_source='local')])

    def routes(self):
        self.load('app/api/routes_policies.py', '_parse_optional_uuid _resolve_conditions create_policy update_policy', True)
        self.ns.update(_make_room_for_priority=lambda *a, **k: None,
                       _resolve_manual_command_set=lambda *a: None,
                       _replace_command_sets=lambda *a: [],
                       policy_to_out=lambda db, p, *a: p,
                       _get_policy_or_404=lambda db, pid: db.query(self.ns['Policy']).first())
        self.load('app/api/routes_policy_conditions.py', '_build_tree replace_condition_tree', True)
        self.load('app/api/routes_policy_versions.py', 'restore_policy_version', True)
        self.ns['_group_to_dict'] = lambda db, root: vars(root)
        self.load('app/api/routes_config.py', 'apply_config', True)
        self.applied = []
        def apply(db, **kw):
            self.applied.append(kw['candidate_text'])
            return NS(id='version')
        self.ns['config_compiler'] = NS(_scope_inventory=self.ns['_scope_inventory'], UncompilablePolicyError=self.ns['UncompilablePolicyError'], compile_candidate=lambda db: self.call('compile_candidate', db),
            get_active_config=lambda: 'previous configuration',
            get_uncompilable_policies=lambda db: self.call('get_uncompilable_policies', db),
            apply_candidate=apply, ApplyFailedError=type('ApplyFailedError', (Exception,), {}))
        self.ns['_version_out'] = lambda v: v

MAPS = dict(group_names_by_id={'g': 'ops'}, device_names_by_id={'d': 'router'},
            device_names_by_group_id={'dg': ['router']})

def source(path): return (ROOT / path).read_text()


def enable_evaluator(h):
    """Load the actual evaluator and effective-access handler, without app startup."""
    from dataclasses import dataclass, field
    h.ns.update(__name__='harness', dataclass=dataclass, field=field)
    h.load('app/services/policy_engine.py',
           'TraceStep EvaluationResult get_ordered_policies get_command_sets_for_policy '
           'get_ordered_rules_for_policy evaluate_command evaluate')
    h.load('app/services/condition_engine.py', 'RequestContext evaluate_policy_condition_tree')
    h.ns['CommandRule'] = ModelMeta('CommandRule', (Record,), {})
    condition_module = types.ModuleType('_f03.services.condition_engine')
    condition_module.__dict__.update({name: h.ns[name] for name in (
        'RequestContext', 'has_condition_tree', 'get_root_group', 'evaluate_policy_condition_tree')})
    parent = types.ModuleType('_f03.services'); parent.__path__ = []
    parent.condition_engine = condition_module
    root = types.ModuleType('_f03'); root.__path__ = []
    root.services = parent
    h.modules.update({'_f03': root, '_f03.services': parent,
                      '_f03.services.condition_engine': condition_module})
    h.ns['policy_engine'] = NS(**{name: h.ns[name] for name in (
        'get_ordered_policies', 'get_ordered_rules_for_policy', 'get_command_sets_for_policy', 'evaluate')})
    h.load('app/api/routes_effective_access.py', '_result_summary effective_access_for_user', True)
