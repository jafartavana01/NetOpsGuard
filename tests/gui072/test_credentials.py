"""Real SQLite/Fernet/API tests; SSH consumers use controlled mocks."""
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app import security
from app.database import get_db
from app.models.audit_schedule_settings import AuditScheduleSettings as Settings
from app.services import device_credentials as credentials
from app.api import deps, routes_device_credentials as api, routes_security, routes_ncm
from app.schemas.security_audit import AuditLiveRequest, AuditScheduleUpdateRequest, BulkAuditRequest
from app.schemas.ncm import NcmBackupRequest

class CredentialsTests(unittest.TestCase):
    def make_engine(self):
        return create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    def setUp(self):
        self.engine=self.make_engine()
        Settings.__table__.create(self.engine)
        self.db=Session(self.engine)
        self.key=patch.object(security,'_fernet',return_value=Fernet(Fernet.generate_key()));self.key.start()
        self.admin=NS(is_superadmin=True,role_id=None,username='operator')
        app=FastAPI();app.include_router(api.router);app.include_router(routes_security.router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[deps.get_current_admin]=lambda:self.admin
        self.client=TestClient(app);self.client.cookies.set(security.CSRF_COOKIE_NAME,'csrf')
        self.headers={'X-CSRF-Token':'csrf'}
    def tearDown(self):
        self.client.close();self.db.close();self.engine.dispose();self.key.stop()
    def status(self):return self.client.get('/api/device-credentials').json()
    def save(self,password='unique-password',revision=None,username='service'):
        return self.client.put('/api/device-credentials',headers=self.headers,json=dict(username=username,password=password,revision=revision or self.status()['revision']))
    def seed(self):
        s=Settings(ssh_username='legacy',ssh_password_encrypted=security.encrypt_secret('old-secret'),enabled=True,daily_run_time='04:30',last_run_status='partial',last_run_summary='Existing history')
        self.db.add(s);self.db.commit();return s
    def test_existing_ciphertext_and_history_preserved(self):
        s=self.seed();original=s.ssh_password_encrypted
        for _ in range(3):self.assertTrue(self.status()['configured'])
        self.db.refresh(s);self.assertEqual(s.ssh_password_encrypted,original);self.assertEqual(s.last_run_summary,'Existing history');self.assertEqual(s.daily_run_time,'04:30');self.assertEqual(self.db.query(Settings).count(),1)
    def test_first_save_encrypts(self):
        self.assertEqual(self.save().status_code,200);s=credentials.get_settings(self.db)
        self.assertNotIn('unique-password',s.ssh_password_encrypted);self.assertEqual(credentials.resolve(self.db),('service','unique-password'))
    def test_blank_retains_exact_ciphertext(self):
        self.save();before=credentials.get_settings(self.db).ssh_password_encrypted
        self.assertEqual(self.save('').status_code,200);self.assertEqual(credentials.get_settings(self.db).ssh_password_encrypted,before)
    def test_null_retains(self):self.save();self.assertEqual(self.save(None).status_code,200);self.assertEqual(credentials.resolve(self.db)[1],'unique-password')
    def test_rotation(self):self.save();self.save('replacement');self.assertEqual(credentials.resolve(self.db)[1],'replacement')
    def test_stale_rotation_rejected(self):
        rev=self.status()['revision'];self.save(revision=rev);r=self.save('lost-update',revision=rev);self.assertEqual(r.status_code,409);self.assertEqual(credentials.resolve(self.db)[1],'unique-password')
    def test_stale_username_does_not_overwrite(self):
        self.save();rev=self.status()['revision'];self.save(None,username='new');self.assertEqual(self.save(None,revision=rev).status_code,409);self.assertEqual(credentials.resolve(self.db)[0],'new')
    def test_first_configuration_requires_password(self):self.assertEqual(self.save('').status_code,400);self.assertFalse(self.status()['configured'])
    def test_get_and_put_secrecy(self):
        r=self.save();s=credentials.get_settings(self.db)
        for text in [r.text,self.client.get('/api/device-credentials').text]:
            self.assertNotIn('unique-password',text);self.assertNotIn(s.ssh_password_encrypted,text)
    def test_validation_does_not_echo_password(self):
        secret='private'*100;r=self.save(secret);self.assertEqual(r.status_code,422);self.assertNotIn(secret,r.text)
    def test_legacy_writer_rejected_without_echo(self):
        self.seed();r=self.client.put('/api/security/schedule',headers=self.headers,json={'enabled':True,'daily_run_time':'01:00','ssh_password':'do-not-echo','ssh_username':'new'})
        self.assertEqual(r.status_code,422);self.assertNotIn('do-not-echo',r.text);self.assertEqual(credentials.resolve(self.db),('legacy','old-secret'))
    def test_schedule_preserves_credentials_and_history(self):
        self.seed();before=credentials.get_settings(self.db).ssh_password_encrypted
        r=self.client.put('/api/security/schedule',headers=self.headers,json={'enabled':False,'daily_run_time':'01:15'})
        self.assertEqual(r.status_code,200,r.text);self.assertEqual(credentials.get_settings(self.db).ssh_password_encrypted,before);self.assertEqual(r.json()['last_run_summary'],'Existing history')
    def test_permission_denied(self):
        self.admin.is_superadmin=False
        self.assertEqual(self.client.get('/api/device-credentials').status_code,403)
        self.assertEqual(self.client.put('/api/device-credentials',headers=self.headers,json={}).status_code,403)
    def test_csrf(self):self.assertEqual(self.client.put('/api/device-credentials',json={}).status_code,403)
    def test_missing_credentials(self):
        with self.assertRaises(HTTPException) as e:credentials.resolve(self.db)
        self.assertIn('Device Credentials',e.exception.detail)
    def test_corrupted_ciphertext(self):
        s=self.seed();s.ssh_password_encrypted='broken';self.db.commit()
        with self.assertRaises(HTTPException) as e:credentials.resolve(self.db)
        self.assertEqual(e.exception.status_code,409)
    def test_live_default_and_explicit_credentials(self):
        self.seed()
        for payload,expected in [(AuditLiveRequest(),('legacy','old-secret')),(AuditLiveRequest(ssh_username='explicit',ssh_password='explicit-secret'),('explicit','explicit-secret'))]:
            with patch.object(routes_security,'_get_device_or_404',return_value=NS(name='R1',ip_address='192.0.2.1')),patch.object(routes_security,'_create_running_audit_row',return_value=NS()),patch('app.services.network_ops_execution.run_commands_on_device',return_value=NS(success=False,command_results=[],message='Denied')) as ssh:
                with self.assertRaises(HTTPException):routes_security.audit_live_device('id',payload,self.db,self.admin)
                self.assertEqual(ssh.call_args.args[1:3],expected)
    def test_live_missing_does_not_create_job(self):
        with patch.object(routes_security,'_get_device_or_404',return_value=NS()),patch.object(routes_security,'_create_running_audit_row') as create:
            with self.assertRaises(HTTPException):routes_security.audit_live_device('id',AuditLiveRequest(),self.db,self.admin)
            create.assert_not_called()
    def test_live_partial_explicit_rejected(self):
        with patch.object(routes_security,'_get_device_or_404',return_value=NS()):
            with self.assertRaises(HTTPException):routes_security.audit_live_device('id',AuditLiveRequest(ssh_username='x'),self.db,self.admin)
    def test_manual_ncm_consumer(self):
        self.seed();out=NS(job_display_number=1,total=1,succeeded=1,failed=0,changed=0,status='completed',failures=[])
        with patch.object(routes_ncm.ncm_backup,'resolve_target_devices',return_value=[NS()]),patch.object(routes_ncm.ncm_backup,'run_backup',return_value=out) as backup:
            routes_ncm.run_backup(NcmBackupRequest(device_ids=[str(uuid.uuid4())]),self.db,self.admin)
            self.assertEqual((backup.call_args.kwargs['ssh_username'],backup.call_args.kwargs['ssh_password']),('legacy','old-secret'))
    def test_bulk_consumer(self):
        self.seed();out=NS(batch_display_number=1,total_devices=1,succeeded=1,failed=0,status='completed',failures=[],summary='Done')
        with patch.object(routes_security,'run_scheduled_audit',return_value=out) as run:
            routes_security.run_bulk_audit(BulkAuditRequest(device_ids=[str(uuid.uuid4())]),self.db,self.admin)
            self.assertEqual(run.call_args.kwargs['ssh_username'],'legacy');self.assertEqual(security.decrypt_secret(run.call_args.kwargs['ssh_password_encrypted']),'old-secret')
    def test_scheduled_consumers(self):
        from app.services import scheduled_audit,ncm_scheduler
        self.seed()
        for module,method in [(scheduled_audit,'run_scheduled_audit'),(ncm_scheduler,'run_due_schedule')]:
            db=MagicMock();db.query.return_value.filter.return_value.all.return_value=[NS(daily_run_time='00:00',last_run_at=None)]
            with patch.object(module,'get_sessionmaker',return_value=lambda:db),patch.object(credentials,'get_settings',return_value=credentials.get_settings(self.db)),patch.object(module,'should_run_now',return_value=True),patch.object(module,method,return_value=NS(status='completed',summary='Done')) as run:
                module._poll_once();self.assertEqual(run.call_args.kwargs['ssh_username'],'legacy')
                kw=run.call_args.kwargs;self.assertEqual(kw.get('ssh_password') or security.decrypt_secret(kw['ssh_password_encrypted']),'old-secret')

    def test_two_sessions_cannot_overwrite_rotation(self):
        self.save();other=Session(self.engine)
        try:
            stale=credentials.get_settings(other);old=credentials.revision(stale)
            self.save('rotated-secret')
            with self.assertRaises(HTTPException) as e:
                credentials.replace(other,username='stale-name',password='lost-secret',expected_revision=old)
            self.assertEqual(e.exception.status_code,409)
            self.db.expire_all();self.assertEqual(credentials.resolve(self.db),('service','rotated-secret'))
        finally:other.close()
    def test_schedule_update_does_not_invalidate_credential_revision(self):
        self.seed();rev=self.status()['revision']
        self.client.put('/api/security/schedule',headers=self.headers,json={'enabled':False,'daily_run_time':'01:15'})
        self.assertEqual(self.save('new',revision=rev).status_code,200)
        self.assertEqual(credentials.get_settings(self.db).daily_run_time,'01:15')
    def test_singleton_repeated_initialization(self):
        for _ in range(4):self.status()
        self.assertEqual(self.db.query(Settings).count(),1)
    def test_credential_fields_not_exposed_to_ncm_viewer(self):
        self.seed();status=routes_ncm.credential_status(self.db,self.admin)
        self.assertEqual(status,{'configured':True})
    def test_live_execution_permission_retained(self):
        self.admin.is_superadmin=False;self.admin.role_id=uuid.uuid4()
        with patch.object(self.db,'query') as query:
            query.return_value.filter.return_value.first.return_value=NS(permissions=['security:view'])
            r=self.client.post('/api/security/devices/'+str(uuid.uuid4())+'/audit/live',json={},headers=self.headers)
            self.assertEqual(r.status_code,403)
    def test_live_validation_never_echoes_explicit_password(self):
        secret='private'*100
        r=self.client.post('/api/security/devices/'+str(uuid.uuid4())+'/audit/live',json={'ssh_username':'x','ssh_password':secret},headers=self.headers)
        self.assertEqual(r.status_code,422);self.assertNotIn(secret,r.text)
    def test_live_csrf_retained(self):
        self.assertEqual(self.client.post('/api/security/devices/'+str(uuid.uuid4())+'/audit/live',json={}).status_code,403)
    def test_page_requires_superadmin(self):
        from app.web import routes_platform
        with patch.object(routes_platform,'current_admin_or_none',return_value=NS(is_superadmin=False)):
            r=routes_platform.device_credentials_page(NS(),'session')
            self.assertEqual(r.status_code,302);self.assertEqual(r.headers['location'],'/dashboard')
    def test_ssh_error_redacts_actual_password(self):
        from app.services import network_ops_execution
        with patch('paramiko.SSHClient') as client:
            client.return_value.connect.side_effect=RuntimeError('failed secret-value')
            r=network_ops_execution.run_commands_on_device('192.0.2.1','u','secret-value',[])
            self.assertNotIn('secret-value',r.message);self.assertFalse(r.success)
    def test_ncm_failure_does_not_log_password(self):
        from app.services import ncm_backup
        with patch.object(ncm_backup.ncm_drivers,'get_driver') as driver:
            driver.return_value.get_configuration.side_effect=RuntimeError('failed secret-value')
            with self.assertLogs(ncm_backup.logger,level='WARNING') as logs:
                r=ncm_backup._retrieve_one(NS(device_id=uuid.uuid4(),device_name='R1',host='192.0.2.1',vendor='Cisco'),'running','u','secret-value')
            self.assertNotIn('secret-value',r['error']);self.assertNotIn('secret-value',str(logs.output))

    def test_run_now_consumes_account_and_preserves_it(self):
        self.seed()
        with patch.object(routes_security,'run_scheduled_audit',return_value=NS(status='completed',summary='Done')) as run:
            result=routes_security.run_schedule_now(self.db,self.admin)
            self.assertEqual(run.call_args.kwargs['ssh_username'],'legacy')
            self.assertEqual(security.decrypt_secret(run.call_args.kwargs['ssh_password_encrypted']),'old-secret')
            self.assertEqual(result.last_run_status,'completed');self.assertEqual(credentials.resolve(self.db),('legacy','old-secret'))
    def test_deploy_and_rollback_use_account_and_redact_failures(self):
        from app.services import ncm_deploy
        settings=self.seed();device=NS(id=uuid.uuid4(),name='R1',ip_address='192.0.2.1')
        pre=NS(id=uuid.uuid4(),configuration_content='hostname R1')
        for rollback in [False,True]:
            db=MagicMock();db.query.return_value.filter.return_value.first.side_effect=[pre,device] if rollback else [device]
            with patch.object(credentials,'get_settings',return_value=settings),patch.object(ncm_deploy,'_next_number',return_value=1),patch.object(ncm_deploy,'_backup_now',return_value=pre),patch.object(ncm_deploy.ssh_provision,'apply_aaa_config',return_value=NS(success=False,message='failed old-secret',command_log=['old-secret'])) as ssh:
                if rollback:
                    result=ncm_deploy.rollback_deployment(db,NS(pre_configuration_id=pre.id,device_id=device.id,status='failed'),actor='operator')
                else:
                    result=ncm_deploy.deploy_candidate(db,NS(id=uuid.uuid4(),device_id=device.id,status=ncm_deploy.STATUS_APPROVED,configuration_lines='hostname R1'),actor='operator')
                self.assertEqual(ssh.call_args.args[1:3],('legacy','old-secret'))
                self.assertFalse(result.ok);self.assertNotIn('old-secret',result.message);self.assertNotIn('old-secret',result.transcript)

if __name__=='__main__':unittest.main(verbosity=2)
