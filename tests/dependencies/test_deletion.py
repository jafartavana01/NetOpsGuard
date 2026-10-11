"""Real SQLite transactions; PostgreSQL-specific guarantees have a separate suite.

Only DDL portability (JSONB and deferred uniqueness) is adapted for SQLite.
Compiler validation, inspection, deletion and rollback use production code.
"""
import importlib
import os
import pkgutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import HTTPException
import app.models
for module in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module('app.models.' + module.name)
from app.database import Base
from app.models.device import NetworkDevice
from app.models.device_group import DeviceGroup
from app.models.group import TacacsGroup
from app.models.user import TacacsUser
from app.models.policy import Policy
from app.models.radius_policy import RadiusPolicy
from app.models.policy_condition import PolicyCondition
from app.models.policy_condition_group import PolicyConditionGroup
from app.models.command_set import CommandSet
from app.models.policy_command_set import PolicyCommandSet
from app.services import dependency_deletion as service

@compiles(JSONB, 'sqlite')
def sqlite_json(element, compiler, **kw):
    return 'JSON'


class DeletionTests(unittest.TestCase):
    def make_engine(self):
        engine = create_engine('sqlite:///' + self.temp.name + '/test.db', connect_args={'timeout':5})
        event.listen(engine, 'connect', lambda con, rec: con.execute('PRAGMA foreign_keys=ON'))
        return engine

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = self.make_engine()
        # SQLite cannot express PostgreSQL DEFERRABLE UNIQUE, not a claim of parity.
        from sqlalchemy import MetaData
        metadata = MetaData()
        for table in Base.metadata.sorted_tables:
            copy = table.to_metadata(metadata)
            for constraint in copy.constraints:
                if self.engine.dialect.name == 'sqlite' and getattr(constraint, 'deferrable', None):
                    constraint.deferrable = None
                    constraint.initially = None
        metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.db.close)
        self.addCleanup(self.engine.dispose)
        self.admin = SimpleNamespace(username='reviewer', is_superadmin=True, role_id=None)
        self.group = DeviceGroup(id=uuid.uuid4(), name='edge')
        self.r1 = NetworkDevice(id=uuid.uuid4(), name='R1', ip_address='192.0.2.1', device_group_id=self.group.id)
        self.r2 = NetworkDevice(id=uuid.uuid4(), name='R2', ip_address='192.0.2.2', device_group_id=self.group.id)
        self.db.add(self.group); self.db.flush()
        # Core insert avoids unrelated licensing environment, not dependency logic.
        for d in (self.r1, self.r2):
            self.db.execute(NetworkDevice.__table__.insert().values(id=d.id, name=d.name, ip_address=d.ip_address, device_group_id=d.device_group_id))
        self.db.commit()

    def policy(self, model=Policy, **kw):
        p = model(id=uuid.uuid4(), name='P' + uuid.uuid4().hex[:6], priority=self.db.query(model).count() + 1, **kw)
        self.db.add(p); self.db.commit()
        return p

    def target(self, kind='device', row=None):
        return {'type': kind, 'id': str((row or self.r1).id)}

    def preview(self, targets=None):
        return service.inspect(self.db, targets or [self.target()])

    def execute(self, targets=None, operation='delete', report=None):
        targets = targets or [self.target()]
        report = report or self.preview(targets)
        return service.execute(self.db, targets, operation, report['revision'], 'DELETE', self.admin)

    def test_direct_legacy_blocks(self):
        p = self.policy(condition_device_id=self.r1.id)
        report = self.preview()
        self.assertEqual(report['policies'][0]['id'], str(p.id))
        with self.assertRaises(HTTPException) as e: self.execute(report=report)
        self.assertEqual(e.exception.status_code, 409)
        self.assertIsNotNone(self.db.get(NetworkDevice, self.r1.id))
        self.assertEqual(self.db.get(Policy, p.id).condition_device_id, self.r1.id)

    def test_group_membership_is_not_direct(self):
        p = self.policy(condition_device_group_id=self.group.id)
        self.assertEqual(self.preview()['policies'], [])
        self.execute()
        self.assertIsNotNone(self.db.get(Policy, p.id))
        self.assertIsNotNone(self.db.get(DeviceGroup, self.group.id))

    def test_final_member_blocks_without_deleting_group_policy(self):
        p = self.policy(condition_device_group_id=self.group.id)
        targets = [self.target(row=self.r1), self.target(row=self.r2)]
        report = self.preview(targets)
        self.assertTrue(any(d['dependency_type'] == 'empty_group' for d in report['dependencies']))
        self.assertFalse(report['policies'])
        with self.assertRaises(HTTPException): self.execute(targets)
        self.assertEqual(self.db.query(NetworkDevice).count(), 2)
        self.assertIsNotNone(self.db.get(Policy, p.id))

    def test_group_direct_blocks_disabled_too(self):
        p = self.policy(enabled=False, condition_device_group_id=self.group.id)
        report = self.preview([self.target('device_group', self.group)])
        self.assertFalse(report['policies'][0]['enabled'])
        self.assertTrue(report['blocked'])

    def test_radius_independent(self):
        p = self.policy(RadiusPolicy, condition_device_id=self.r1.id)
        report = self.preview()
        self.assertEqual(report['policies'][0]['protocol'], 'radius')
        with self.assertRaises(HTTPException): self.execute()
        self.assertIsNotNone(self.db.get(RadiusPolicy, p.id))

    def tree(self, p, kind='device', ref=None):
        root = PolicyConditionGroup(id=uuid.uuid4(), policy_id=p.id, logical_operator='AND')
        self.db.add(root); self.db.flush()
        child = PolicyConditionGroup(id=uuid.uuid4(), policy_id=p.id, parent_group_id=root.id, logical_operator='OR')
        self.db.add(child); self.db.flush()
        leaf = PolicyCondition(id=uuid.uuid4(), group_id=child.id, object_type=kind, operator='equal', value_type='database_id', value='cached', referenced_object_id=ref or self.r1.id)
        self.db.add(leaf); self.db.commit()
        return leaf

    def test_nested_tree_blocks(self):
        p = self.policy(); leaf = self.tree(p)
        report = self.preview()
        self.assertTrue(any(str(leaf.id) in d['reference_location'] for d in report['dependencies']))
        with self.assertRaises(HTTPException): self.execute()

    def test_manual_command_set_blocks(self):
        cs = CommandSet(id=uuid.uuid4(), name='Read'); self.db.add(cs); self.db.commit()
        self.policy(manual_default_command_set_id=cs.id, requires_manual_approval=True)
        self.assertTrue(self.preview([self.target('command_set', cs)])['blocked'])

    def test_association_blocks(self):
        cs = CommandSet(id=uuid.uuid4(), name='Read'); self.db.add(cs); self.db.commit()
        p = self.policy()
        self.db.add(PolicyCommandSet(policy_id=p.id, command_set_id=cs.id)); self.db.commit()
        self.assertTrue(self.preview([self.target('command_set', cs)])['blocked'])

    def test_remove_dependencies_retains_object(self):
        self.policy(condition_device_id=self.r1.id)
        self.policy(condition_device_id=self.r1.id, enabled=False)
        self.execute(operation='cleanup')
        self.assertEqual(self.db.query(Policy).count(), 0)
        self.assertIsNotNone(self.db.get(NetworkDevice, self.r1.id))

    def test_combined_deletes_together(self):
        self.policy(condition_device_id=self.r1.id)
        self.execute(operation='cleanup_delete')
        self.assertEqual(self.db.query(Policy).count(), 0)
        self.assertIsNone(self.db.get(NetworkDevice, self.r1.id))

    def test_confirmation_required(self):
        with self.assertRaises(HTTPException):
            service.execute(self.db, [self.target()], 'delete', self.preview()['revision'], '', self.admin)
        self.assertIsNotNone(self.db.get(NetworkDevice, self.r1.id))

    def test_all_failures_rollback(self):
        p = self.policy(condition_device_id=self.r1.id)
        pid = p.id
        for stage in ('policy_delete', 'object_delete', 'validation', 'audit', 'commit'):
            report = self.preview()
            with self.subTest(stage=stage), patch.object(service, '_checkpoint', side_effect=lambda name: (_ for _ in ()).throw(RuntimeError('injected')) if name == stage else None):
                with self.assertRaises(RuntimeError): self.execute(operation='cleanup_delete', report=report)
            self.assertIsNotNone(self.db.get(NetworkDevice, self.r1.id))
            self.assertIsNotNone(self.db.get(Policy, pid))

    def test_actual_commit_failure_rolls_back(self):
        self.policy(condition_device_id=self.r1.id)
        report = self.preview()
        with patch.object(self.db, 'commit', side_effect=RuntimeError('commit failed')):
            with self.assertRaises(RuntimeError): self.execute(operation='cleanup_delete', report=report)
        self.assertEqual(self.db.query(Policy).count(), 1)
        self.assertEqual(self.db.query(NetworkDevice).count(), 2)

    def test_stale_preview_rejected(self):
        report = self.preview()
        self.policy(condition_device_id=self.r1.id)
        with self.assertRaises(HTTPException) as e: self.execute(report=report)
        self.assertEqual(e.exception.detail['code'], 'dependency.stale')
        self.assertIsNotNone(self.db.get(NetworkDevice, self.r1.id))

    def test_bulk_safe(self):
        self.execute([self.target(row=self.r1), self.target(row=self.r2)])
        self.assertEqual(self.db.query(NetworkDevice).count(), 0)

    def test_bulk_one_blocker_rolls_back_all(self):
        self.policy(condition_device_id=self.r2.id)
        with self.assertRaises(HTTPException): self.execute([self.target(row=self.r1), self.target(row=self.r2)])
        self.assertEqual(self.db.query(NetworkDevice).count(), 2)

    def test_unrestricted_unchanged(self):
        p = self.policy()
        self.execute()
        self.assertIsNone(self.db.get(Policy, p.id).condition_device_id)

    def test_repair_missing_tree_reference(self):
        p = self.policy(); leaf = self.tree(p, ref=uuid.uuid4())
        pid, lid = p.id, leaf.id
        report = service.orphans(self.db)
        self.assertEqual(report[0]['missing'][0]['condition_id'], str(lid))
        service.repair(self.db, str(pid), report[0]['revision'], [{'condition_id': str(lid), 'replacement_id': str(self.r1.id)}], self.admin)
        leaves = self.db.query(PolicyCondition).all()
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0].referenced_object_id, self.r1.id)

    def test_invalid_repair_preserves_tree(self):
        p = self.policy(); leaf = self.tree(p, ref=uuid.uuid4()); old = leaf.referenced_object_id
        report = service.orphans(self.db)
        with self.assertRaises(HTTPException): service.repair(self.db, str(p.id), report[0]['revision'], [{'condition_id': str(leaf.id), 'replacement_id': str(uuid.uuid4())}], self.admin)
        self.assertEqual(self.db.get(PolicyCondition, leaf.id).referenced_object_id, old)

    def test_stale_policy_change_invalidates_cleanup(self):
        p = self.policy(condition_device_id=self.r1.id)
        report = self.preview()
        p.default_action = 'permit'; self.db.commit()
        with self.assertRaises(HTTPException): self.execute(operation='cleanup_delete', report=report)
        self.assertEqual(self.db.get(Policy, p.id).default_action, 'permit')

    def test_stale_tree_only_change_prevents_individual_policy_delete(self):
        p=self.policy();leaf=self.tree(p)
        targets=[self.target('policy',p)];report=self.preview(targets)
        leaf.referenced_object_id=self.r2.id;self.db.commit()
        with self.assertRaises(HTTPException) as error:self.execute(targets,report=report)
        self.assertEqual(error.exception.detail['code'],'dependency.stale')
        self.assertIsNotNone(self.db.get(Policy,p.id))

    def test_identity_group_and_user_membership_distinct(self):
        group = TacacsGroup(id=uuid.uuid4(), name='ops')
        self.db.add(group); self.db.flush()
        u1 = TacacsUser(id=uuid.uuid4(), username='u1', group_id=group.id, password_hash='fixture')
        u2 = TacacsUser(id=uuid.uuid4(), username='u2', group_id=group.id, password_hash='fixture')
        self.db.add_all([u1,u2]); self.db.commit()
        p = self.policy(condition_group_id=group.id)
        self.assertTrue(self.preview([self.target('user_group',group)])['blocked'])
        self.assertFalse(self.preview([self.target('user',u1)])['policies'])
        self.execute([self.target('user',u1)])
        self.assertIsNotNone(self.db.get(Policy,p.id))
        with self.assertRaises(HTTPException): self.execute([self.target('user',u2)])

    def test_direct_user_tree_blocks(self):
        u = TacacsUser(id=uuid.uuid4(), username='u1', password_hash='fixture')
        self.db.add(u); self.db.commit()
        p=self.policy(enabled=False); self.tree(p,kind='user',ref=u.id)
        self.assertTrue(self.preview([self.target('user',u)])['blocked'])

    def test_nonpolicy_grant_not_automatically_deleted(self):
        from app.models.device_access_grant import DeviceAccessGrant
        group = TacacsGroup(id=uuid.uuid4(),name='ops');self.db.add(group);self.db.commit()
        grant = DeviceAccessGrant(device_id=self.r1.id,user_group_id=group.id)
        self.db.add(grant);self.db.commit()
        self.policy(condition_device_id=self.r1.id)
        with self.assertRaises(HTTPException): self.execute(operation='cleanup_delete')
        self.assertEqual(self.db.query(Policy).count(),1)
        self.assertEqual(self.db.query(DeviceAccessGrant).count(),1)

    def test_category_is_metadata_not_authorization(self):
        from app.models.command_category import CommandCategory
        from app.models.command_rule import CommandRule
        category=CommandCategory(id=uuid.uuid4(),name='show');cs=CommandSet(id=uuid.uuid4(),name='read')
        self.db.add_all([category,cs]);self.db.flush()
        rule=CommandRule(id=uuid.uuid4(),command_set_id=cs.id,category_id=category.id,command_pattern='show',action='permit')
        self.db.add(rule);self.db.commit();rid=rule.id
        self.assertFalse(self.preview([self.target('command_category',category)])['blocked'])
        self.execute([self.target('command_category',category)])
        self.assertEqual(self.db.get(CommandRule,rid).command_pattern,'show')
        self.assertIsNone(self.db.get(CommandRule,rid).category_id)

    def test_ncm_serialized_schedule_blocks(self):
        from app.models.ncm import NcmBackupSchedule
        schedule=NcmBackupSchedule(id=uuid.uuid4(),name='Nightly',device_ids=str(self.r1.id))
        self.db.add(schedule);self.db.commit()
        self.assertTrue(any(d['referencing_type']=='ncm_schedule' for d in self.preview()['dependencies']))
        with self.assertRaises(HTTPException): self.execute()

    def test_direct_api_and_rbac_csrf(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes_dependencies import router
        from app.api.routes_devices import router as devices
        from app.api.deps import get_current_admin
        from app.database import get_db
        from app.models.admin_role import AdminRole
        from app import security
        app=FastAPI();app.include_router(router);app.include_router(devices)
        role=AdminRole(id=uuid.uuid4(),name='viewer',permissions=['devices:view','policies:view'])
        self.db.add(role);self.db.commit()
        viewer=SimpleNamespace(username='viewer',is_superadmin=False,role_id=role.id)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_admin]=lambda:viewer
        client=TestClient(app);client.cookies.set(security.CSRF_COOKIE_NAME,'fixture')
        headers={'X-CSRF-Token':'fixture'}
        body={'targets':[self.target()]}
        self.assertEqual(client.post('/api/dependencies/inspect',json=body).status_code,403)
        response=client.post('/api/dependencies/inspect',json=body,headers=headers)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.json()['can_delete'])
        body.update(operation='cleanup_delete',revision=response.json()['revision'],confirmation='DELETE')
        self.assertEqual(client.post('/api/dependencies/execute',json=body,headers=headers).status_code,403)
        self.assertEqual(client.delete('/api/devices/'+str(self.r1.id),headers=headers).status_code,403)
        app.dependency_overrides[get_current_admin]=lambda:self.admin
        self.policy(condition_device_id=self.r1.id)
        self.assertEqual(client.delete('/api/devices/'+str(self.r1.id),headers=headers).status_code,409)
        self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id))

    def test_repair_history_failure_rolls_back(self):
        p=self.policy();leaf=self.tree(p,ref=uuid.uuid4());old=leaf.referenced_object_id
        report=service.orphans(self.db)[0]
        with patch.object(service.policy_versioning,'record_version',side_effect=RuntimeError('history failed')):
            with self.assertRaises(RuntimeError): service.repair(self.db,str(p.id),report['revision'],[{'condition_id':str(leaf.id),'replacement_id':str(self.r1.id)}],self.admin)
        self.assertEqual(self.db.get(PolicyCondition,leaf.id).referenced_object_id,old)

    def test_committed_audit_is_in_transaction(self):
        from app.models.dependency_audit import DependencyAudit
        report=self.preview()
        with patch.object(self.db,'commit',side_effect=RuntimeError('commit failed')):
            with self.assertRaises(RuntimeError):self.execute(report=report)
        self.assertEqual(self.db.query(DependencyAudit).count(),0)
        self.execute()
        row=self.db.query(DependencyAudit).one()
        self.assertEqual(row.actor,'reviewer')
        self.assertNotIn('password',row.details)

    def test_concurrent_tree_writer_finishes_before_delete_rechecks(self):
        import threading
        from app.services.reference_lock import guard
        ready=threading.Event();release=threading.Event();finished=threading.Event();failures=[]
        report=self.preview();self.db.rollback()
        pid=uuid.uuid4();gid=uuid.uuid4();did=self.r1.id;self.db.rollback()
        def writer():
            try:
                with Session(self.engine) as db:
                    guard(db)
                    self.assertIsNotNone(db.get(NetworkDevice,did))
                    ready.set();self.assertTrue(release.wait(4))
                    db.add(Policy(id=pid,name='concurrent',priority=44));db.flush()
                    db.add(PolicyConditionGroup(id=gid,policy_id=pid,logical_operator='AND'));db.flush()
                    db.add(PolicyCondition(group_id=gid,object_type='device',operator='equal',value_type='database_id',value='R1',referenced_object_id=did));db.commit()
            except BaseException as e:failures.append(e);ready.set()
        def deleter():
            try:
                with Session(self.engine,autoflush=False) as db:
                    with self.assertRaises(HTTPException) as e:
                        service.execute(db,[{'type':'device','id':str(did)}],'delete',report['revision'],'DELETE',self.admin)
                    self.assertEqual(e.exception.detail['code'],'dependency.stale')
            except BaseException as e:failures.append(e)
            finally:finished.set()
        one=threading.Thread(target=writer);two=threading.Thread(target=deleter)
        one.start();self.assertTrue(ready.wait(4));two.start()
        self.assertFalse(finished.wait(.15),'Deletion must wait for the reference writer transaction')
        release.set();one.join(6);two.join(6)
        self.assertFalse(one.is_alive() or two.is_alive())
        if failures:raise failures[0]
        self.assertIsNotNone(self.db.get(NetworkDevice,did))
        self.assertIsNotNone(self.db.get(Policy,pid))

    def test_writer_after_delete_cannot_validate_deleted_object(self):
        from app.services.reference_lock import guard
        did=self.r1.id
        self.execute()
        self.db.rollback()
        with Session(self.engine) as writer:
            guard(writer)
            self.assertIsNone(writer.get(NetworkDevice,did))

    def test_external_membership_not_reinterpreted_as_local_empty(self):
        from app.models.ad_settings import AdSettings
        source=AdSettings(id=uuid.uuid4(),enabled=True,host='ad.example.test',port=636,use_tls=True,
            use_memberof=True,bind_dn='reader@example.test',bind_password_encrypted='structural-fixture',
            search_base='DC=example,DC=test',group_prefix='AAA-')
        self.db.add(source);self.db.flush()
        group=TacacsGroup(id=uuid.uuid4(),name='ops',authority='EXTERNAL',external_source_id=source.id,ad_group_name='AAA-ops')
        self.db.add(group);self.db.flush()
        user=TacacsUser(id=uuid.uuid4(),username='directory_operator',auth_source='ad',group_id=group.id)
        self.db.add(user);self.db.commit()
        p=self.policy(condition_group_id=group.id)
        inventory=service.config_compiler._scope_inventory(self.db)
        self.assertTrue(service.policy_scope.resolve_scope(p,'tacacs',inventory).deployable)
        report=self.preview([self.target('user',user)])
        self.assertEqual(report['policies'],[])
        self.assertFalse(any(d['dependency_type']=='empty_group' for d in report['dependencies']))

    def test_explicit_orphan_policy_delete_leaves_fallback_only_after_confirmation(self):
        p=self.policy();self.tree(p,ref=uuid.uuid4())
        fallback=self.policy(default_action='permit')
        with self.assertRaises(service.config_compiler.UncompilablePolicyError):service.config_compiler.compile_candidate(self.db)
        targets=[self.target('policy',p)]
        result=self.execute(targets)
        self.assertTrue(result['candidate']['applicable'])
        self.assertFalse(result['deployed_configuration_changed'])
        self.assertIsNotNone(self.db.get(Policy,fallback.id))
        self.assertIn('may change effective',result['warning'])

    def test_multiple_policy_cleanup_failure_restores_every_policy(self):
        self.policy(condition_device_id=self.r1.id);self.policy(condition_device_id=self.r1.id)
        count=0
        def fail_second(stage):
            nonlocal count
            if stage=='policy_delete':
                count+=1
                if count==2:raise RuntimeError('second deletion failed')
        with patch.object(service,'_checkpoint',side_effect=fail_second):
            with self.assertRaises(RuntimeError):self.execute(operation='cleanup_delete')
        self.assertEqual(self.db.query(Policy).count(),2)
        self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id))

    def test_new_candidate_error_rolls_back_without_apply(self):
        failure=service.config_compiler.UncompilablePolicyError('invalid',[{'code':'injected.new.invalid_scope'}])
        with patch.object(service.config_compiler,'compile_candidate',side_effect=['valid',failure]), patch.object(service.config_compiler,'apply_candidate',side_effect=AssertionError('Apply must never be called')):
            with self.assertRaises(HTTPException):self.execute()
        self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id))

if __name__ == '__main__':
    unittest.main(verbosity=2)
