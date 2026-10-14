"""Schedule HTTP permission/CSRF contract using actual SQLite persistence."""
import unittest
from types import SimpleNamespace as NS
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import security
from app.database import get_db
from app.api import deps,routes_ncm
from test_integration import ScheduledBackupIntegration

class ScheduleAPI(ScheduledBackupIntegration):
    # Only API cases belong here; use the fixture without re-running inherited tests.
    def test_run_now_csrf_and_confirmed_blocked_result(self):
        row=self.schedule(device_ids='')
        app=FastAPI();app.include_router(routes_ncm.router)
        def session():
            with self.sessions() as db:yield db
        app.dependency_overrides[get_db]=session
        app.dependency_overrides[deps.get_current_admin]=lambda:NS(is_superadmin=True,role_id=None,username='operator')
        with TestClient(app) as client:
            url='/api/ncm/schedules/'+str(row.id)+'/run-now'
            self.assertEqual(client.post(url).status_code,403)
            self.assertEqual(self.db.query(routes_ncm.NcmBackupJob).count(),0)
            client.cookies.set(security.CSRF_COOKIE_NAME,'token')
            response=client.post(url,headers={'X-CSRF-Token':'token'})
            self.assertEqual(response.status_code,200,response.text)
            data=response.json();self.assertEqual(data['execution_status'],'blocked');self.assertTrue(data['last_job_id']);self.assertTrue(data['last_attempted_at'].endswith('Z'))
            self.assertNotIn('test-password',response.text)
            saved=client.get('/api/ncm/schedules').json()[0];self.assertEqual(saved['last_job_id'],data['last_job_id'])
            self.assertIn('No enabled',saved['execution_error'])
    def test_run_now_permission_denied(self):
        from app.models.admin_role import AdminRole
        AdminRole.__table__.create(self.engine)
        role=AdminRole(name='viewer',permissions='ncm:view');self.db.add(role);self.db.commit()
        row=self.schedule()
        app=FastAPI();app.include_router(routes_ncm.router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[deps.get_current_admin]=lambda:NS(is_superadmin=False,role_id=role.id,username='viewer')
        with TestClient(app) as client:
            client.cookies.set(security.CSRF_COOKIE_NAME,'token')
            response=client.post('/api/ncm/schedules/'+str(row.id)+'/run-now',headers={'X-CSRF-Token':'token'})
            self.assertEqual(response.status_code,403,response.text)
            self.assertEqual(self.db.query(routes_ncm.NcmBackupJob).count(),0)

if __name__=='__main__':
    suite=unittest.TestSuite(ScheduleAPI(name) for name in ScheduleAPI.__dict__ if name.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
