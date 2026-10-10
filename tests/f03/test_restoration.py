"""Actual restoration/compiler/apply functions with DB doubles; no native/PG claims."""
import copy
import json
import unittest
import uuid
from types import SimpleNamespace as NS
from harness import Harness, DB, HTTPException


def snapshot(**changes):
    return dict(name='restricted', description=None, enabled=True, priority=1,
                condition_device_name=None, condition_device_group_name=None,
                condition_group_name=None, command_set_names=[],
                default_priv_lvl=15, default_action='permit') | changes


class RestorationTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(); self.h.routes()
        self.device = self.h.row('NetworkDevice', id=uuid.uuid4(), name='router', enabled=True, device_group_id=None)
        self.policy = self.h.policy(condition_device_id=self.device.id)
        self.db = DB(Policy=[self.policy], NetworkDevice=[self.device])
        self.admin = NS(username='reviewer')

    def restore(self, data):
        v = self.h.row('PolicyVersion', policy_id=self.policy.id, snapshot=json.dumps(data), version_number=1)
        self.db.rows['PolicyVersion'] = [v]
        return self.h.call('restore_policy_version', str(self.policy.id), str(v.id), self.db, self.admin)

    def reject_unchanged(self, data, code):
        before = copy.deepcopy(vars(self.policy))
        with self.assertRaises(HTTPException) as caught: self.restore(data)
        self.assertEqual(caught.exception.status_code, 409)
        detail = caught.exception.detail
        self.assertEqual(detail['code'], 'policy.restore.invalid'); self.assertFalse(detail['restored'])
        self.assertIn(code, [d['code'] for d in detail['diagnostics']])
        self.assertEqual(vars(self.policy), before); self.assertEqual(self.db.commits, 0)
        self.assertEqual(len(self.db.rows['PolicyVersion']), 1)
        self.assertEqual(self.db.rows['PolicyVersion'][0].snapshot, json.dumps(data))
        return detail

    def test_existing_device_restores_restriction(self):
        self.restore(snapshot(condition_device_name='router'))
        self.assertEqual(self.policy.condition_device_id, self.device.id)
        self.assertIn('device == router', self.h.call('compile_candidate', self.db))

    def test_intentional_unrestricted_history_still_restores(self):
        self.restore(snapshot()); self.assertIsNone(self.policy.condition_device_id)
        self.assertIn('script {\n                profile = restricted', self.h.call('compile_candidate', self.db))

    def test_missing_device_preserves_live_policy_and_history(self):
        detail = self.reject_unchanged(snapshot(condition_device_name='missing'), 'policy.restore.reference_missing')
        d = next(d for d in detail['diagnostics'] if d['code'] == 'policy.restore.reference_missing')
        self.assertEqual(d['object_name'], 'missing'); self.assertEqual(d['object_type'], 'device')
        self.assertEqual(d['policy_id'], str(self.policy.id)); self.assertEqual(d['protocol'], 'tacacs')

    def test_missing_restore_does_not_create_unconditional_candidate(self):
        self.reject_unchanged(snapshot(condition_device_name='missing'), 'policy.restore.reference_missing')
        candidate = self.h.call('compile_candidate', self.db)
        self.assertIn('if (device == router)', candidate)
        self.assertNotIn('script {\n                profile = restricted', candidate)

    def test_apply_after_rejection_only_sees_preserved_restriction(self):
        self.reject_unchanged(snapshot(condition_device_name='missing'), 'policy.restore.reference_missing')
        self.h.call('apply_config', NS(note='test'), self.db, self.admin)
        self.assertEqual(len(self.h.applied), 1); self.assertIn('if (device == router)', self.h.applied[0])

    def test_injected_unresolved_reference_blocked_at_candidate_and_apply(self):
        self.policy.condition_device_id = uuid.uuid4()
        with self.assertRaises(self.h.ns['UncompilablePolicyError']): self.h.call('compile_candidate', self.db)
        with self.assertRaises(HTTPException) as caught: self.h.call('apply_config', NS(note='test'), self.db, self.admin)
        self.assertEqual(caught.exception.status_code, 409); self.assertEqual(self.h.applied, [])

    def test_partial_loss_rejects_entire_restore(self):
        self.reject_unchanged(snapshot(condition_device_name='router', condition_device_group_name='missing'), 'policy.restore.reference_missing')

    def test_multiple_missing_references_all_diagnosed(self):
        d = self.reject_unchanged(snapshot(condition_device_name='missing', condition_device_group_name='missing', condition_group_name='missing', command_set_names=['missing']), 'policy.restore.reference_missing')
        self.assertEqual(len([x for x in d['diagnostics'] if x['code'] == 'policy.restore.reference_missing']), 4)

    def test_missing_command_set_does_not_remove_restrictions(self):
        self.reject_unchanged(snapshot(command_set_names=['missing']), 'policy.restore.reference_missing')

    def test_missing_identity_group(self):
        self.reject_unchanged(snapshot(condition_group_name='missing'), 'policy.restore.reference_missing')

    def test_missing_device_group(self):
        self.reject_unchanged(snapshot(condition_device_group_name='missing'), 'policy.restore.reference_missing')

    def test_malformed_reference_not_interpreted_as_any(self):
        for value in ('', [], {}, 0, False):
            with self.subTest(value=value): self.reject_unchanged(snapshot(condition_device_name=value), 'policy.restore.snapshot_invalid')

    def test_incomplete_scope_snapshot_is_not_any(self):
        s = snapshot(); del s['condition_device_name']
        self.reject_unchanged(s, 'policy.restore.snapshot_invalid')

    def test_malformed_snapshot_structure(self):
        for s in (None, [], 'invalid'):
            with self.subTest(snapshot=s): self.reject_unchanged(s, 'policy.restore.snapshot_invalid')

    def test_malformed_command_sets(self):
        for value in (None, 'set', [''], [False]):
            with self.subTest(value=value): self.reject_unchanged(snapshot(command_set_names=value), 'policy.restore.snapshot_invalid')

    def test_disabled_snapshot_cannot_silently_lose_reference(self):
        self.reject_unchanged(snapshot(enabled=False, condition_device_name='missing'), 'policy.restore.reference_missing')

    def test_tree_backed_target_not_overlaid_with_legacy_restore(self):
        self.db.rows['PolicyConditionGroup'] = [self.h.row('PolicyConditionGroup', id='root', policy_id=self.policy.id, parent_group_id=None, logical_operator='AND', order=0)]
        self.db.rows['PolicyCondition'] = [self.h.leaf(referenced_object_id=self.device.id)]
        self.reject_unchanged(snapshot(), 'policy.restore.tree_unsupported')
        self.assertEqual(len(self.db.rows['PolicyCondition']), 1)

    def test_unsupported_tree_snapshot_rejected(self):
        self.reject_unchanged(snapshot(condition_tree={'user':'missing'}), 'policy.restore.snapshot_unsupported')

    def test_empty_referenced_group_not_restored_as_deployable(self):
        self.db.rows['DeviceGroup'] = [self.h.row('DeviceGroup', id=uuid.uuid4(), name='empty')]
        self.reject_unchanged(snapshot(condition_device_group_name='empty'), 'scope.empty_group')

    def test_missing_live_reference_is_retained_as_snapshot_blocker(self):
        self.policy.condition_device_id = uuid.uuid4()
        saved = self.h.call('build_snapshot', self.db, self.policy)
        self.assertTrue(saved.get('restoration_blockers'))
        self.reject_unchanged(saved, 'policy.restore.reference_missing')

    def test_snapshot_records_tree_restoration_limit(self):
        saved = self.h.call('build_snapshot', self.h.tree_db(self.policy), self.policy)
        self.assertTrue(saved.get('restoration_blockers'))
        self.reject_unchanged(saved, 'policy.restore.tree_unsupported')

    def test_valid_device_group_and_identity_preserve_conjunction(self):
        group = self.h.row('DeviceGroup', id=uuid.uuid4(), name='edge')
        identity = self.h.row('TacacsGroup', id=uuid.uuid4(), name='ops', authority='LEGACY')
        self.device.device_group_id = group.id
        self.db.rows.update(DeviceGroup=[group], TacacsGroup=[identity],
            TacacsUser=[self.h.row('TacacsUser', id=uuid.uuid4(), username='localuser', group_id=identity.id, enabled=True, auth_source='local')])
        self.restore(snapshot(condition_device_name='router', condition_device_group_name='edge', condition_group_name='ops'))
        candidate = self.h.call('compile_candidate', self.db)
        self.assertIn('member == ops && device == router && (device == router)', candidate)

    def test_valid_command_sets_keep_order(self):
        sets = [self.h.row('CommandSet', id=uuid.uuid4(), name=n) for n in ('first', 'second')]
        self.db.rows['CommandSet'] = sets
        self.restore(snapshot(condition_device_name='router', command_set_names=['second', 'first']))
        self.assertEqual([x.command_set_id for x in self.db.rows['PolicyCommandSet']], [sets[1].id, sets[0].id])

    def test_duplicate_name_never_selects_arbitrary_object(self):
        self.db.rows['NetworkDevice'].append(self.h.row('NetworkDevice', id=uuid.uuid4(), name='router', enabled=True))
        self.reject_unchanged(snapshot(condition_device_name='router'), 'policy.restore.reference_ambiguous')

    def test_snapshot_does_not_erase_missing_command_set_id(self):
        missing = uuid.uuid4()
        self.db.rows['PolicyCommandSet'] = [self.h.row('PolicyCommandSet', policy_id=self.policy.id, command_set_id=missing, order=0)]
        s = self.h.call('build_snapshot', self.db, self.policy)
        self.assertEqual(s['restoration_blockers'][0]['object_id'], str(missing))
        self.reject_unchanged(s, 'policy.restore.reference_missing')

    def test_existing_external_restore_block_remains(self):
        self.reject_unchanged(snapshot(external_scope_bindings=[{'group_id':'external'}]), 'policy.restore.external_unsupported')

    def test_known_empty_local_identity_group_blocked(self):
        self.db.rows['TacacsGroup'] = [self.h.row('TacacsGroup', id=uuid.uuid4(), name='empty', authority='LEGACY')]
        self.reject_unchanged(snapshot(condition_group_name='empty'), 'scope.empty_group')

    def test_invalid_json_rejected_without_mutation(self):
        v = self.h.row('PolicyVersion', policy_id=self.policy.id, snapshot='{invalid', version_number=1)
        self.db.rows['PolicyVersion'] = [v]
        before = copy.deepcopy(vars(self.policy))
        with self.assertRaises(HTTPException) as caught:
            self.h.call('restore_policy_version', str(self.policy.id), str(v.id), self.db, self.admin)
        self.assertEqual(caught.exception.detail['diagnostics'][0]['code'], 'policy.restore.snapshot_invalid')
        self.assertEqual(vars(self.policy), before); self.assertEqual(self.db.commits, 0)
