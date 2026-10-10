"""Actual FastAPI router/JSON/CSRF boundary with query doubles and stubbed login.

Not a PostgreSQL or session-authentication integration test.
"""
import importlib.util
import json
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock

DEPS = all(importlib.util.find_spec(n) for n in ('fastapi','sqlalchemy','httpx'))

@unittest.skipUnless(DEPS, 'Project dependencies required for HTTP restoration tests')
class RestorationHTTPTests(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes_policy_versions import router
        from app.api.deps import get_current_admin
        from app.database import get_db
        from app.security import CSRF_COOKIE_NAME
        self.policy=NS(id=uuid.uuid4(), name='scoped')
        self.version=NS(id=uuid.uuid4(),policy_id=self.policy.id,snapshot=json.dumps({
            'condition_device_name':'missing','condition_group_name':None,
            'condition_device_group_name':None,'command_set_names':[]}))
        self.db=MagicMock()
        def query(model):
            q=MagicMock();q.filter.return_value=q;q.all.return_value=[]
            q.first.return_value={'Policy':self.policy,'PolicyVersion':self.version}.get(model.__name__)
            return q
        self.db.query.side_effect=query
        app=FastAPI();app.include_router(router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_admin]=lambda:NS(username='reviewer',is_superadmin=True,role_id=None)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.client.cookies.set(CSRF_COOKIE_NAME,'test-only-csrf')
        self.url=f'/api/policies/{self.policy.id}/versions/{self.version.id}/restore'
    def test_missing_reference_returns_structured_conflict(self):
        response=self.client.post(self.url,headers={'X-CSRF-Token':'test-only-csrf'})
        self.assertEqual(response.status_code,409)
        d=response.json()['detail'];self.assertFalse(d['restored'])
        self.assertEqual(d['code'],'policy.restore.invalid')
        self.assertEqual(d['diagnostics'][0]['code'],'policy.restore.reference_missing')
        self.assertEqual(d['diagnostics'][0]['object_name'],'missing')
        self.assertNotIn('Traceback',response.text)
        self.db.commit.assert_not_called();self.db.add.assert_not_called();self.db.flush.assert_not_called()
    def test_invalid_json_is_structured_not_internal_error(self):
        self.version.snapshot='{malformed'
        response=self.client.post(self.url,headers={'X-CSRF-Token':'test-only-csrf'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['detail']['diagnostics'][0]['code'],'policy.restore.snapshot_invalid')
        self.db.commit.assert_not_called()
    def test_csrf_remains_required(self):
        response=self.client.post(self.url)
        self.assertEqual(response.status_code,403)
        self.db.commit.assert_not_called()
