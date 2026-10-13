"""Real FastAPI route/dependency checks with synthetic identities; no PostgreSQL claim."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import deps, routes_admin_users, routes_admin_roles, routes_platform_settings, routes_ad_settings, routes_modules, routes_license, routes_radius, routes_diagnostics
from app.database import get_db

class AdministrationBoundary(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI()
        for module in [routes_admin_users,routes_admin_roles,routes_platform_settings,routes_ad_settings,routes_modules,routes_license,routes_radius,routes_diagnostics]:self.app.include_router(module.router)
        self.db=MagicMock();self.db.query.return_value.filter.return_value.first.return_value=NS(permissions=[])
        self.admin=NS(is_superadmin=False,role_id='limited-role')
        self.app.dependency_overrides[deps.get_current_admin]=lambda:self.admin
        self.app.dependency_overrides[get_db]=lambda:self.db
        self.client=TestClient(self.app)
        self.client.cookies.set('aaa_platform_csrf','probe-token')
    def request(self,method,path,payload=None,csrf=True):
        return self.client.request(method,path,json=payload,headers={'X-CSRF-Token':'probe-token'} if csrf else {})
    def denied(self,method,path,payload=None):
        response=self.request(method,path,payload)
        self.assertEqual(response.status_code,403,response.text)
        self.assertFalse(self.db.commit.called)
    def test_administrator_reads_require_superadmin(self):
        for path in ['/api/admin-users','/api/admin-roles','/api/admin-roles/permission-catalog']:
            with self.subTest(path=path):self.denied('GET',path)
    def test_platform_reads_require_superadmin(self):
        for path in ['/api/platform-settings','/api/ad-settings','/api/modules','/api/license','/api/radius/settings','/api/radius/listeners']:
            with self.subTest(path=path):self.denied('GET',path)
    def test_settings_writes_require_superadmin(self):
        for method,path,payload in [('PUT','/api/platform-settings/network',{}),('PUT','/api/ad-settings',{}),('PUT','/api/radius/settings',{}),('PUT','/api/modules/ncm',{'enabled':False})]:
            with self.subTest(path=path):self.denied(method,path,payload)
    def test_sensitive_operations_require_superadmin(self):
        for path in ['/api/platform-settings/restart-management-service','/api/platform-settings/tls/regenerate','/api/platform-settings/tls/upload','/api/ad-settings/test','/api/radius/probe','/api/license/import','/api/license/remove']:
            with self.subTest(path=path):self.denied('POST',path,{})
    def test_account_mutations_require_superadmin(self):
        for method,path in [('POST','/api/admin-users'),('PUT','/api/admin-users/00112233-4455-6677-8899-aabbccddeeff'),('DELETE','/api/admin-users/00112233-4455-6677-8899-aabbccddeeff'),('POST','/api/admin-roles'),('DELETE','/api/admin-roles/00112233-4455-6677-8899-aabbccddeeff')]:
            with self.subTest(path=path,method=method):self.denied(method,path,{})
    def test_diagnostics_retains_permission_checks(self):
        for method,path in [('GET','/api/diagnostics/overview'),('GET','/api/diagnostics/audit-events'),('GET','/api/diagnostics/service-log/aaa-platform.service'),('POST','/api/diagnostics/validate-config')]:
            with self.subTest(path=path):self.denied(method,path)
    def test_mutation_csrf_required_even_for_superadmin(self):
        self.admin.is_superadmin=True
        for method,path in [('PUT','/api/platform-settings/network'),('POST','/api/platform-settings/restart-management-service'),('POST','/api/platform-settings/tls/upload'),('POST','/api/license/import'),('POST','/api/license/remove'),('POST','/api/ad-settings/test'),('PUT','/api/ad-settings'),('PUT','/api/radius/settings'),('POST','/api/radius/probe'),('POST','/api/admin-users'),('POST','/api/admin-roles'),('PUT','/api/modules/ncm')]:
            with self.subTest(path=path):
                response=self.request(method,path,{},csrf=False)
                self.assertEqual(response.status_code,403,response.text);self.assertIn('CSRF',response.text)
        self.assertFalse(self.db.commit.called)
    def test_superadmin_dependency_allows_declared_admin(self):
        self.admin.is_superadmin=True
        self.assertIs(deps.get_current_superadmin(self.admin),self.admin)

if __name__=='__main__':unittest.main(verbosity=2)
