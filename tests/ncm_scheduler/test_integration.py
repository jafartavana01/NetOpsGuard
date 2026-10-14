"""Actual SQLite, scheduler, backup and archive pipeline; controlled real SSH."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import importlib
import pkgutil
import tempfile
import subprocess
import os
import uuid
import asyncio
import unittest
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace as NS
from unittest.mock import patch
from cryptography.fernet import Fernet
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from app import models,security
from app.database import Base
for item in pkgutil.iter_modules(models.__path__):importlib.import_module('app.models.'+item.name)
from app.models.device import NetworkDevice
from app.models.device_group import DeviceGroup
from app.models.audit_schedule_settings import AuditScheduleSettings
from app.models.ncm import NcmBackupSchedule,NcmBackupJob,NcmBackupJobTarget,NcmConfiguration,NcmScheduleState
from app.services import ncm_scheduler as scheduler,network_ops_execution,ncm_lock
from ssh_fixture import SSHDevice

class ScheduledBackupIntegration(unittest.TestCase):
    def make_engine(self):
        return create_engine("sqlite:///"+self.temp.name+"/test.sqlite")
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.engine=self.make_engine()
        @event.listens_for(self.engine,'connect')
        def foreign_keys(connection,record):
            if self.engine.dialect.name=='sqlite':connection.execute('PRAGMA foreign_keys=ON')
        Base.metadata.create_all(self.engine,tables=[t for t in Base.metadata.sorted_tables if t.name.startswith("ncm_") or t.name in ("network_devices","device_groups","audit_schedule_settings")]);self.sessions=sessionmaker(self.engine,autoflush=False,expire_on_commit=True);self.db=self.sessions()
        self.addCleanup(self.engine.dispose);self.addCleanup(self.db.close)
        self.key=Fernet.generate_key()
        self.fernet=patch.object(security,'_fernet',return_value=Fernet(self.key));self.fernet.start();self.addCleanup(self.fernet.stop)
        self.now=datetime(2026,10,14,12,0,tzinfo=timezone.utc)
        self.device=NetworkDevice(name='R1',ip_address='127.0.0.1',vendor='Cisco',enabled=True)
        self.db.add(self.device);self.db.add(AuditScheduleSettings(ssh_username='backup',ssh_password_encrypted=security.encrypt_secret('test-password')));self.db.commit()
        self.clock=patch.object(scheduler,'get_sessionmaker',return_value=self.sessions);self.clock.start();self.addCleanup(self.clock.stop)
    def schedule(self,**kw):
        values=dict(name='daily',device_ids=str(self.device.id),device_group_ids='',daily_run_time='12:00',configuration_types='running',created_at=self.now-timedelta(minutes=1))
        values.update(kw);row=NcmBackupSchedule(**values);self.db.add(row);self.db.commit();return row
    def state(self,row):self.db.expire_all();return self.db.get(NcmScheduleState,row.id)
    def test_due_real_ssh_job_archive_and_second_poll(self):
        row=self.schedule(configuration_types='running,startup')
        with SSHDevice() as device:
            real=network_ops_execution.run_commands_on_device
            def connect(*args,**kwargs):return real(*args,**kwargs,port=device.port)
            # Only redirect the fixture port; real SSH, driver and persistence execute.
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=connect):
                scheduler._poll_once(self.now-timedelta(seconds=1));self.assertEqual(self.db.query(NcmBackupJob).count(),0)
                scheduler._poll_once(self.now+timedelta(seconds=1))
                state=self.state(row);self.assertEqual(state.status,'completed',state.error)
                self.assertEqual(self.db.query(NcmBackupJob).count(),1)
                configs=self.db.query(NcmConfiguration).all();self.assertEqual(len(configs),2)
                for config in configs:
                    self.assertEqual(config.device_id,self.device.id);self.assertEqual(config.job_id,state.job_id);self.assertIn('hostname R1',config.configuration_content)
                targets=self.db.query(NcmBackupJobTarget).all();self.assertEqual(len(targets),2);self.assertTrue(all(t.connection_ok and t.retrieval_ok and t.configuration_id for t in targets))
                self.assertIn('show running-config',device.commands);self.assertIn('show startup-config',device.commands)
                scheduler._poll_once(self.now+timedelta(minutes=3));self.assertEqual(self.db.query(NcmBackupJob).count(),1);self.assertEqual(len(device.connections),2)
    def test_missing_credentials_visible_and_not_retried(self):
        row=self.schedule();self.db.query(AuditScheduleSettings).delete();self.db.commit()
        scheduler._poll_once(self.now);state=self.state(row);self.assertEqual(state.status,'blocked');self.assertIn('Device Credentials',state.error)
        scheduler._poll_once(self.now+timedelta(minutes=1));self.assertEqual(self.db.query(NcmBackupJob).count(),1)
    def test_empty_targets_not_success(self):
        row=self.schedule(device_ids='');scheduler._poll_once(self.now);self.assertEqual(self.state(row).status,'blocked')
    def test_disabled_never_runs(self):
        self.schedule(enabled=False);scheduler._poll_once(self.now);self.assertEqual(self.db.query(NcmBackupJob).count(),0)
    def test_bad_time_does_not_stop_other_schedule(self):
        bad=self.schedule(name='bad',daily_run_time='25:00');good=self.schedule(name='good',device_ids='')
        scheduler._poll_once(self.now);self.assertEqual(self.state(bad).status,'blocked');self.assertEqual(self.state(good).status,'blocked');self.assertEqual(self.db.query(NcmBackupJob).count(),2)
    def test_midnight_catchup(self):
        row=self.schedule(daily_run_time='23:59',created_at=self.now-timedelta(days=1),device_ids='')
        scheduler._poll_once(self.now.replace(hour=0,minute=1));self.assertIsNotNone(self.state(row).attempted_at)
    def test_new_future_schedule_does_not_backfill(self):
        row=self.schedule(daily_run_time='13:00');scheduler._poll_once(self.now);self.assertIsNone(self.state(row))
    def test_lock_blocks_second_session_and_edit(self):
        row=self.schedule()
        with ncm_lock.hold(self.db,'schedule:'+str(row.id)):
            with self.sessions() as other:
                with self.assertRaises(ncm_lock.Busy):scheduler.run_schedule(other,row.id,now=self.now)
        scheduler._poll_once(self.now-timedelta(seconds=1));self.assertEqual(self.db.query(NcmBackupJob).count(),0)
    def test_naive_utc_and_offsets(self):
        self.assertFalse(scheduler.should_run_now('12:00',self.now.replace(tzinfo=None),self.now+timedelta(hours=1)))
        self.assertFalse(scheduler.should_run_now('25:00',None,self.now))
        self.assertEqual(scheduler.due_slot('12:00',self.now),scheduler.due_slot('12:00',self.now.astimezone(timezone(timedelta(hours=3,minutes=30)))))


    def test_group_dedup_and_disabled_devices(self):
        from app.services.ncm_backup import resolve_target_devices
        group=DeviceGroup(name='edge');self.db.add(group);self.db.flush()
        self.device.device_group_id=group.id
        disabled=NetworkDevice(name='off',ip_address='192.0.2.2',enabled=False,device_group_id=group.id)
        self.db.add(disabled);self.db.commit()
        targets=resolve_target_devices(self.db,[self.device.id,disabled.id],[group.id])
        self.assertEqual([d.id for d in targets],[self.device.id])
        self.assertEqual(resolve_target_devices(self.db,[],[uuid.uuid4()]),[])

    def test_real_ssh_auth_failure_persisted(self):
        row=self.schedule()
        settings=self.db.query(AuditScheduleSettings).one();settings.ssh_password_encrypted=security.encrypt_secret('wrong-secret');self.db.commit()
        with SSHDevice() as device:
            real=network_ops_execution.run_commands_on_device
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=lambda *a,**k:real(*a,**k,port=device.port)):
                scheduler._poll_once(self.now)
        state=self.state(row);self.assertEqual(state.status,'failed');self.assertEqual(state.failed,1)
        target=self.db.query(NcmBackupJobTarget).one();self.assertEqual(target.status,'failed');self.assertNotIn('wrong-secret',target.error_message)
        self.assertEqual(self.db.query(NcmConfiguration).count(),0)

    def test_timeout_is_visible(self):
        from app.services import ncm_drivers
        row=self.schedule()
        with patch.object(ncm_drivers,'get_driver',return_value=NS(get_configuration=lambda *a: (_ for _ in ()).throw(TimeoutError('timed out test-password')))):
            scheduler._poll_once(self.now)
        self.assertEqual(self.state(row).status,'failed')
        target=self.db.query(NcmBackupJobTarget).one();self.assertIn('timed out',target.error_message);self.assertNotIn('test-password',target.error_message)

    def test_failed_schedule_does_not_stop_real_ssh_schedule(self):
        bad=self.schedule(name='bad',device_ids='not-a-uuid');good=self.schedule(name='good')
        with SSHDevice() as device:
            real=network_ops_execution.run_commands_on_device
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=lambda *a,**k:real(*a,**k,port=device.port)):
                scheduler._poll_once(self.now)
        self.assertEqual(self.state(bad).status,'failed');self.assertEqual(self.state(good).status,'completed')
        self.assertEqual(self.db.query(NcmBackupJob).count(),2);self.assertEqual(self.db.query(NcmConfiguration).count(),1)

    def test_busy_writer_defers_without_consuming_occurrence(self):
        row=self.schedule(device_ids='')
        with ncm_lock.hold(self.db,'backup-writer'):
            scheduler._poll_once(self.now)
        self.assertIsNone(self.state(row));self.assertEqual(self.db.query(NcmBackupJob).count(),0)
        scheduler._poll_once(self.now);self.assertEqual(self.state(row).status,'blocked')

    def test_restart_recovers_interrupted_job_without_replay(self):
        row=self.schedule();job=NcmBackupJob(display_number=1,source='scheduled',status='running',schedule_id=row.id,total_devices=1)
        self.db.add(job);self.db.flush();self.db.add(NcmScheduleState(schedule_id=row.id,last_slot=self.now,status='running',attempted_at=self.now,job_id=job.id,total=1))
        self.db.commit()
        scheduler._poll_once(self.now+timedelta(minutes=1));state=self.state(row)
        self.assertEqual(state.status,'failed');self.assertIn('interrupted',state.error);self.assertEqual(self.db.query(NcmBackupJob).count(),1)
        self.assertEqual(self.db.get(NcmBackupJob,job.id).status,'failed')

    def test_restart_recovers_completed_job(self):
        row=self.schedule();job=NcmBackupJob(display_number=1,source='scheduled',status='completed',schedule_id=row.id,total_devices=1,succeeded=1,completed_at=self.now)
        self.db.add(job);self.db.flush();self.db.add(NcmScheduleState(schedule_id=row.id,last_slot=self.now,status='running',job_id=job.id));self.db.commit()
        scheduler._poll_once(self.now+timedelta(minutes=1));state=self.state(row)
        self.assertEqual(state.status,'completed');self.assertEqual(state.succeeded,1);self.assertIsNotNone(state.succeeded_at)
        self.assertEqual(self.db.query(NcmBackupJob).count(),1)

    def test_process_death_releases_lock(self):
        if self.engine.dialect.name!='sqlite':self.skipTest('SQLite process lock; PostgreSQL sessions tested separately')
        row=self.schedule(device_ids='')
        code="from sqlalchemy import create_engine; from sqlalchemy.orm import Session; from app.services.ncm_lock import hold; import sys,time; db=Session(create_engine(sys.argv[1])); lock=hold(db,sys.argv[2]); lock.__enter__(); print('locked',flush=True); time.sleep(30)"
        process=subprocess.Popen([sys.executable,'-c',code,str(self.engine.url),'schedule:'+str(row.id)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(),'locked')
            scheduler._poll_once(self.now);self.assertEqual(self.db.query(NcmBackupJob).count(),0)
        finally:
            process.kill();process.wait(timeout=5);process.stdout.close()
        scheduler._poll_once(self.now);self.assertEqual(self.state(row).status,'blocked')
        scheduler._poll_once(self.now);self.assertEqual(self.db.query(NcmBackupJob).count(),1)

    def test_last_attempt_and_next_due_are_persisted(self):
        from app.api.routes_ncm import _schedule_out
        row=self.schedule(device_ids='');scheduler._poll_once(self.now)
        self.db.expire_all();out=_schedule_out(self.db.get(NcmBackupSchedule,row.id),self.db)
        self.assertEqual(out.execution_status,'blocked');self.assertIsNotNone(out.last_attempted_at);self.assertIsNotNone(out.last_job_id)
        self.assertEqual(scheduler.next_due(row,self.state(row),self.now),self.now+timedelta(days=1))
        row.enabled=False;self.db.commit();self.assertIsNone(scheduler.next_due(row,self.state(row),self.now))

    def test_manual_disabled_busy_and_edit_protection(self):
        from fastapi import HTTPException
        from app.api.routes_ncm import update_schedule,delete_schedule,run_schedule_now
        from app.schemas.ncm import NcmScheduleRequest
        row=self.schedule(enabled=False)
        with self.assertRaises(HTTPException) as caught:scheduler.run_schedule(self.db,row.id,now=self.now,manual=True)
        self.assertEqual(caught.exception.status_code,409)
        row.enabled=True;self.db.commit()
        with ncm_lock.hold(self.db,'schedule:'+str(row.id)):
            for action in [lambda:update_schedule(str(row.id),NcmScheduleRequest(name='changed',daily_run_time='12:00',device_ids=[str(self.device.id)]),self.db,NS(username='admin')),
                           lambda:delete_schedule(str(row.id),self.db,NS(username='admin')),
                           lambda:run_schedule_now(str(row.id),self.db,NS(username='admin'))]:
                with self.assertRaises(HTTPException) as caught:action()
                self.assertEqual(caught.exception.status_code,409)
        self.db.expire_all();self.assertEqual(self.db.get(NcmBackupSchedule,row.id).name,'daily')

    def test_loop_continues_after_poll_exception(self):
        async def exercise():
            calls=[]
            def poll():
                calls.append(1)
                if len(calls)==1:raise RuntimeError('database unavailable')
            async def sleep(_):
                if len(calls)==2:raise asyncio.CancelledError()
            with patch.object(scheduler,'_poll_once',side_effect=poll),patch.object(scheduler.asyncio,'sleep',side_effect=sleep):
                with self.assertRaises(asyncio.CancelledError):await scheduler.scheduler_loop()
            self.assertEqual(len(calls),2)
        asyncio.run(exercise())

    def test_retention_preserves_latest_baseline_rollback_and_other_jobs(self):
        from app.services import ncm_archive,ncm_retention
        from app.models.ncm import NcmBaseline,NcmDeployment
        row=self.schedule(retention_days=7)
        job=NcmBackupJob(display_number=1,source='scheduled',status='completed',schedule_id=row.id);self.db.add(job);self.db.flush()
        snapshots=[]
        for i in range(5):
            result=ncm_archive.archive_configuration(self.db,device_id=self.device.id,device_name='R1',configuration_type='running',content='hostname R1\n! v'+str(i),source='scheduled',created_by=None,job_id=job.id)
            result.configuration.created_at=self.now-timedelta(days=20);snapshots.append(result.configuration)
        self.db.add(NcmBaseline(device_id=self.device.id,device_name='R1',configuration_type='running',configuration_id=snapshots[0].id,version_number=1,sha256=snapshots[0].sha256))
        self.db.add(NcmDeployment(display_number=1,device_id=self.device.id,device_name='R1',status='failed',pre_configuration_id=snapshots[1].id))
        self.db.add(NcmBackupJobTarget(job_id=job.id,device_id=self.device.id,device_name='R1',configuration_type='running',configuration_id=snapshots[2].id,status='success'))
        snapshots[3].job_id=None
        self.db.commit();removed=snapshots[2].id
        with ncm_lock.hold(self.db,'backup-writer'):ncm_retention.prune(self.db,row,self.now)
        self.db.expire_all();self.assertIsNone(self.db.get(NcmConfiguration,removed));self.assertEqual(self.db.query(NcmConfiguration).count(),4)
        self.assertIsNone(self.db.query(NcmBackupJobTarget).one().configuration_id)


    def test_real_ssh_incomplete_output_not_archived(self):
        row=self.schedule()
        with SSHDevice(incomplete=True) as device:
            real=network_ops_execution.run_commands_on_device
            def connect(*a,**k):
                k['command_timeout_seconds']=1
                return real(*a,**k,port=device.port)
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=connect):scheduler._poll_once(self.now)
        self.assertEqual(self.state(row).status,'failed')
        self.assertEqual(self.db.query(NcmConfiguration).count(),0)
        self.assertIn('timed out',self.db.query(NcmBackupJobTarget).one().error_message)

    def test_partial_results_and_last_success_preserved(self):
        from app.services import ncm_drivers
        from app.services.ncm_drivers import ConfigRetrievalResult
        row=self.schedule(configuration_types='running,startup')
        self.db.add(NcmScheduleState(schedule_id=row.id,status='completed',last_slot=self.now-timedelta(days=1),succeeded_at=self.now-timedelta(days=1)));self.db.commit()
        def retrieve(host,user,password,kind):
            return ConfigRetrievalResult(ok=kind=='running',content='hostname R1',connection_ok=True,retrieval_ok=kind=='running',error='Startup unavailable' if kind=='startup' else None)
        with patch.object(ncm_drivers,'get_driver',return_value=NS(get_configuration=retrieve)):scheduler._poll_once(self.now)
        state=self.state(row);self.assertEqual(state.status,'failed');self.assertEqual(state.failed,1);self.assertEqual(state.succeeded,0)
        self.assertEqual(scheduler.utc(state.succeeded_at),self.now-timedelta(days=1))
        self.assertEqual(self.db.query(NcmConfiguration).count(),1);self.assertEqual(self.db.query(NcmBackupJobTarget).count(),2)


    def child(self,row,mode):
        env=dict(os.environ,NCM_TEST_FERNET=self.key.decode())
        return subprocess.Popen([sys.executable,str(Path(__file__).with_name('worker.py')),str(self.engine.url),str(row.id),self.now.isoformat(),str(mode)],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)

    def test_two_processes_single_real_job(self):
        if self.engine.dialect.name!='sqlite':self.skipTest('Isolated-schema PostgreSQL requires separate process setup')
        row=self.schedule()
        with SSHDevice() as device:
            workers=[self.child(row,device.port) for _ in range(2)]
            for worker in workers:
                _,error=worker.communicate(timeout=20);self.assertEqual(worker.returncode,0,error)
        self.assertEqual(self.state(row).status,'completed')
        self.assertEqual(self.db.query(NcmBackupJob).count(),1);self.assertEqual(self.db.query(NcmConfiguration).count(),1)
        self.assertEqual(len(device.connections),1)

    def test_actual_process_crash_after_claim_no_replay(self):
        if self.engine.dialect.name!='sqlite':self.skipTest('Isolated-schema PostgreSQL requires separate process setup')
        row=self.schedule();worker=self.child(row,'crash');_,error=worker.communicate(timeout=20)
        self.assertEqual(worker.returncode,23,error);self.assertEqual(self.state(row).status,'running')
        self.assertEqual(self.db.query(NcmBackupJob).count(),1)
        scheduler._poll_once(self.now+timedelta(minutes=1))
        self.assertEqual(self.state(row).status,'failed');self.assertIn('interrupted',self.state(row).error)
        self.assertEqual(self.db.query(NcmBackupJob).count(),1)

    def test_startup_registers_scheduler_and_shutdown_cancels(self):
        from app.main import app
        from app import database
        started=[]
        async def loop():
            started.append(True)
            await asyncio.Event().wait()
        async def exercise():
            handler=next(f for f in app.router.on_startup if f.__name__=='_start_ncm_scheduler_loop')
            stopper=next(f for f in app.router.on_shutdown if f.__name__=='_stop_ncm_scheduler_loop')
            with patch.object(database,'get_engine',return_value=self.engine),patch('app.main.get_sessionmaker',return_value=self.sessions),patch.object(scheduler,'scheduler_loop',side_effect=loop):
                await handler();await asyncio.sleep(0)
                self.assertEqual(started,[True]);self.assertFalse(app.state.ncm_scheduler_task.done())
                await stopper();self.assertTrue(app.state.ncm_scheduler_task.cancelled())
        asyncio.run(exercise())


    def test_real_ssh_partial_fleet(self):
        second=NetworkDevice(name='R2',ip_address='127.0.0.2',vendor='Cisco',enabled=True);self.db.add(second);self.db.commit()
        row=self.schedule(device_ids=str(self.device.id)+','+str(second.id))
        with SSHDevice() as good, SSHDevice(reject=True) as bad:
            real=network_ops_execution.run_commands_on_device
            def connect(host,*a,**k):return real('127.0.0.1',*a,**k,port=good.port if host=='127.0.0.1' else bad.port)
            with patch.object(network_ops_execution,'run_commands_on_device',side_effect=connect):scheduler._poll_once(self.now)
        state=self.state(row);self.assertEqual(state.status,'partial_success');self.assertEqual((state.total,state.succeeded,state.failed),(2,1,1))
        self.assertEqual(self.db.query(NcmConfiguration).count(),1);self.assertEqual(self.db.query(NcmBackupJobTarget).count(),2)
        self.assertIsNone(state.succeeded_at)

if __name__=='__main__':unittest.main(verbosity=2)
