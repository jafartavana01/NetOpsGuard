"""Focused GUI-02 source/permission projection contracts. No PostgreSQL required."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from app.web.dashboard_context import dashboard_capabilities,DASHBOARD_PERMISSIONS
from app.api.deps import require_permission
from fastapi import HTTPException
class DB:
 def __init__(self,role):self.role=role;self.queries=0
 def query(self,*args):self.queries+=1;return self
 def filter(self,*args):return self
 def first(self):return self.role
class DashboardContracts(unittest.TestCase):
 def test_projection_matches_existing_api_rules(self):
  for superadmin,role_id,role in [(True,'x',None),(False,None,None),(False,'x',None),(False,'x',NS(permissions=[])),(False,'x',NS(permissions=['accounting:view','ncm:view']))]:
   admin=NS(is_superadmin=superadmin,role_id=role_id)
   db=DB(role);caps=dashboard_capabilities(admin,db)
   self.assertLessEqual(db.queries,1)
   for key in DASHBOARD_PERMISSIONS:
    try:require_permission(key)(admin=admin,db=db);expected=True
    except HTTPException as exc:self.assertEqual(exc.status_code,403);expected=False
    self.assertEqual(caps[key],expected,(superadmin,role_id,key))
   self.assertEqual(caps['directory:check'],superadmin)
 def test_missing_role_does_not_expose_actions(self):
  caps=dashboard_capabilities(NS(is_superadmin=False,role_id='missing'),DB(None));self.assertFalse(any(caps.values()))
 def test_no_role_keeps_existing_compatibility(self):
  caps=dashboard_capabilities(NS(is_superadmin=False,role_id=None),DB(None));self.assertTrue(caps['devices:write']);self.assertFalse(caps['directory:check'])
 def test_safe_dom_rendering(self):
  code=(ROOT/'app/static/js/pages/dashboard.js').read_text();self.assertNotIn('.innerHTML',code);self.assertIn('textContent',code)
 def test_read_only_refresh_with_bounded_directory_polling(self):
  code=(ROOT/'app/static/js/pages/dashboard.js').read_text()
  self.assertEqual(code.count('setInterval('),1);self.assertIn('setInterval(checkDirectory,60000)',code);self.assertIn('clearInterval(directoryTimer)',code);self.assertNotIn("method:'POST'",code);self.assertNotIn('/api/config/apply',code)
  self.assertIn('Promise.allSettled',code);self.assertIn('AbortController',code);self.assertIn('onViewLeave',code)
 def test_existing_security_contracts_not_reinterpreted(self):
  code=(ROOT/'app/static/js/pages/dashboard.js').read_text()
  self.assertNotIn('identity_membership_unknown',code);self.assertNotIn('compile_candidate',code)
  self.assertIn('!candidate.applicable',code);self.assertIn('candidate.diagnostics',code)
 def test_dashboard_is_scoped_to_existing_design_system(self):
  template=(ROOT/'app/templates/dashboard.html').read_text();css=(ROOT/'app/static/css/pages/dashboard.css').read_text()
  self.assertIn('partials/gui_components.html',template);self.assertIn('class="card',template);self.assertNotIn(':root',css)
  self.assertIn('NetOpsUI.chartOptions()', (ROOT/'app/static/js/pages/dashboard.js').read_text())
 def test_fixture_code_not_loaded_by_production(self):
  for path in [ROOT/'app/templates/dashboard.html',ROOT/'app/static/js/pages/dashboard.js',ROOT/'app/web/dashboard_context.py']:
   text=path.read_text();self.assertNotIn('fixtures.cjs',text);self.assertNotIn('operator1',text);self.assertNotIn('synthetic-fixture',text)
 def test_data_semantics_documented_in_ui(self):
  code=(ROOT/'app/static/js/pages/dashboard.js').read_text()
  for phrase in ['No backup job history','Snapshots added within 48 hours','Correlated from accounting log tail','Non-permit includes','Coverage is partial']:
   self.assertIn(phrase,code)
if __name__=='__main__':unittest.main(verbosity=2)
