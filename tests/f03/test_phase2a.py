"""Additional Phase 2A diagnostics and deployment-boundary regressions."""
import unittest
from types import SimpleNamespace as NS
from harness import DB, Harness


class Phase2ATests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h.routes()
        self.h.load('app/api/routes_config.py', 'get_candidate apply_import restore_version', True)
        self.h.load('app/api/routes_diagnostics.py', 'validate_config_now', True)
        self.h.ns['CandidateOut'] = NS
        self.h.ns['config_compiler'].compute_diff = lambda active, candidate: 'diff' if active != candidate else ''
        self.h.ns['config_compiler'].validate_candidate = lambda text: self.fail('Native validation must not run for invalid scope')
        self.scope = self.h.ns['policy_scope']
        self.admin = NS(username='reviewer')
    def invalid_db(self):
        return DB(Policy=[self.h.policy(condition_device_id='deleted')])
    def resolve(self, p, inventory=None, protocol='tacacs'):
        return self.scope.resolve_scope(p, protocol, inventory or self.scope.ScopeInventory())
    def test_unrestricted_is_explicit_result(self):
        result = self.resolve(self.h.policy())
        self.assertEqual(result.state, self.scope.ScopeState.UNRESTRICTED)
        self.assertTrue(result.deployable)
        self.assertIsNone(result.predicate)
    def test_empty_is_distinct_and_non_deployable(self):
        p = self.h.policy(condition_device_group_id='dg')
        inv = self.scope.ScopeInventory(device_groups=[NS(id='dg', name='edge')])
        result = self.resolve(p, inv)
        self.assertEqual(result.state, self.scope.ScopeState.EMPTY)
        self.assertFalse(result.deployable)
    def test_partial_loss_has_no_usable_partial_predicate(self):
        p = self.h.policy(condition_device_id='d', condition_device_group_id='gone')
        inv = self.scope.ScopeInventory(devices=[NS(id='d', name='router', device_group_id=None)])
        result = self.resolve(p, inv)
        self.assertEqual(result.state, self.scope.ScopeState.INVALID)
        self.assertIsNone(result.predicate)
        self.assertEqual(result.policy_id, str(p.id))
        self.assertEqual(result.protocol, 'tacacs')
        self.assertEqual({r.object_id for r in result.references}, {'d', 'gone'})
        self.assertEqual({r.dimension for r in result.references}, {'condition_device_id', 'condition_device_group_id'})
    def test_multiple_protocol_diagnostics(self):
        p, r = self.h.policy(condition_device_id='gone'), self.h.policy(radius=True, condition_group_id='missing')
        with self.assertRaises(self.h.ns['UncompilablePolicyError']) as caught:
            self.h.call('compile_candidate', DB(Policy=[p], RadiusPolicy=[r]))
        diagnostics = caught.exception.diagnostics
        self.assertEqual({d['protocol'] for d in diagnostics}, {'tacacs', 'radius'})
        self.assertEqual({d['policy_id'] for d in diagnostics}, {str(p.id), str(r.id)})
        for d in diagnostics:
            self.assertTrue(d['policy_name'])
            self.assertTrue(d['dimension'])
            self.assertTrue(d['object_id'])
            self.assertTrue(d['object_type'])
            self.assertTrue(d['path'])
            self.assertEqual(d['code'], 'scope.reference_missing')
            self.assertNotIn('Traceback', d['reason'])
    def test_preview_is_non_applicable_without_candidate(self):
        result = self.h.call('get_candidate', self.invalid_db(), self.admin)
        self.assertFalse(result.applicable)
        self.assertEqual(result.candidate, '')
        self.assertEqual(result.diff, '')
        self.assertEqual(result.active, 'previous configuration')
        self.assertEqual(result.diagnostics[0]['object_id'], 'deleted')
        self.assertEqual(self.h.applied, [])
    def test_apply_returns_structured_conflict_before_side_effect(self):
        from harness import HTTPException
        db = self.invalid_db()
        with self.assertRaises(HTTPException) as caught:
            self.h.call('apply_config', NS(note=None), db, self.admin)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(caught.exception.detail['applicable'])
        self.assertEqual(caught.exception.detail['code'], 'invalid_policy_scope')
        self.assertTrue(caught.exception.detail['diagnostics'])
        self.assertEqual(self.h.applied, [])
        self.assertEqual(db.commits, 0)
    def test_valid_generated_candidate_reaches_apply(self):
        db = DB(Policy=[self.h.policy()])
        self.h.call('apply_config', NS(note=None), db, self.admin)
        self.assertEqual(len(self.h.applied), 1)
        self.assertIn('profile = restricted', self.h.applied[0])
    def test_diagnostics_does_not_invoke_daemon_for_invalid_scope(self):
        result = self.h.call('validate_config_now', self.invalid_db(), self.admin)
        self.assertFalse(result['applicable'])
        self.assertFalse(result['validated'])
        self.assertTrue(result['definitively_failed'])
        self.assertTrue(result['diagnostics'])
    def test_raw_import_still_uses_privileged_recovery_path(self):
        self.h.call('apply_import', NS(config_text='recovery text'), self.invalid_db(), self.admin)
        self.assertEqual(self.h.applied, ['recovery text'])
    def test_config_version_restore_still_uses_recovery_path(self):
        self.h.ns['_get_version_or_404'] = lambda db, number: NS(content='old known configuration')
        self.h.call('restore_version', 1, self.invalid_db(), self.admin)
        self.assertEqual(self.h.applied, ['old known configuration'])
    def test_disabled_invalid_policy_does_not_block(self):
        db = DB(Policy=[self.h.policy(enabled=False, condition_device_id='missing')])
        self.assertNotIn('profile = restricted', self.h.call('compile_candidate', db))
    def test_directory_membership_unknown_not_falsely_empty(self):
        p = self.h.policy(condition_group_id='g')
        inv = self.scope.ScopeInventory(identity_groups=[NS(id='g', name='ops')], external_identity_enabled=True)
        result = self.resolve(p, inv)
        self.assertEqual(result.state, self.scope.ScopeState.INVALID)
        self.assertEqual(result.diagnostics[0].code, 'scope.identity_membership_unknown')
    def test_empty_group_diagnostic_identifies_reference(self):
        p = self.h.policy(condition_device_group_id='dg')
        result = self.resolve(p, self.scope.ScopeInventory(device_groups=[NS(id='dg', name='edge')]))
        diagnostic = result.diagnostics[0].to_dict()
        self.assertEqual(diagnostic['object_id'], 'dg')
        self.assertEqual(diagnostic['path'], 'legacy.condition_device_group_id')
        self.assertEqual(diagnostic['code'], 'scope.empty_group')
    def test_multiple_roots_are_invalid(self):
        p = self.h.policy()
        groups = [NS(id=i, policy_id=p.id, parent_group_id=None, logical_operator='AND', order=0) for i in ('a', 'b')]
        result = self.resolve(p, self.scope.ScopeInventory(tree_groups=groups))
        self.assertEqual(result.state, self.scope.ScopeState.INVALID)
        self.assertIn('scope.invalid_root', [d.code for d in result.diagnostics])
    def test_foreign_child_is_invalid(self):
        p = self.h.policy()
        groups = [NS(id='a', policy_id=p.id, parent_group_id=None, logical_operator='AND', order=0),
                  NS(id='b', policy_id='other', parent_group_id='a', logical_operator='AND', order=0)]
        result = self.resolve(p, self.scope.ScopeInventory(tree_groups=groups))
        self.assertIn('scope.foreign_child', [d.code for d in result.diagnostics])
    def test_cyclic_disconnected_groups_are_invalid(self):
        p = self.h.policy()
        groups = [NS(id='a', policy_id=p.id, parent_group_id='b', logical_operator='AND', order=0),
                  NS(id='b', policy_id=p.id, parent_group_id='a', logical_operator='AND', order=0)]
        result = self.resolve(p, self.scope.ScopeInventory(tree_groups=groups))
        self.assertEqual(result.state, self.scope.ScopeState.INVALID)
    def test_empty_root_is_invalid_not_unrestricted(self):
        db = self.h.tree_db()
        db.rows['PolicyCondition'] = []
        with self.assertRaises(self.h.ns['UncompilablePolicyError']) as caught:
            self.h.call('compile_candidate', db)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'scope.empty_tree_group')
    def test_radius_service_type_preserved(self):
        p = self.h.policy(radius=True, condition_service_type='Login-User')
        profiles, rules = self.h.call('_radius_policy_blocks', DB(RadiusPolicy=[p]))
        self.assertIn('if (aaa.protocol == radius)', profiles)
        self.assertIn('if (radius[Service-Type] == Login-User)', profiles)
        self.assertNotIn('Service-Type', rules)
    def test_radius_malformed_service_type_rejected(self):
        p = self.h.policy(radius=True, condition_service_type='Login-User\npermit')
        result = self.resolve(p, protocol='radius')
        self.assertEqual(result.state, self.scope.ScopeState.INVALID)
        self.assertEqual(result.diagnostics[0].code, 'scope.malformed_service_type')
    def test_nested_boolean_structure_retained(self):
        p = self.h.policy()
        groups = [NS(id='root', policy_id=p.id, parent_group_id=None, logical_operator='AND', order=0),
                  NS(id='or', policy_id=p.id, parent_group_id='root', logical_operator='OR', order=0)]
        conditions = [self.h.leaf(group_id='root', object_type='source_ip', value='192.0.2.1'),
                      self.h.leaf(group_id='or', referenced_object_id='a'),
                      self.h.leaf(group_id='or', referenced_object_id='b')]
        devices = [NS(id=i, name=i, device_group_id=None) for i in ('a', 'b')]
        result = self.resolve(p, self.scope.ScopeInventory(devices=devices, tree_groups=groups, conditions=conditions))
        self.assertEqual(self.h.call('_render_scope', result, []), 'nac == 192.0.2.1 && (device == a || device == b)')
