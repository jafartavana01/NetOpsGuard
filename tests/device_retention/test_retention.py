"""Device removal preserves historical content and explicitly removes whole policies."""
import sys
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dependencies'))
from test_deletion import DeletionTests
from app.models.ncm import NcmConfiguration, NcmBaseline, NcmCandidate, NcmBackupJob, NcmBackupJobTarget, NcmDeployment, NcmBackupSchedule
from app.models.policy import Policy
from app.models.radius_policy import RadiusPolicy
from app.models.device import NetworkDevice
from app.models.device_group import DeviceGroup
from app.services import dependency_deletion as service, ncm_lock, ncm_backup
from fastapi import HTTPException

class RetentionTests(DeletionTests):
    def archive(self):
        c=NcmConfiguration(id=uuid.uuid4(),device_id=self.r1.id,device_name='R1',version_number=1,configuration_type='running',configuration_content='hostname R1\nend',sha256='a'*64,size_bytes=15,source='manual')
        self.db.add(c);self.db.flush()
        b=NcmBaseline(id=uuid.uuid4(),device_id=self.r1.id,device_name='R1',configuration_type='running',configuration_id=c.id)
        p=NcmCandidate(id=uuid.uuid4(),display_number=1,device_id=self.r1.id,device_name='R1',title='Saved change',configuration_lines='hostname R1',status='approved')
        self.db.add_all([b,p]);self.db.commit();return c,b,p
    def remove(self, targets=None):
        targets=targets or [self.target()];report=self.preview(targets)
        return service.execute(self.db,targets,'device_delete',report['revision'],'DELETE',self.admin)
    def test_api_policy_permission_and_csrf(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from types import SimpleNamespace
        from app.api.routes_dependencies import router
        from app.api.deps import get_current_admin
        from app.database import get_db
        from app.models.admin_role import AdminRole
        from app import security
        role=AdminRole(id=uuid.uuid4(),name='device-editor',permissions=['devices:view','devices:write','policies:view'])
        self.db.add(role);self.db.commit()
        p=self.policy(condition_device_id=self.r1.id)
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_admin]=lambda:SimpleNamespace(username='operator',is_superadmin=False,role_id=role.id)
        with TestClient(app) as client:
            client.cookies.set(security.CSRF_COOKIE_NAME,'fixture')
            headers={'X-CSRF-Token':'fixture'}
            body=dict(targets=[self.target()],operation='device_delete',revision=self.preview()['revision'],confirmation='DELETE')
            self.assertEqual(client.post('/api/dependencies/execute',headers=headers,json=body).status_code,403)
            app.dependency_overrides[get_current_admin]=lambda:self.admin
            self.assertEqual(client.post('/api/dependencies/execute',json=body).status_code,403)
            self.assertIsNotNone(self.db.get(Policy,p.id))
            result=client.post('/api/dependencies/execute',headers=headers,json=body)
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(len(result.json()['deleted_policies']),1)
    def test_non_device_new_operation_rejected(self):
        targets=[self.target('device_group',self.group)]
        with self.assertRaises(HTTPException) as e:self.remove(targets)
        self.assertEqual(e.exception.status_code,400)
    def test_archives_baselines_candidates_survive(self):
        c,b,p=self.archive();ids=[c.id,b.id,p.id];self.remove();self.db.expire_all()
        self.assertIsNone(self.db.get(NetworkDevice,self.r1.id))
        for model,i in zip((NcmConfiguration,NcmBaseline,NcmCandidate),ids):self.assertEqual(self.db.get(model,i).device_id,self.r1.id)
        self.assertEqual(self.db.get(NcmConfiguration,ids[0]).configuration_content,'hostname R1\nend')
        self.assertEqual(self.db.get(NcmBaseline,ids[1]).configuration_id,ids[0])
    def test_archive_identity_not_name_reused(self):
        c,_,_=self.archive();self.remove()
        other=uuid.uuid4();self.db.execute(NetworkDevice.__table__.insert().values(id=other,name='R1',ip_address='192.0.2.1'));self.db.commit()
        self.assertNotEqual(c.device_id,other)
    def test_retained_archive_remains_readable_and_comparable(self):
        from app.api.routes_ncm import get_configuration, diff_configurations, NcmDiffRequest
        c,_,_=self.archive()
        newer=NcmConfiguration(id=uuid.uuid4(),device_id=self.r1.id,device_name='R1',version_number=2,configuration_type='running',configuration_content='hostname R1-new\nend',sha256='b'*64,size_bytes=19,source='manual')
        self.db.add(newer);self.db.commit();self.remove()
        detail=get_configuration(str(c.id),self.db,self.admin)
        self.assertEqual(detail.configuration_content,'hostname R1\nend')
        diff=diff_configurations(NcmDiffRequest(from_configuration_id=str(c.id),to_configuration_id=str(newer.id)),self.db,self.admin)
        self.assertFalse(diff.identical);self.assertEqual(diff.added,1);self.assertEqual(diff.removed,1)
    def test_missing_candidate_target_cannot_deploy(self):
        from app.services.ncm_deploy import deploy_candidate
        c,b,p=self.archive();self.remove()
        with patch('app.services.ncm_deploy.ssh_provision.apply_aaa_config') as ssh:
            # Inventory is resolved before credentials or transport.
            result=deploy_candidate(self.db,p,actor='reviewer')
        self.assertFalse(result.ok);ssh.assert_not_called()
    def test_direct_tacacs_and_radius_listed_and_deleted(self):
        p=self.policy(condition_device_id=self.r1.id);r=self.policy(RadiusPolicy,condition_device_id=self.r1.id)
        preview=self.preview();self.assertEqual({x['id'] for x in preview['device_policies']},{str(p.id),str(r.id)})
        result=self.remove();self.assertEqual(len(result['deleted_policies']),2)
        self.assertIsNone(self.db.get(Policy,p.id));self.assertIsNone(self.db.get(RadiusPolicy,r.id))
    def test_disabled_direct_policy_not_left_unrestricted(self):
        p=self.policy(condition_device_id=self.r1.id,enabled=False);self.remove();self.assertIsNone(self.db.get(Policy,p.id))
    def test_tree_policy_removed_whole(self):
        p=self.policy();self.tree(p);self.remove();self.assertIsNone(self.db.get(Policy,p.id))
    def test_final_group_members_require_explicit_whole_policy_cleanup(self):
        p=self.policy(condition_device_group_id=self.group.id)
        targets=[self.target(row=self.r1),self.target(row=self.r2)]
        preview=self.preview(targets);self.assertFalse(preview['policies']);self.assertEqual(preview['device_policies'][0]['id'],str(p.id))
        self.remove(targets);self.assertIsNone(self.db.get(Policy,p.id));self.assertIsNotNone(self.db.get(DeviceGroup,self.group.id))
    def test_nonempty_group_policy_survives(self):
        p=self.policy(condition_device_group_id=self.group.id);self.remove();self.assertIsNotNone(self.db.get(Policy,p.id))
    def test_schedule_preserved_never_becomes_all_devices(self):
        s=NcmBackupSchedule(id=uuid.uuid4(),name='Nightly',device_ids=str(self.r1.id));self.db.add(s);self.db.commit();self.remove()
        self.assertEqual(self.db.get(NcmBackupSchedule,s.id).device_ids,str(self.r1.id))
        self.assertEqual(ncm_backup.resolve_target_devices(self.db,[self.r1.id],[]),[])
    def test_terminal_backup_job_and_target_retained(self):
        job=NcmBackupJob(id=uuid.uuid4(),display_number=1,source='manual',status='completed',total_devices=1)
        self.db.add(job);self.db.flush()
        target=NcmBackupJobTarget(id=uuid.uuid4(),job_id=job.id,device_id=self.r1.id,device_name='R1',configuration_type='running',status='success')
        self.db.add(target);self.db.commit();self.remove();self.db.refresh(target)
        self.assertIsNone(target.device_id);self.assertIsNotNone(self.db.get(NcmBackupJob,job.id))
    def test_running_backup_blocks(self):
        with ncm_lock.hold(self.db,'backup-writer'):
            with self.assertRaises(HTTPException) as e:self.remove()
        self.assertEqual(e.exception.status_code,409);self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id))
    def test_running_deployment_blocks(self):
        d=NcmDeployment(id=uuid.uuid4(),display_number=1,device_id=self.r1.id,device_name='R1',status='running')
        self.db.add(d);self.db.commit()
        with self.assertRaises(HTTPException):self.remove()
        self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id))
    def test_rollback_preserves_device_policy_archive(self):
        c,_,_=self.archive();p=self.policy(condition_device_id=self.r1.id)
        def failure(stage):
            if stage=='object_delete':raise RuntimeError('injected')
        with patch.object(service,'_checkpoint',side_effect=failure):
            with self.assertRaises(RuntimeError):self.remove()
        self.assertIsNotNone(self.db.get(NetworkDevice,self.r1.id));self.assertIsNotNone(self.db.get(Policy,p.id));self.assertIsNotNone(self.db.get(NcmConfiguration,c.id))
    def test_stale_preview_cannot_remove_new_policy(self):
        report=self.preview();p=self.policy(condition_device_id=self.r1.id)
        with self.assertRaises(HTTPException):service.execute(self.db,[self.target()],'device_delete',report['revision'],'DELETE',self.admin)
        self.assertIsNotNone(self.db.get(Policy,p.id))

if __name__=='__main__':
    suite=unittest.TestSuite(RetentionTests(n) for n in RetentionTests.__dict__ if n.startswith('test_'))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
