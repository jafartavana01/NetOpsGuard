"""Positive EXTERNAL contract. Source-function tests; no LDAP/PG/native claims."""
import json
import difflib
import shutil
import subprocess
import unittest
import uuid
from types import SimpleNamespace as NS
from harness import DB, Harness, HTTPException, source

SOURCE = uuid.UUID('00112233-4455-6677-8899-aabbccddeeff')
TOKEN = 'netopsguard_ad_' + SOURCE.hex

class ExternalAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.scope = self.h.ns['policy_scope']
        self.group = self.h.row('TacacsGroup', id='g', name='ops', description=None,
            authority='EXTERNAL', external_source_id=SOURCE, ad_group_name='AAA-ops')
        self.backend = self.h.row('AdSettings', id=SOURCE, enabled=True, host='ad.example.test',
            port=636, use_tls=True, use_starttls=False, use_memberof=True, group_prefix='AAA-',
            search_base='DC=example,DC=test', bind_dn='CN=reader,DC=example,DC=test',
            bind_password_encrypted='test-only', user_filter_template='(sAMAccountName=%s)')
        self.policy = self.h.policy(condition_group_id='g')
        self.inv = self.scope.ScopeInventory(identity_groups=[self.group],
            external_sources=[self.backend], external_identity_enabled=True)
    def result(self, policy=None, protocol='tacacs'):
        return self.scope.resolve_scope(policy or self.policy, protocol, self.inv)
    def blocked(self, code, policy=None, protocol='tacacs'):
        r = self.result(policy, protocol)
        self.assertFalse(r.deployable)
        self.assertIsNone(r.predicate)
        self.assertIn(code, [d.code for d in r.diagnostics])
    def expression(self):
        return self.h.call('_render_scope', self.result(), [])
    def db(self):
        return DB(Policy=[self.policy], TacacsGroup=[self.group], AdSettings=[self.backend],
            TacacsUser=self.inv.users, NetworkDevice=self.inv.devices,
            PolicyConditionGroup=self.inv.tree_groups, PolicyCondition=self.inv.conditions)
    def tree(self, op='equal', logical='AND'):
        self.inv.tree_groups=[self.h.row('PolicyConditionGroup', id='root', policy_id=self.policy.id,
            parent_group_id=None, logical_operator=logical, order=0)]
        self.inv.conditions=[self.h.leaf(object_type='user_group', referenced_object_id='g', operator=op)]
    def test_positive_external_without_local_rows(self):
        self.assertTrue(self.result().deployable)
        self.assertEqual(self.expression(), f'identity-source == {TOKEN} && member == ops && aaa.protocol == tacacs')
    def test_source_name_stable_and_safe(self):
        self.assertEqual(self.scope.external_source_name(SOURCE), TOKEN)
        self.assertEqual(self.scope.external_source_name(str(SOURCE).upper()), TOKEN)
    def test_source_missing(self):
        self.inv.external_sources=[]; self.blocked('scope.external_source_missing')
    def test_binding_missing(self):
        self.group.external_source_id=None; self.blocked('scope.external_source_missing')
    def test_wrong_source(self):
        self.backend.id=uuid.uuid4(); self.blocked('scope.external_source_missing')
    def test_disabled_backend(self):
        self.backend.enabled=False; self.blocked('scope.external_backend_disabled')
    def test_memberof_disabled(self):
        self.backend.use_memberof=False; self.blocked('scope.external_membership_disabled')
    def test_incomplete_backend(self):
        self.backend.bind_password_encrypted=None; self.blocked('scope.external_backend_incomplete')
    def test_unsupported_starttls_not_falsely_certified(self):
        self.backend.use_starttls=True; self.blocked('scope.external_backend_unsupported')
    def test_multiple_sources_not_silently_first(self):
        self.inv.external_sources.append(NS(id=uuid.uuid4())); self.blocked('scope.external_source_ambiguous')
    def test_mapping_case_preserved(self):
        self.group.ad_group_name='aaa-ops'; self.assertTrue(self.result().deployable)
        self.group.ad_group_name='AAA-Ops'; self.blocked('scope.external_mapping_mismatch')
    def test_prefix_metacharacters_block(self):
        for value in ('AAA.*', '^AAA-', 'AAA|', 'AAA[', 'AAA\\', 'AAA$'):
            with self.subTest(prefix=value):
                self.backend.group_prefix=value; self.blocked('scope.external_prefix_unsafe')
    def test_empty_prefix_supported_without_alias(self):
        self.backend.group_prefix=''; self.group.ad_group_name='ops'
        self.assertTrue(self.result().deployable)
    def test_spaces_not_silently_normalized(self):
        self.group.ad_group_name='AAA-Network Admins'; self.blocked('scope.external_mapping_mismatch')
    def test_unsafe_cn_blocked(self):
        self.group.ad_group_name='AAA-ops,OU=admin'; self.blocked('scope.external_cn_unsafe')
    def test_duplicate_cn_known_binding_blocked(self):
        self.inv.identity_groups.append(NS(id='other', name='Ops', authority='EXTERNAL',
            external_source_id=SOURCE, ad_group_name='aaa-OPS'))
        self.blocked('scope.external_mapping_ambiguous')
    def test_explicit_username_collision(self):
        self.inv.users=[NS(id='u1',enabled=True,username='ALICE',auth_source='local'),
            NS(id='u2',enabled=True,username='directory-alice',auth_source='ad',ad_identity='alice')]
        self.blocked('scope.external_username_collision')
    def test_does_not_guess_domain_username_equivalence(self):
        self.inv.users=[NS(id='u1',enabled=True,username='alice',auth_source='local'),
            NS(id='u2',enabled=True,username='directory-alice',auth_source='ad',ad_identity='alice@example.test')]
        self.assertTrue(self.result().deployable)  # Deliberate documented detection limit.
    def test_missing_group_blocks(self):
        self.inv.identity_groups=[]; self.blocked('scope.reference_missing')
    def test_device_and_external_both_retained(self):
        self.policy.condition_device_id='d'; self.inv.devices=[NS(id='d',name='R1',device_group_id=None)]
        self.assertEqual(self.expression(), f'identity-source == {TOKEN} && member == ops && aaa.protocol == tacacs && device == R1')
    def test_partial_loss_invalidates_whole_scope(self):
        self.policy.condition_device_id='gone'; self.blocked('scope.reference_missing')
    def test_positive_tree(self):
        self.tree(); self.assertEqual(self.expression(), f'identity-source == {TOKEN} && member == ops && aaa.protocol == tacacs')
    def test_tree_boolean_structure(self):
        self.tree(logical='OR')
        self.inv.conditions.append(self.h.leaf(referenced_object_id='d'))
        self.inv.devices=[NS(id='d',name='R1',device_group_id=None)]
        self.assertEqual(self.expression(), f'(identity-source == {TOKEN} && member == ops && aaa.protocol == tacacs || device == R1)')
    def test_external_negation_rejected(self):
        self.tree('not_equal'); self.blocked('scope.external_negation_unsupported')
    def test_not_group_rejected(self):
        self.tree(logical='NOT'); self.blocked('scope.unsupported_operator')
    def test_radius_not_certified(self):
        self.blocked('scope.external_protocol_unsupported', protocol='radius')
    def test_legacy_ambiguous_stays_blocked(self):
        self.group.authority='LEGACY'; self.group.external_source_id=None
        self.blocked('scope.identity_membership_unknown')
    def test_legacy_empty_stays_empty(self):
        self.group.authority='LEGACY'; self.group.external_source_id=None; self.group.ad_group_name=None
        self.inv.external_identity_enabled=False; self.blocked('scope.empty_group')
    def test_legacy_shared_members_not_reclassified(self):
        self.group.authority='LEGACY'; self.group.external_source_id=None
        self.inv.users=[NS(id='u',group_id='g',enabled=True,username='alice',auth_source='local')]
        self.assertEqual(self.expression(),'member == ops')
    def test_any_policy_unchanged(self):
        p=self.h.policy(); self.assertEqual(self.result(p).state,self.scope.ScopeState.UNRESTRICTED)
    def test_named_module_and_selector_agree(self):
        self.h.load('app/services/config_compiler.py','_mavis_block')
        self.h.ns['security']=NS(decrypt_secret=lambda x:'temporary-fixture-password')
        block=self.h.call('_mavis_block',self.backend)
        self.assertIn(f'mavis module {TOKEN} = external {{',block)
        self.assertIn('setenv FLAG_USE_MEMBEROF = 1',block)
        self.assertIn('setenv AD_GROUP_PREFIX = "AAA-"',block)
        self.assertIn(TOKEN,self.expression())
    def test_snapshot_records_binding_and_blocks_restore(self):
        snapshot=self.h.call('build_snapshot',self.db(),self.policy)
        self.assertEqual(snapshot['external_scope_bindings'][0]['source_id'],str(SOURCE))
        with self.assertRaises(ValueError): self.h.call('resolve_snapshot_for_restore',self.db(),snapshot)
    def test_tree_snapshot_records_binding(self):
        self.tree(); self.policy.condition_group_id=None
        snapshot=self.h.call('build_snapshot',self.db(),self.policy)
        self.assertEqual(snapshot['external_scope_bindings'][0]['directory_cn'],'AAA-ops')
    def test_old_snapshot_cannot_rebind_external(self):
        with self.assertRaises(ValueError):
            self.h.call('resolve_snapshot_for_restore',self.db(),{'condition_group_name':'ops'})
    def preview(self):
        self.h.routes(); self.h.load('app/api/routes_config.py','get_candidate',True)
        self.h.ns['CandidateOut']=NS
        self.h.load('app/services/config_compiler.py','compute_diff')
        self.h.ns['difflib']=difflib
        self.h.ns['config_compiler'].compute_diff=self.h.ns['compute_diff']
        return self.h.call('get_candidate',self.db(),NS(username='reviewer'))
    def test_changed_candidate_applicable(self):
        r=self.preview(); self.assertTrue(r.applicable); self.assertTrue(r.has_changes)
        self.assertTrue(r.diff); self.assertEqual(r.diagnostics,[])
        self.assertIn(f'identity-source == {TOKEN} && member == ops && aaa.protocol == tacacs',r.candidate)
    def test_blocked_candidate_preserves_apply_boundary(self):
        self.backend.enabled=False; r=self.preview()
        self.assertFalse(r.applicable); self.assertEqual(r.candidate,'')
        with self.assertRaises(HTTPException) as caught:
            self.h.call('apply_config',NS(note=None),self.db(),NS(username='reviewer'))
        self.assertEqual(caught.exception.status_code,409); self.assertEqual(self.h.applied,[])
    def test_unchanged_candidate_not_blocked(self):
        first=self.preview(); self.h.ns['config_compiler'].get_active_config=lambda:first.candidate
        r=self.h.call('get_candidate',self.db(),NS(username='reviewer'))
        self.assertTrue(r.applicable); self.assertFalse(r.has_changes); self.assertEqual(r.diff,'')
    def test_invalid_policy_not_omitted_before_fallback(self):
        self.backend.enabled=False; db=self.db(); db.rows['Policy'].append(self.h.policy(name='fallback'))
        with self.assertRaises(self.h.ns['UncompilablePolicyError']): self.h.call('compile_candidate',db)
    def test_external_override_cannot_bypass_source(self):
        db=self.db()
        db.rows['DeviceAccessGrant']=[self.h.row('DeviceAccessGrant',user_group_id='g')]
        with self.assertRaises(self.h.ns['UncompilablePolicyError']) as caught:
            self.h.call('compile_candidate',db)
        self.assertIn('scope.external_override_unsupported',[d['code'] for d in caught.exception.diagnostics])
    def test_restore_current_external_policy_rejected_before_writes(self):
        self.h.routes();db=self.db()
        version=self.h.row('PolicyVersion',policy_id=self.policy.id,snapshot='{}')
        db.rows['PolicyVersion']=[version]
        with self.assertRaises(HTTPException) as caught:
            self.h.call('restore_policy_version',str(self.policy.id),str(version.id),db,NS(username='reviewer'))
        self.assertEqual(caught.exception.status_code,409);self.assertEqual(db.commits,0)
        self.assertEqual(self.policy.condition_group_id,'g')
    @unittest.skipUnless(shutil.which('node'), 'Node required for actual editor submit handler')
    def test_editor_sends_explicit_source_and_authority(self):
        handler=source('app/templates/groups.html').split("document.getElementById('group-form').addEventListener('submit', async (e) => {",1)[1].split('\n  });',1)[0]
        for authority in ('ad','local'):
            fields={'group-id':'','group-type':authority,'group-external-source':str(SOURCE),
                'group-name':'ops','group-description':'','group-ad-name':'AAA-ops'}
            script="""const fields=FIELDS; const document={getElementById:id=>({value:fields[id]||'',hidden:false})};
const AAAPlatform={authedFetch:async(url,request)=>{process.stdout.write(request.body);return {ok:true}},toast(){}};
function closeModal(){} function loadGroups(){}
(async(e)=>{HANDLER})({preventDefault(){}});""".replace('FIELDS',json.dumps(fields)).replace('HANDLER',handler)
            result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=10,check=True)
            payload=json.loads(result.stdout)
            self.assertEqual(payload['authority'],'EXTERNAL' if authority=='ad' else 'LEGACY')
            self.assertEqual(payload['external_source_id'],str(SOURCE) if authority=='ad' else None)
            self.assertNotIn('binding_status',payload)
    @unittest.skipUnless(shutil.which('node'), 'Node required to execute actual frontend decision function')
    def test_actual_frontend_three_states(self):
        js=source('app/templates/config.html').split('  async function loadCandidate() {',1)[1].split('  async function applyConfig()',1)[0]
        fn='async function loadCandidate() {'+js
        valid=vars(self.preview())
        cases=[(valid,'apply-btn','Configuration blocked'),
               (dict(valid,has_changes=False,diff=''),'Up to date','apply-btn'),
               (dict(valid,applicable=False,diagnostics=[dict(protocol='tacacs',policy_name='R1',reason='broken',path='scope',code='scope.external_source_missing')]),'Configuration blocked','apply-btn')]
        for response,expected,absent in cases:
            script='''const panel={innerHTML:''}; const document={getElementById:id=>id==='candidate-panel'?panel:{addEventListener(){}}};
const AAAPlatform={authedFetch:async()=>({ok:true,status:200,json:async()=>(RESPONSE)})};
const escapeHtml=x=>String(x); const renderDiff=x=>x; function applyConfig(){};
FUNCTION
loadCandidate().then(()=>process.stdout.write(panel.innerHTML));'''.replace('RESPONSE',json.dumps(response)).replace('FUNCTION',fn)
            result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=10,check=True)
            self.assertIn(expected,result.stdout); self.assertNotIn(absent,result.stdout)
