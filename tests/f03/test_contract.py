"""F03 security contracts. Expected failures assert the FUTURE safe outcome.

Run through run.py: unexpected successes and non-assertion errors fail the run.
No expected failure is an assertion that today's unsafe behavior is desirable.
"""
import ast
import copy
import json
import shutil
import subprocess
import unittest
import uuid
from types import SimpleNamespace as NS
from harness import DB, Harness, HTTPException, MAPS, ROOT, source


def contract(finding, description):
    def decorate(fn):
        fn.__doc__ = f'{finding}: {description}'
        fn.finding = finding
        fn.classification = 'currently fails because it exposes F03'
        return unittest.expectedFailure(fn)
    return decorate


class ScopeTests(unittest.TestCase):
    def setUp(self): self.h = Harness()
    def expression(self, p, maps=None):
        return self.h.call('_condition_expression', p, **(maps or MAPS))
    def reject_candidate(self, db):
        # Runtime/type/import errors MUST NOT count as security rejection.
        with self.assertRaises(self.h.ns['UncompilablePolicyError']):
            self.h.call('compile_candidate', db)
    def test_intentional_unrestricted(self):
        """Intentional behavior: a no-tree/all-NULL policy remains a catch-all."""
        p = self.h.policy()
        text = self.h.call('compile_candidate', DB(Policy=[p]))
        self.assertIn('profile = restricted', text)
        selector = self.h.call('_ruleset_block', [(p, self.expression(p))])
        self.assertNotIn('if (', selector)
    def test_valid_partial_scope(self):
        """Protect correct behavior: Any identity/group with a valid device restriction."""
        p = self.h.policy(condition_device_id='d')
        self.assertEqual(self.expression(p), 'device == router')
        self.assertTrue(self.h.call('policy_matches', p, device_id='d')[0])
        self.assertFalse(self.h.call('policy_matches', p, device_id='other')[0])
    def test_valid_device_group(self):
        """Protect correct behavior: valid device group with unrestricted identity."""
        self.assertEqual(self.expression(self.h.policy(condition_device_group_id='dg')), 'device == router')
    def test_valid_identity_group(self):
        """Protect correct behavior: valid identity group with unrestricted device dimensions."""
        self.assertEqual(self.expression(self.h.policy(condition_group_id='g')), 'member == ops')
    def test_valid_multiple_dimensions(self):
        """Protect correct behavior: legacy device and device-group use conjunction."""
        p = self.h.policy(condition_device_id='d', condition_device_group_id='dg')
        self.assertEqual(self.expression(p), 'device == router && device == router')
    def test_disabled_device_still_resolves(self):
        """Protect correct behavior: disabling a device does not erase its selector."""
        rows = self.h.inventory(); rows['NetworkDevice'][0].enabled = False
        text = self.h.call('compile_candidate', DB(Policy=[self.h.policy(condition_device_id='d')], **rows))
        self.assertIn('if (device == router)', text)
    def test_null_provenance_is_not_recoverable(self):
        """Design limitation: persisted NULL alone cannot distinguish prior loss from intent."""
        intentional = self.h.policy()
        lost = self.h.policy(condition_device_id='d')
        # Explicit hypothetical post-FK state; NOT a database deletion simulation.
        lost.condition_device_id = None
        fields = ('condition_group_id', 'condition_device_id', 'condition_device_group_id')
        self.assertEqual([getattr(intentional, f) for f in fields], [getattr(lost, f) for f in fields])
        self.assertIsNone(self.expression(intentional))
        self.assertIsNone(self.expression(lost))


def add_legacy_contract(name, scope, inventory_change=None):
    @contract('T1/T2', 'Invalid enabled legacy scope must reject the candidate, never drop a dimension.')
    def test(self):
        rows = self.h.inventory()
        if inventory_change: inventory_change(rows)
        self.reject_candidate(DB(Policy=[self.h.policy(**scope)], **rows))
    setattr(ScopeTests, 'test_' + name, test)

for name, scope, change in [
    ('empty_device_group', {'condition_device_group_id': 'dg'}, lambda r: r.update(NetworkDevice=[])),
    ('empty_identity_group', {'condition_group_id': 'g'}, lambda r: r.update(TacacsUser=[])),
    ('missing_device', {'condition_device_id': 'gone'}, None),
    ('missing_device_group', {'condition_device_group_id': 'gone'}, None),
    ('missing_identity_group', {'condition_group_id': 'gone'}, None),
    ('partial_loss', {'condition_group_id': 'g', 'condition_device_group_id': 'gone'}, None),
]: add_legacy_contract(name, scope, change)


class TreeTests(unittest.TestCase):
    setUp = ScopeTests.setUp
    reject_candidate = ScopeTests.reject_candidate
    def test_tree_precedence(self):
        """Intentional behavior: an existing valid tree overrides legacy fields."""
        p = self.h.policy(condition_device_id='gone')
        db = self.h.tree_db(p, **self.h.inventory())
        expression = self.h.call('resolve_condition_expression', db, p, **MAPS, acl_blocks_out=[])
        self.assertEqual(expression, 'device == router')
    def test_leaf_rejects_missing_reference(self):
        """Protect correct behavior: the leaf compiler already rejects unresolved objects."""
        with self.assertRaises(self.h.ns['UncompilablePolicyError']):
            self.h.call('_compile_condition_leaf', self.h.leaf(referenced_object_id='gone'), **MAPS, acl_blocks_out=[])
    def test_supported_tree_simulation(self):
        """Protect correct behavior: supported device equality agrees with emitted selector."""
        c = self.h.leaf()
        context = NS(user=None, device=NS(id='d', name='router', device_group_id='dg'), source_ip=None)
        self.assertTrue(self.h.call('evaluate_condition', DB(), c, context)[0])
        self.assertEqual(self.h.call('_compile_condition_leaf', c, **MAPS, acl_blocks_out=[]), 'device == router')
    @contract('T6', 'Orphan tree data must not fall back to an unconditional legacy policy.')
    def test_missing_root(self):
        p = self.h.policy()
        child = self.h.row('PolicyConditionGroup', id='child', policy_id=p.id, parent_group_id='missing-root', logical_operator='AND', order=0)
        self.reject_candidate(DB(Policy=[p], PolicyConditionGroup=[child], PolicyCondition=[self.h.leaf(group_id='child')], **self.h.inventory()))
    @contract('T3', 'Invalid restrictive policy must block compilation, not expose a permissive fallback.')
    def test_restrictive_before_permissive_fallback(self):
        p = self.h.policy(default_action='deny')
        db = self.h.tree_db(p, self.h.leaf(referenced_object_id='gone'), **self.h.inventory())
        db.rows['Policy'].append(self.h.policy(name='fallback', priority=2, default_action='permit'))
        # Fixture proves the removed policy denies an arbitrary command whereas fallback permits.
        restricted = self.h.call('_policy_block', p, [])
        fallback = self.h.call('_policy_block', db.rows['Policy'][1], [])
        import re
        self.h.ns['re'] = re
        self.h.load('tests/test_policy_block_authorization.py', 'evaluate_profile')
        self.assertEqual(self.h.call('evaluate_profile', restricted, service='shell', cmd='configure terminal')[0], 'deny')
        self.assertEqual(self.h.call('evaluate_profile', fallback, service='shell', cmd='configure terminal')[0], 'permit')
        self.reject_candidate(db)
    @contract('SIM', 'An unsupported leaf beneath NOT must not become an authoritative match.')
    def test_invalid_under_not_simulator(self):
        db = self.h.tree_db(leaf=self.h.leaf(object_type='unsupported'), operator='NOT')
        ctx = NS(user=None, device=None, source_ip=None)
        result, trace = self.h.call('evaluate_group', db, db.rows['PolicyConditionGroup'][0], ctx)
        self.assertFalse(result, f'Invalid condition became a match: {trace}')
    @contract('SIM', 'Malformed negated CIDR must not become an authoritative match.')
    def test_malformed_negated_cidr_simulator(self):
        leaf = self.h.leaf(object_type='source_ip', operator='is_not_in_cidr', value='bad-cidr')
        ctx = NS(user=None, device=None, source_ip='192.0.2.1')
        result, trace = self.h.call('evaluate_condition', DB(), leaf, ctx)
        self.assertFalse(result, str(trace))
    @contract('SIM', 'An unresolved negated identity reference must not produce an authoritative match.')
    def test_deleted_negated_identity_simulator(self):
        leaf = self.h.leaf(object_type='user_group', operator='not_equal', referenced_object_id='gone')
        ctx = NS(user=NS(id='u', username='alice', group_id='g'), device=None, source_ip=None)
        self.assertFalse(self.h.call('evaluate_condition', DB(), leaf, ctx)[0])
    @contract('SIM', 'Malformed CIDR must be reported invalid, not evaluated as an ordinary false condition.')
    def test_malformed_cidr_simulator_validity(self):
        leaf = self.h.leaf(object_type='source_ip', operator='is_in_cidr', value='bad-cidr')
        # No public invalid-result type exists yet: fail-closed exception is this initial contract boundary.
        with self.assertRaises(ValueError):
            self.h.call('evaluate_condition', DB(), leaf, NS(user=None, device=None, source_ip='192.0.2.1'))


for name, values, operator in [
    ('missing_device', {'referenced_object_id': 'gone'}, 'AND'),
    ('missing_device_group', {'object_type': 'device_group', 'referenced_object_id': 'gone'}, 'AND'),
    ('missing_identity', {'object_type': 'user_group', 'referenced_object_id': 'gone'}, 'AND'),
    ('missing_user', {'object_type': 'user', 'referenced_object_id': 'gone'}, 'AND'),
    ('null_reference', {'referenced_object_id': None}, 'AND'),
    ('unsupported_leaf', {'object_type': 'alien'}, 'AND'),
    ('unsupported_operator', {'operator': 'alien'}, 'AND'),
    ('invalid_under_not', {'referenced_object_id': 'gone'}, 'NOT'),
    ('malformed_cidr', {'object_type': 'source_ip', 'operator': 'is_in_cidr', 'value': 'bad-cidr'}, 'AND'),
    ('malformed_negated_cidr', {'object_type': 'source_ip', 'operator': 'is_not_in_cidr', 'value': 'bad-cidr'}, 'AND'),
]:
    def make(values=values, operator=operator):
        @contract('T3', 'Invalid enabled tree must reject the whole candidate rather than be omitted/emitted.')
        def test(self):
            self.reject_candidate(self.h.tree_db(leaf=self.h.leaf(**values), operator=operator, **self.h.inventory()))
        return test
    setattr(TreeTests, 'test_candidate_' + name, make())


class RadiusTests(unittest.TestCase):
    def setUp(self): self.h = Harness()
    def test_intentional_unrestricted(self):
        """Intentional behavior: RADIUS catch-all retains protocol guard and an unconditional selector."""
        profiles, rules = self.h.call('_radius_policy_blocks', DB(RadiusPolicy=[self.h.policy(radius=True)]))
        self.assertIn('aaa.protocol == radius', profiles)
        self.assertIn('profile = rad_restricted', rules)
        self.assertNotIn('if (', rules)
    def test_valid_device_partial_unrestricted(self):
        """Protect correct behavior: RADIUS device-only restriction preserves Any identity/group."""
        profiles, rules = self.h.call('_radius_policy_blocks', DB(RadiusPolicy=[self.h.policy(radius=True, condition_device_id='d')], **self.h.inventory()))
        self.assertIn('if (device == router)', rules)
        self.assertNotIn('member ==', rules)
    def test_valid_group_scope(self):
        """Protect correct behavior: RADIUS identity plus device group remains conjunctive."""
        p = self.h.policy(radius=True, condition_group_id='g', condition_device_group_id='dg')
        _, rules = self.h.call('_radius_policy_blocks', DB(RadiusPolicy=[p], **self.h.inventory()))
        self.assertIn('member == ops && (device == router)', rules)
    @contract('R1', 'Lost RADIUS scope must never emit an unconditional selector.')
    def test_no_unconditional_after_scope_loss(self):
        # Stronger boundary: the generator must reject, rather than return omitted text.
        with self.assertRaises(self.h.ns['UncompilablePolicyError']) as caught:
            self.h.call('_radius_policy_blocks', DB(RadiusPolicy=[self.h.policy(radius=True, condition_device_id='gone')]))
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'scope.reference_missing')
        self.assertEqual(caught.exception.diagnostics[0]['protocol'], 'radius')

for name, scope, change in [
    ('empty_device_group', {'condition_device_group_id': 'dg'}, lambda r: r.update(NetworkDevice=[])),
    ('empty_identity_group', {'condition_group_id': 'g'}, lambda r: r.update(TacacsUser=[])),
    ('missing_device', {'condition_device_id': 'gone'}, None),
    ('missing_device_group', {'condition_device_group_id': 'gone'}, None),
    ('missing_identity', {'condition_group_id': 'gone'}, None),
    ('partial_loss', {'condition_group_id': 'g', 'condition_device_id': 'gone'}, None),
]:
    def make(scope=scope, change=change):
        @contract('R1/R2', 'Invalid enabled RADIUS scope must block the shared candidate independently of TACACS+.')
        def test(self):
            rows = self.h.inventory()
            if change: change(rows)
            with self.assertRaises(self.h.ns['UncompilablePolicyError']):
                self.h.call('compile_candidate', DB(RadiusPolicy=[self.h.policy(radius=True, **scope)], **rows))
        return test
    setattr(RadiusTests, 'test_' + name, make())

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.routes()
        self.admin = NS(username='reviewer')
    def restore(self, snapshot, with_tree=False):
        snapshot = dict(condition_device_name=None, condition_device_group_name=None,
                        condition_group_name=None, command_set_names=[]) | snapshot
        p = self.h.policy(condition_device_id=uuid.uuid4())
        version = self.h.row('PolicyVersion', policy_id=p.id, snapshot=json.dumps(snapshot), version_number=1)
        rows = dict(Policy=[p], PolicyVersion=[version])
        if with_tree:
            # Complete the existing MAPS-backed fixture for inventory-based resolution.
            rows.update(self.h.inventory())
            rows['PolicyConditionGroup'] = [self.h.row('PolicyConditionGroup', id='root', policy_id=p.id, parent_group_id=None, logical_operator='AND', order=0)]
            rows['PolicyCondition'] = [self.h.leaf()]
        db = DB(**rows)
        self.restore_db = db
        self.restore_before = copy.deepcopy(vars(p))
        result = self.h.call('restore_policy_version', str(p.id), str(version.id), db, self.admin)
        return db, result
    @contract('RESTORE', 'A restore with a missing reference must not commit NULL scope after a warning.')
    def test_restore_warning_must_not_commit_null(self):
        with self.assertRaises(HTTPException) as caught:
            self.restore({'condition_device_name': 'deleted', 'enabled': True})
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn('policy.restore.reference_missing',
                      [d['code'] for d in caught.exception.detail['diagnostics']])
        self.assertEqual(self.restore_db.commits, 0)
        self.assertEqual(vars(self.restore_db.rows['Policy'][0]), self.restore_before)
    @contract('RESTORE', 'Complete policy snapshots must retain tree scope, not only legacy fields.')
    def test_snapshot_retains_tree(self):
        p = self.h.policy()
        db = self.h.tree_db(p)
        snapshot = self.h.call('build_snapshot', db, p)
        self.assertTrue(any('tree' in key for key in snapshot), 'No condition tree in version snapshot')
    @contract('RESTORE', 'Restoring legacy scope onto an existing tree must not silently retain conflicting effective scope.')
    def test_tree_backed_restore(self):
        with self.assertRaises(HTTPException) as caught:
            self.restore({}, with_tree=True)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn('policy.restore.tree_unsupported',
                      [d['code'] for d in caught.exception.detail['diagnostics']])
        self.assertEqual(self.restore_db.commits, 0)
        self.assertEqual(vars(self.restore_db.rows['Policy'][0]), self.restore_before)
        self.assertEqual(len(self.restore_db.rows['PolicyCondition']), 1)
    def save_then_fail_tree(self, editing):
        # Replays the old editor first request with omitted scope intent.
        # It must now be rejected before any second request can be needed.
        p = self.h.policy(condition_device_id=uuid.uuid4())
        db = DB(Policy=[p] if editing else [])
        payload = NS(**vars(self.h.policy()), command_set_ids=[], change_description=None)
        with self.assertRaises(HTTPException) as caught:
            if editing:
                self.h.call('update_policy', str(p.id), payload, db, self.admin)
            else:
                self.h.call('create_policy', payload, db, self.admin)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertEqual(db.commits, 0, 'Incomplete request must not commit an intermediate policy')
        return db
    @contract('T4', 'Failed tree save must not leave a new enabled unrestricted policy committed.')
    def test_new_policy_two_step_failure(self):
        db = self.save_then_fail_tree(False)
        self.assertFalse(any(p.enabled and all(getattr(p, f) is None for f in
            ('condition_group_id', 'condition_device_id', 'condition_device_group_id')) for p in db.rows['Policy']))
    @contract('T4', 'Failed tree save must preserve the old restrictive scope of an edited legacy policy.')
    def test_edit_policy_two_step_failure(self):
        db = self.save_then_fail_tree(True)
        self.assertIsNotNone(db.rows['Policy'][0].condition_device_id, 'First transaction already erased scope')
    @contract('T3/APPLY', 'Invalid enabled scope must prevent reaching the apply side-effect boundary.')
    def test_apply_blocks_invalid_with_fallback(self):
        db = self.h.tree_db(leaf=self.h.leaf(referenced_object_id='gone'), **self.h.inventory())
        db.rows['Policy'].append(self.h.policy(name='fallback', priority=2, default_action='permit'))
        try:
            self.h.call('apply_config', NS(note='test'), db, self.admin)
        except (HTTPException, self.h.ns['UncompilablePolicyError']):
            pass
        self.assertEqual(self.h.applied, [], 'Unsafe candidate reached apply_candidate')
    @contract('T1/MEMBERSHIP', 'Removing the last member must not leave an enabled policy deployable as Any.')
    def test_remove_final_device(self):
        device_id = uuid.uuid4()
        group = self.h.row('DeviceGroup', id='dg', name='edge')
        device = self.h.row('NetworkDevice', id=device_id, name='router', device_group_id='dg', enabled=True)
        db = DB(DeviceGroup=[group], NetworkDevice=[device], Policy=[self.h.policy(condition_device_group_id='dg')])
        self.h.load('app/api/routes_device_groups.py', 'remove_member', True)
        self.h.ns['_get_group_or_404'] = lambda db, gid: group
        try:
            self.h.call('remove_member', 'dg', str(device_id), db, self.admin)
        except HTTPException:
            return  # dependency protection is an acceptable future boundary
        self.assertIsNone(db.saved['NetworkDevice'][0].device_group_id)
        with self.assertRaises(self.h.ns['UncompilablePolicyError']): self.h.call('compile_candidate', db)

for dimension in ('device', 'device_group', 'group'):
    def make(dimension=dimension):
        @contract('RESTORE', 'Missing named scope during restore must be rejected, not resolved to Any.')
        def test(self):
            with self.assertRaises((ValueError, HTTPException, self.h.ns['UncompilablePolicyError'])):
                self.h.call('resolve_snapshot_for_restore', DB(),
                    dict(condition_device_name=None, condition_device_group_name=None,
                         condition_group_name=None, command_set_names=[]) | {f'condition_{dimension}_name': 'deleted'})
        return test
    setattr(LifecycleTests, 'test_restore_missing_' + dimension, make())

for model, path, fn, getter, field, object_type in [
    ('NetworkDevice', 'app/api/routes_devices.py', 'delete_device', '_get_device_or_404', 'condition_device_id', 'device'),
    ('DeviceGroup', 'app/api/routes_device_groups.py', 'delete_device_group', '_get_group_or_404', 'condition_device_group_id', 'device_group'),
    ('TacacsGroup', 'app/api/routes_tacacs_groups.py', 'delete_group', '_get_group_or_404', 'condition_group_id', 'user_group'),
    ('TacacsUser', 'app/api/routes_tacacs_users.py', 'delete_user', '_get_user_or_404', None, 'user'),
]:
    for mode in (('tree',) if field is None else ('legacy', 'radius', 'tree')):
        def make(model=model, path=path, fn=fn, getter=getter, field=field, object_type=object_type, mode=mode):
            def test(self):
                """T2/R2: Actual DELETE transaction rejects references and preserves complete rows."""
                import sys
                sys.path.insert(0, str(ROOT / 'tests/dependencies'))
                from legacy_contract_bridge import assert_deletion_case
                assert_deletion_case(self, model, path, fn, field, object_type, mode)
            test.finding = 'T2/R2'
            test.classification = 'currently passes: transactional dependency protection'
            return test
        setattr(LifecycleTests, 'test_delete_' + mode + '_' + model.lower(), make())


class ModelTests(unittest.TestCase):
    def test_tree_reference_is_not_a_foreign_key(self):
        """Source/model limitation: polymorphic tree target UUID has no FK; DB tests are separate."""
        tree = ast.parse(source('app/models/policy_condition.py'))
        field = next(n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', '') == 'referenced_object_id')
        self.assertFalse(any(isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'ForeignKey' for n in ast.walk(field)))
    def test_policy_schema_missing_fields_default_null(self):
        """Source contract used by API failure fixture: omitted legacy inputs default to NULL."""
        tree = ast.parse(source('app/schemas/policy.py'))
        fields = {n.target.id: n.value for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
        for name in ('condition_group_id', 'condition_device_id', 'condition_device_group_id'):
            self.assertIsInstance(fields[name], ast.Constant)
            self.assertIsNone(fields[name].value)

for path in ('app/models/policy.py', 'app/models/radius_policy.py'):
    for field in ('condition_group_id', 'condition_device_id', 'condition_device_group_id'):
        def make(path=path, field=field):
            @contract('T2/R2', 'Declared scope FK must preserve restrictive intent on deletion; model inspection only.')
            def test(self):
                tree = ast.parse(source(path))
                node = next(n for n in ast.walk(tree) if isinstance(n, ast.AnnAssign) and getattr(n.target, 'id', '') == field)
                fk = next(n for n in ast.walk(node) if isinstance(n, ast.Call) and getattr(n.func, 'id', '') == 'ForeignKey')
                ondelete = next(k.value.value for k in fk.keywords if k.arg == 'ondelete')
                self.assertIn(ondelete, ('RESTRICT', 'NO ACTION'))
            return test
        setattr(ModelTests, 'test_' + path.split('/')[-1].replace('.py', '') + '_' + field, make())


class EditorTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js required to execute the real editor conversion function')
    @contract('T5', 'Saving legacy device AND group via the editor must preserve its intersection.')
    def test_legacy_and_preserved(self):
        text = source('app/templates/policies.html')
        start = text.index('  function msEntriesToConditionTree(')
        end = text.index('\n  // Reverse conversion', start)
        program = text[start:end] + '''
const tree = msEntriesToConditionTree([], [
 {object_type:'device', id:'R1'}, {object_type:'device_group', id:'edge'}]);
console.log(JSON.stringify(tree));
'''
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, check=True)
        tree = json.loads(result.stdout)
        def matches(group, device, device_group):
            values = [({'device': device, 'device_group': device_group}[c['object_type']] == c['referenced_object_id']) for c in group['conditions']]
            values += [matches(g, device, device_group) for g in group['child_groups']]
            return all(values) if group['logical_operator'] == 'AND' else any(values)
        # R2 is in edge but was excluded by the original R1 AND edge condition.
        self.assertFalse(matches(tree, 'R2', 'edge'))
        self.assertTrue(matches(tree, 'R1', 'edge'))
        self.assertFalse(matches(tree, 'R1', 'other'))

class EffectiveAccessTests(unittest.TestCase):
    def setUp(self):
        from harness import enable_evaluator
        self.h = Harness()
        enable_evaluator(self.h)
    @contract('SIM', 'Effective-access must not report unsupported NOT conditions as deployed reachability.')
    def test_unsupported_tree_not_authoritative(self):
        rows = self.h.inventory()
        user = rows['TacacsUser'][0]; user.id = uuid.uuid4()
        db = self.h.tree_db(leaf=self.h.leaf(object_type='unsupported'), operator='NOT', **rows)
        try:
            result = self.h.call('effective_access_for_user', str(user.id), db, None)
        except (ValueError, HTTPException, self.h.ns['UncompilablePolicyError']):
            return
        self.assertEqual(result['total_reachable'], 0,
                         'Unsupported condition became authoritative effective access')
    @contract('SIM/T1', 'Legacy simulator/compiler scope must agree or explicitly reject an invalid candidate.')
    def test_empty_legacy_group_parity(self):
        rows = self.h.inventory(); rows['NetworkDevice'][0].device_group_id = None
        p = self.h.policy(condition_device_group_id='dg')
        db = DB(Policy=[p], **rows)
        result = self.h.call('evaluate', db, user=rows['TacacsUser'][0], device=rows['NetworkDevice'][0])
        try: text = self.h.call('compile_candidate', db)
        except self.h.ns['UncompilablePolicyError']: return
        self.assertIsNone(result.matched_policy)
        self.assertNotIn('profile = restricted', text, 'Simulator denied scope but candidate selected profile unconditionally')

for object_type, inventory_key, ref in [('device_group', 'NetworkDevice', 'dg'), ('user_group', 'TacacsUser', 'g')]:
    def make(object_type=object_type, inventory_key=inventory_key, ref=ref):
        @contract('T3/EMPTY', 'An enabled tree depending on a known empty group is non-deployable.')
        def test(self):
            rows = self.h.inventory(); rows[inventory_key] = []
            self.reject_candidate(self.h.tree_db(leaf=self.h.leaf(object_type=object_type, referenced_object_id=ref), **rows))
        return test
    setattr(TreeTests, 'test_empty_' + object_type, make())


# Individually verified Phase 2A corrections. No contract assertion is relaxed.
# Keep these as ordinary regressions; all unlisted lifecycle/simulator cases stay XFAIL.
PHASE_2A_RESOLVED = (
    'EffectiveAccessTests.test_empty_legacy_group_parity',
    'LifecycleTests.test_apply_blocks_invalid_with_fallback',
    'LifecycleTests.test_remove_final_device',
    'RadiusTests.test_empty_device_group',
    'RadiusTests.test_empty_identity_group',
    'RadiusTests.test_missing_device',
    'RadiusTests.test_missing_device_group',
    'RadiusTests.test_missing_identity',
    'RadiusTests.test_no_unconditional_after_scope_loss',
    'RadiusTests.test_partial_loss',
    'ScopeTests.test_empty_device_group',
    'ScopeTests.test_empty_identity_group',
    'ScopeTests.test_missing_device',
    'ScopeTests.test_missing_device_group',
    'ScopeTests.test_missing_identity_group',
    'ScopeTests.test_partial_loss',
    'TreeTests.test_candidate_invalid_under_not',
    'TreeTests.test_candidate_malformed_cidr',
    'TreeTests.test_candidate_malformed_negated_cidr',
    'TreeTests.test_candidate_missing_device',
    'TreeTests.test_candidate_missing_device_group',
    'TreeTests.test_candidate_missing_identity',
    'TreeTests.test_candidate_missing_user',
    'TreeTests.test_candidate_null_reference',
    'TreeTests.test_candidate_unsupported_leaf',
    'TreeTests.test_candidate_unsupported_operator',
    'TreeTests.test_empty_device_group',
    'TreeTests.test_empty_user_group',
    'TreeTests.test_missing_root',
    'TreeTests.test_restrictive_before_permissive_fallback',
)
for _name in PHASE_2A_RESOLVED:
    _class, _method = _name.split(".")
    _test = getattr(globals()[_class], _method)
    _test.__unittest_expecting_failure__ = False
    _test.classification = "currently passes: Phase 2A production correction"

# Narrow release-blocker correction: reject lossy restoration, not lifecycle redesign.
RESTORATION_RESOLVED = (
    'LifecycleTests.test_restore_missing_device',
    'LifecycleTests.test_restore_missing_device_group',
    'LifecycleTests.test_restore_missing_group',
    'LifecycleTests.test_restore_warning_must_not_commit_null',
    'LifecycleTests.test_tree_backed_restore',
)
for _name in RESTORATION_RESOLVED:
    _class, _method = _name.split('.')
    _test = getattr(globals()[_class], _method)
    _test.__unittest_expecting_failure__ = False
    _test.classification = 'currently passes: restoration rejected before mutation'

# The former partial-save request is now rejected; real atomic transactions have
# a separate mandatory PostgreSQL suite. No unrelated XFAIL is reclassified.
for _method in ('test_new_policy_two_step_failure', 'test_edit_policy_two_step_failure'):
    _test = getattr(LifecycleTests, _method)
    _test.__unittest_expecting_failure__ = False
    _test.classification = 'passes: incomplete split-save request rejected before mutation'
