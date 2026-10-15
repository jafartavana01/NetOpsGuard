"""Real SQLite state/claims; one controlled SSH backup, audit work mocked explicitly."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ncm_scheduler'))
import test_integration as fixture
from ssh_fixture import SSHDevice
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
from unittest.mock import patch
from app.models.audit_schedule_settings import AuditScheduleSettings
from app.models.ncm import NcmConfiguration,NcmBackupJob
from app.services import ncm_scheduler,scheduled_audit,network_ops_execution,ncm_lock
from app.api import routes_security,routes_ncm
from app.schemas.security_audit import AuditScheduleUpdateRequest
from app.schemas.ncm import NcmScheduleRequest

class ExecutionTests(unittest.TestCase):
    make_engine=fixture.ScheduledBackupIntegration.make_engine
    setUp=fixture.ScheduledBackupIntegration.setUp
    schedule=fixture.ScheduledBackupIntegration.schedule
    state=fixture.ScheduledBackupIntegration.state
    def test_timezone_schedule_real_ssh_persists_archive_once(self):
        row=self.schedule(daily_run_time='15:30',schedule_timezone='Asia/Tehran')
        with SSHDevice() as device:
            real=network_ops_execution.run_commands_on_device
            def connect(*args,**kw):return real(*args,**kw,port=device.port)
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=connect):
                ncm_scheduler._poll_once(self.now-timedelta(seconds=1))
                self.assertEqual(self.db.query(NcmBackupJob).count(),0)
                ncm_scheduler._poll_once(self.now+timedelta(seconds=1))
                self.assertEqual(self.state(row).status,'completed')
                c=self.db.query(NcmConfiguration).one();self.assertEqual(c.device_id,self.device.id);self.assertIn('hostname R1',c.configuration_content)
                ncm_scheduler._poll_once(self.now+timedelta(minutes=10))
                self.assertEqual(self.db.query(NcmBackupJob).count(),1)
    def test_audit_claim_committed_before_work_and_restart_no_duplicate(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.daily_run_time='15:30';s.schedule_timezone='Asia/Tehran';self.db.commit()
        def work(*args,**kw):
            with self.sessions() as check:
                saved=check.get(AuditScheduleSettings,s.id);self.assertEqual(saved.last_run_status,'running');self.assertIsNotNone(saved.last_slot)
            return NS(status='completed',summary='done')
        with patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions),patch.object(scheduled_audit,'run_scheduled_audit',side_effect=work) as run:
            scheduled_audit._poll_once(self.now);scheduled_audit._poll_once(self.now+timedelta(minutes=1));self.assertEqual(run.call_count,1)
        self.db.expire_all();self.assertEqual(s.last_run_status,'completed')
    def test_audit_missing_credentials_persisted_blocked(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.daily_run_time='12:00';s.ssh_password_encrypted=None;self.db.commit()
        with patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions):scheduled_audit._poll_once(self.now)
        self.db.expire_all();self.assertEqual(s.last_run_status,'blocked');self.assertIsNotNone(s.last_slot)
    def test_audit_crash_consumed_and_reported(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.daily_run_time='12:00';s.last_run_status='running';s.last_slot=self.now;s.last_run_at=self.now;self.db.commit()
        with patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions),patch.object(scheduled_audit,'run_scheduled_audit') as run:
            scheduled_audit._poll_once(self.now+timedelta(minutes=1));run.assert_not_called()
        self.db.expire_all();self.assertEqual(s.last_run_status,'failed')
    def test_audit_busy_worker_does_not_claim(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.daily_run_time='12:00';self.db.commit()
        with ncm_lock.hold(self.db,'security-audit-schedule'),patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions):scheduled_audit._poll_once(self.now)
        self.db.expire_all();self.assertIsNone(s.last_slot)
    def test_audit_error_is_persisted_and_not_replayed(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.daily_run_time='12:00';self.db.commit()
        with patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions),patch.object(scheduled_audit,'run_scheduled_audit',side_effect=RuntimeError('secret')) as run:
            scheduled_audit._poll_once(self.now);scheduled_audit._poll_once(self.now);self.assertEqual(run.call_count,1)
        self.db.expire_all();self.assertEqual(s.last_run_status,'failed');self.assertNotIn('secret',s.last_run_summary)
    def test_audit_edit_omitted_zone_preserves_conversion(self):
        s=self.db.query(AuditScheduleSettings).one();s.schedule_timezone='Asia/Tehran';self.db.commit()
        routes_security.update_schedule_settings(AuditScheduleUpdateRequest(enabled=False,daily_run_time='02:00'),self.db,NS())
        self.assertEqual(s.schedule_timezone,'Asia/Tehran')
    def test_ncm_edit_omitted_zone_preserves_conversion(self):
        s=self.schedule(schedule_timezone='Asia/Tehran')
        payload=NcmScheduleRequest(name=s.name,daily_run_time='02:00',device_ids=[str(self.device.id)])
        routes_ncm.update_schedule(str(s.id),payload,self.db,NS(username='admin'))
        self.assertEqual(s.schedule_timezone,'Asia/Tehran')
    def test_schedule_edit_blocked_during_execution(self):
        s=self.schedule()
        with ncm_lock.hold(self.db,'schedule:'+str(s.id)):
            with self.assertRaises(Exception) as error:routes_ncm.update_schedule(str(s.id),NcmScheduleRequest(name=s.name,daily_run_time='02:00',device_ids=[str(self.device.id)]),self.db,NS(username='admin'))
            self.assertEqual(error.exception.status_code,409)
        self.db.refresh(s);self.assertEqual(s.daily_run_time,'12:00')

    def test_invalid_saved_audit_zone_blocks_and_remains_editable(self):
        s=self.db.query(AuditScheduleSettings).one();s.enabled=True;s.schedule_timezone='bad';self.db.commit()
        with patch.object(scheduled_audit,'get_sessionmaker',return_value=self.sessions),patch.object(scheduled_audit,'run_scheduled_audit') as run:
            scheduled_audit._poll_once(self.now);run.assert_not_called()
        self.db.expire_all();self.assertEqual(s.last_run_status,'blocked')
        out=routes_security.get_schedule_settings(self.db,NS());self.assertEqual(out.schedule_timezone,'bad')
    def test_invalid_saved_ncm_zone_blocks_and_remains_editable(self):
        s=self.schedule(schedule_timezone='bad')
        ncm_scheduler.run_schedule(self.db,s.id,now=self.now)
        self.assertEqual(self.state(s).status,'blocked')
        self.assertEqual(routes_ncm._schedule_out(s,self.db).schedule_timezone,'bad')
