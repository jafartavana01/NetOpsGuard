import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import security
from app.database import get_db
from app.api import routes_system, routes_platform_settings, deps
from app.services import timezone_preference

class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'timezone.json'
        self.p=patch.object(timezone_preference,'PATH',self.path);self.p.start();self.addCleanup(self.p.stop)
        self.admin=NS(is_superadmin=True,role_id=None)
        app=FastAPI();app.include_router(routes_system.router);app.include_router(routes_platform_settings.router)
        app.dependency_overrides[deps.get_current_admin]=lambda:self.admin
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.client.cookies.set(security.CSRF_COOKIE_NAME,'token');self.headers={'X-CSRF-Token':'token'}
    def save(self,zone):return self.client.put('/api/platform-settings/timezone',json={'timezone':zone},headers=self.headers)
    def test_default_is_explicit_utc_not_host(self):
        self.assertEqual(self.client.get('/api/system/timezone').json()['timezone'],'UTC')
    def test_save_and_read(self):
        self.assertEqual(self.save('Asia/Tehran').status_code,200)
        self.assertEqual(self.client.get('/api/system/timezone').json()['timezone'],'Asia/Tehran')
    def test_bad_timezone_keeps_previous(self):
        self.save('Asia/Tehran');self.assertEqual(self.save('fake').status_code,422)
        self.assertEqual(timezone_preference.load(),'Asia/Tehran')
    def test_csrf(self):
        r=self.client.put('/api/platform-settings/timezone',json={'timezone':'UTC'})
        self.assertEqual(r.status_code,403);self.assertFalse(self.path.exists())
    def test_non_admin_read_only(self):
        self.admin.is_superadmin=False
        self.assertEqual(self.save('UTC').status_code,403)
        self.assertEqual(self.client.get('/api/system/timezone').status_code,200)
    def test_no_auth(self):
        self.client.app.dependency_overrides.clear()
        self.client.app.dependency_overrides[get_db]=lambda:None
        self.assertIn(self.client.get('/api/system/version').status_code,[401,403])
    def test_version_public_allowlist(self):
        d=self.client.get('/api/system/version').json()
        self.assertEqual(set(d),{'application','version','commit'})
        self.assertRegex(d['version'],r'^\d+\.\d+\.\d+\.\d+$')
    def test_corruption_does_not_silently_reset(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):timezone_preference.load()
