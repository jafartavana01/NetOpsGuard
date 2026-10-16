"""Comparison contracts plus real SQLite persistence/API; no device verification."""
import copy
import importlib
import json
import os
from pathlib import Path
import pkgutil
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, event, MetaData
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from fastapi import FastAPI
from fastapi.testclient import TestClient
import app.models
for m in pkgutil.iter_modules(app.models.__path__):
    importlib.import_module('app.models.'+m.name)
from app.database import Base, get_db
from app.models.audit_run import AuditRun, AuditFinding, AuditAssessment
from app.models.device import NetworkDevice
from app.api import deps, routes_security as api
from app.services.audit_comparison import Assessment, compare, ComparisonError, score_comparison, load_assessments
from app.services.audit_evidence import capture, findings_digest, config_hash
from app.services.security_audit_persistence import persist_audit_result
from app.security_center.engine.orchestrator import run_device_audit

RAW='version 15.2\nhostname R1\ninterface GigabitEthernet0/1\n description uplink\n!\nend\n'
DEVICE=uuid.uuid4()


def finding(status='fail', **kw):
    data=dict(id=uuid.uuid4(), domain='Management',check_id='SSH-1',interface_name=None,
              correlation_id=None,title='SSH',status=status,severity='high',evidence=['ip ssh version 2'],
              evidence_label='Observed',detail='',recommendation='',fix_command='',why='',risk='',attack='',
              best='',performance='',operational='',compatibility='',references=[])
    data.update(kw)
    return AuditFinding(**data)


def assessment(finding_status='fail', **kw):
    rows=[] if finding_status is None else [finding(finding_status)]
    r=AuditRun(id=uuid.uuid4(),device_id=DEVICE,device_name='R1',source='live',status='completed',
               raw_config=RAW,config_snapshot_hash=config_hash(RAW),overall_score=70,
               started_at=datetime(2026,1,1,tzinfo=timezone.utc))
    for key,value in kw.items():setattr(r,key,value)
    a=Assessment(r,rows,AuditAssessment(audit_run_id=r.id,device_identity=str(DEVICE),manifest='{}'))
    seal(a)
    return a


def seal(a):
    m=capture(a.run.raw_config or '',{},[])
    m.update(findings_hash=findings_digest(a.findings),score=a.run.overall_score)
    a.provenance.manifest=json.dumps(m)


def change_manifest(a, **kw):
    m=a.manifest;m.update(kw);a.provenance.manifest=json.dumps(m)


class ComparisonTests(unittest.TestCase):
    def category(self,a,b):return compare(a,b)['items'][0]['category']
    def test_fail_pass(self):self.assertEqual(self.category(assessment(),assessment('pass')),'resolved')
    def test_fail_fail(self):self.assertEqual(self.category(assessment(),assessment()),'persistent')
    def test_pass_fail(self):self.assertEqual(self.category(assessment('pass'),assessment()),'new')
    def test_first_observed(self):self.assertEqual(self.category(assessment(None),assessment()),'first_observed')
    def test_missing_is_indeterminate(self):self.assertEqual(self.category(assessment(),assessment(None)),'indeterminate')
    def test_manual_never_closes(self):self.assertEqual(self.category(assessment(),assessment('manual_review')),'manual_review')
    def test_na_never_closes(self):self.assertEqual(self.category(assessment(),assessment('na')),'indeterminate')
    def test_warn_never_closes(self):self.assertEqual(self.category(assessment(),assessment('warn')),'indeterminate')
    def test_error_never_closes(self):self.assertEqual(self.category(assessment(),assessment('error')),'indeterminate')
    def test_failed_run(self):self.assertEqual(self.category(assessment(),assessment('pass',status='failed')),'indeterminate')
    def test_running_run(self):self.assertEqual(self.category(assessment(),assessment('pass',status='running')),'indeterminate')
    def test_incomplete(self):
        b=assessment('pass');change_manifest(b,complete=False);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_changed_engine(self):
        b=assessment('pass');change_manifest(b,engine='a'*64);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_changed_policy(self):
        b=assessment('pass');change_manifest(b,policy='b'*64);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_changed_scope(self):
        b=assessment('pass');change_manifest(b,scope=[]);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_legacy_provenance(self):
        b=assessment('pass');b.provenance=None;self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_legacy_prior_is_not_regression(self):
        a=assessment('pass');a.provenance=None;self.assertEqual(self.category(a,assessment()),'first_observed')
    def test_malformed_manifest(self):
        b=assessment('pass');b.provenance.manifest='[';self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_malformed_manifest_fields(self):
        b=assessment('pass');change_manifest(b,engine=None);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_failed_manual_observation(self):
        self.assertEqual(self.category(assessment(),assessment('manual_review',status='failed')),'indeterminate')
    def test_error_elsewhere_blocks_resolution(self):
        b=assessment('pass');b.findings.append(finding('error',check_id='OTHER'));seal(b)
        self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_unknown_identity_format(self):
        a=assessment();a.run.device_id=None;a.provenance.device_identity='R1'
        with self.assertRaises(ComparisonError):compare(a,assessment())
    def test_tampered_evidence(self):
        b=assessment('pass');b.findings[0].evidence=['changed'];self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_tampered_status(self):
        b=assessment();b.findings[0].status='pass';self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_tampered_capture(self):
        b=assessment('pass');b.run.raw_config+='x';self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_partial_rows_deleted(self):
        b=assessment('pass');b.findings=[];self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_duplicates_retained(self):
        b=assessment('pass');b.findings.append(finding('pass'));seal(b);r=compare(assessment(),b)
        self.assertEqual(r['items'][0]['category'],'indeterminate');self.assertEqual(len(r['items'][0]['current']),2);self.assertIsNone(r['score_delta'])
    def test_duplicate_old(self):
        a=assessment();a.findings.append(finding());seal(a);self.assertEqual(self.category(a,assessment('pass')),'indeterminate')
    def test_different_domains(self):
        b=assessment('pass');b.findings[0].domain='Other';seal(b);self.assertEqual(self.category(assessment(),b),'indeterminate')
    def test_different_interfaces(self):
        a,b=assessment(),assessment('pass');a.findings[0].interface_name='Gi1';b.findings[0].interface_name='Gi2';seal(a);seal(b)
        self.assertEqual(self.category(a,b),'indeterminate')
    def test_correlation_disappears(self):
        a=assessment();a.findings[0].correlation_id='CORR-A';seal(a);self.assertEqual(self.category(a,assessment(None)),'indeterminate')
    def test_correlation_identity_separate(self):
        a,b=assessment(),assessment('pass');b.findings[0].correlation_id='CORR-A';seal(b);self.assertEqual(self.category(a,b),'indeterminate')
    def test_device_rename(self):self.assertEqual(self.category(assessment(),assessment('pass',device_name='renamed')),'resolved')
    def test_same_hostname_different_identity(self):
        b=assessment();b.run.device_id=uuid.uuid4();b.provenance.device_identity=str(b.run.device_id)
        with self.assertRaises(ComparisonError):compare(assessment(),b)
    def test_deleted_identity_retained(self):
        a,b=assessment(),assessment('pass');a.run.device_id=b.run.device_id=None;self.assertEqual(self.category(a,b),'resolved')
    def test_deleted_legacy_unknown(self):
        a=assessment();a.run.device_id=None;a.provenance=None
        with self.assertRaises(ComparisonError):compare(a,assessment())
    def test_identity_conflict(self):
        b=assessment();b.provenance.device_identity=str(uuid.uuid4())
        with self.assertRaises(ComparisonError):compare(assessment(),b)
    def test_same_run(self):
        a=assessment()
        with self.assertRaises(ComparisonError):compare(a,a)
    def test_reverse_order(self):
        a=assessment();b=assessment();b.run.started_at-=timedelta(days=1)
        with self.assertRaises(ComparisonError):compare(a,b)
    def test_sqlite_naive_utc(self):self.assertEqual(self.category(assessment(),assessment('pass',started_at=datetime(2026,1,1))),'resolved')
    def test_different_sources(self):
        for source in ['upload','scheduled','snapshot']:
            with self.subTest(source=source):self.assertEqual(self.category(assessment(),assessment('pass',source=source)),'resolved')
    def test_missing_score(self):self.assertIsNone(compare(assessment(),assessment('pass',overall_score=None))['score_delta'])
    def test_real_zero_score(self):self.assertEqual(compare(assessment(overall_score=0),assessment('pass',overall_score=90))['score_delta'],90)
    def test_score_changed_coverage(self):self.assertIsNone(compare(assessment(),assessment(None))['score_delta'])
    def test_score_tamper(self):
        b=assessment('pass');b.run.overall_score=99;self.assertIsNone(compare(assessment(),b)['score_delta'])
    def test_score_applicability(self):self.assertIsNone(compare(assessment(),assessment('na'))['score_delta'])
    def test_immutable_comparison(self):
        a,b=assessment(),assessment('pass');before=(a.provenance.manifest,b.provenance.manifest,a.findings[0].status)
        compare(a,b);self.assertEqual(before,(a.provenance.manifest,b.provenance.manifest,a.findings[0].status))
    def test_deterministic_order(self):
        a,b=assessment(),assessment();b.findings.append(finding(check_id='AAA'));seal(b)
        first=compare(a,b);b.findings.reverse();self.assertEqual([i['key'] for i in first['items']],[i['key'] for i in compare(a,b)['items']])
    def test_incomplete_config(self):
        for raw in ['', 'hostname R1\nend\n', RAW.replace('end\n',''),RAW+'--More--']:
            with self.subTest(raw=raw):self.assertFalse(capture(raw,{},[])['complete'])
    def test_real_engine_capture(self):
        r=run_device_audit(RAW);self.assertTrue(r.assessment['complete']);self.assertTrue(r.findings)
    def test_interface_failure_recorded(self):
        with patch('app.security_center.engine.orchestrator.parse_interface_config',side_effect=ValueError('bad')):
            r=run_device_audit(RAW)
        self.assertFalse(r.assessment['complete']);self.assertTrue(r.findings)


@compiles(JSONB,'sqlite')
def sqlite_json(element,compiler,**kw):return 'JSON'


class PersistenceTests(unittest.TestCase):
    def make_engine(self):
        engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        event.listen(engine,'connect',lambda con,rec:con.execute('PRAGMA foreign_keys=ON'))
        return engine
    def setUp(self):
        self.engine=self.make_engine();metadata=MetaData()
        for table in Base.metadata.sorted_tables:
            t=table.to_metadata(metadata)
            for c in t.constraints:
                if self.engine.dialect.name=='sqlite' and getattr(c,'deferrable',None):c.deferrable=None;c.initially=None
        metadata.create_all(self.engine);metadata.create_all(self.engine)  # repeatable additive installation
        self.db=Session(self.engine)
        self.addCleanup(self.engine.dispose);self.addCleanup(self.db.close)
        self.db.execute(NetworkDevice.__table__.insert().values(id=DEVICE,name='R1',ip_address='192.0.2.1'));self.db.commit()
        app=FastAPI();app.include_router(api.router)
        self.admin=NS(is_superadmin=True,role_id=None,username='tester')
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[deps.get_current_admin]=lambda:self.admin
        self.client=TestClient(app);self.addCleanup(self.client.close)
    def store(self,status='fail'):
        a=assessment(status);self.db.add(a.run);self.db.flush()
        for f in a.findings:f.audit_run_id=a.run.id;f.device_id=DEVICE;self.db.add(f)
        self.db.add(a.provenance);self.db.commit();return a
    def request(self,a,b):return self.client.get('/api/security/audits/'+str(a.run.id)+'/compare/'+str(b.run.id))
    def csrf(self):
        from app import security
        self.client.cookies.set(security.CSRF_COOKIE_NAME,'fixture')
        return {'X-CSRF-Token':'fixture'}
    def test_upload_complete_persists_provenance(self):
        r=self.client.post('/api/security/audit/upload',headers=self.csrf(),json={'device_id':str(DEVICE),'raw_config':RAW})
        self.assertEqual(r.status_code,201,r.text)
        run=self.db.get(AuditRun,uuid.UUID(r.json()['id']))
        self.assertIsNone(load_assessments(self.db,[run])[run.id].problem())
        self.assertEqual(self.client.get('/api/security/devices/'+str(DEVICE)+'/audits').status_code,200)
        self.assertEqual(self.client.get('/api/security/dashboard').status_code,200)
    def test_upload_csrf_preserved(self):
        r=self.client.post('/api/security/audit/upload',json={'device_id':str(DEVICE),'raw_config':RAW})
        self.assertEqual(r.status_code,403);self.assertEqual(self.db.query(AuditRun).count(),0)
    def test_unattached_upload_not_identity_by_name(self):
        ids=[]
        for _ in range(2):
            r=self.client.post('/api/security/audit/upload',headers=self.csrf(),json={'device_name':'R1','raw_config':RAW});self.assertEqual(r.status_code,201);ids.append(r.json()['id'])
        self.assertEqual(self.client.get('/api/security/audits/'+ids[0]+'/compare/'+ids[1]).status_code,409)
    def test_live_actual_engine_with_mocked_transport(self):
        result=NS(success=True,command_results=[NS(output=RAW)])
        with patch('app.services.network_ops_execution.run_commands_on_device',return_value=result):
            r=self.client.post('/api/security/devices/'+str(DEVICE)+'/audit/live',headers=self.csrf(),json={'ssh_username':'fixture','ssh_password':'fixture-secret'})
        self.assertEqual(r.status_code,201,r.text)
        run=self.db.get(AuditRun,uuid.UUID(r.json()['id']))
        self.assertIsNone(load_assessments(self.db,[run])[run.id].problem());self.assertNotIn('fixture-secret',r.text)
    def test_scheduled_actual_engine_with_mocked_transport(self):
        from app.services import scheduled_audit
        with patch.object(scheduled_audit.security,'decrypt_secret',return_value='fixture'),patch.object(scheduled_audit.network_ops_execution,'run_commands_on_device',return_value=NS(success=True,command_results=[NS(output=RAW)])):
            result=scheduled_audit.run_scheduled_audit(self.db,ssh_username='fixture',ssh_password_encrypted='opaque')
        self.assertEqual(result.succeeded,1)
        run=self.db.query(AuditRun).one();self.assertIsNone(load_assessments(self.db,[run])[run.id].problem())
        self.assertEqual(self.client.get('/api/security/batches').status_code,200)
    def test_incomplete_upload_cannot_confirm_resolution(self):
        a=self.store()
        r=self.client.post('/api/security/audit/upload',headers=self.csrf(),json={'device_id':str(DEVICE),'raw_config':RAW.replace('end\n','')})
        self.assertEqual(r.status_code,201)
        data=self.client.get('/api/security/audits/'+str(a.run.id)+'/compare/'+r.json()['id']).json()
        self.assertEqual(data['resolved_findings'],[]);self.assertIsNone(data['score_delta'])
    def test_api_resolved_and_evidence(self):
        a,b=self.store(),self.store('pass');r=self.request(a,b);self.assertEqual(r.status_code,200);data=r.json()
        self.assertEqual(data['counts']['resolved'],1);self.assertEqual(data['comparisons'][0]['previous'][0]['status'],'fail');self.assertEqual(data['comparisons'][0]['current'][0]['status'],'pass')
    def test_api_missing_not_resolved(self):
        a,b=self.store(),self.store(None);data=self.request(a,b).json();self.assertEqual(data['resolved_findings'],[]);self.assertEqual(data['counts']['indeterminate'],1)
    def test_api_identical(self):
        a=self.store();self.assertEqual(self.request(a,a).status_code,409)
    def test_api_bad_id(self):self.assertEqual(self.client.get('/api/security/audits/bad/compare/bad').status_code,404)
    def test_api_missing_id(self):self.assertEqual(self.client.get('/api/security/audits/'+str(uuid.uuid4())+'/compare/'+str(uuid.uuid4())).status_code,404)
    def test_api_denied(self):
        a,b=self.store(),self.store('pass');self.admin.is_superadmin=False;self.admin.role_id=uuid.uuid4()
        self.assertEqual(self.request(a,b).status_code,403)
    def test_retained_history_fk(self):
        a,b=self.store(),self.store('pass');self.db.execute(NetworkDevice.__table__.delete().where(NetworkDevice.id==DEVICE));self.db.commit();self.db.expire_all()
        self.assertIsNone(self.db.get(AuditRun,a.run.id).device_id);self.assertEqual(self.request(a,b).json()['counts']['resolved'],1)
        self.assertEqual(self.db.query(AuditFinding).count(),2)
    def test_legacy_rows_not_backfilled(self):
        a,b=self.store(),self.store('pass');self.db.delete(b.provenance);self.db.commit()
        self.assertEqual(self.request(a,b).json()['counts']['indeterminate'],1);self.assertEqual(self.db.query(AuditAssessment).count(),1)
    def test_real_engine_persistence(self):
        a=assessment();self.db.add(a.run);self.db.flush();result=run_device_audit(RAW);persist_audit_result(self.db,audit_run=a.run,result=result);self.db.commit()
        loaded=load_assessments(self.db,[a.run])[a.run.id];self.assertIsNone(loaded.problem());self.assertIsNotNone(a.run.completed_at)
    def test_transaction_rollback(self):
        a=assessment();self.db.add(a.run);self.db.commit()
        persist_audit_result(self.db,audit_run=a.run,result=run_device_audit(RAW));self.db.rollback()
        self.assertEqual(self.db.query(AuditAssessment).count(),0);self.assertEqual(self.db.query(AuditFinding).count(),0)
    def test_capture_mismatch_rejected(self):
        a=assessment();self.db.add(a.run);self.db.flush()
        with self.assertRaises(ValueError):persist_audit_result(self.db,audit_run=a.run,result=run_device_audit(RAW+'!\n'))
        self.db.rollback();self.assertEqual(self.db.query(AuditAssessment).count(),0)
    def test_activity_no_unknown_delta(self):
        a,b=self.store(),self.store('pass');self.db.delete(b.provenance);self.db.commit()
        r=self.client.get('/api/security/activity');self.assertEqual(r.status_code,200);self.assertTrue(all(x['score_delta'] is None for x in r.json()))

if __name__=='__main__':unittest.main()
