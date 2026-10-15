"""Loopback actual-template preview; API data is synthetic and labelled in tests."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.version import metadata
base.ENV.globals['application_metadata']=metadata
base.PAGES.update({'/ncm/schedules':'ncm_schedules.html','/security/schedule':'security_schedule.html','/platform/settings':'platform_settings.html','/platform/diagnostics':'diagnostics.html'})
from types import SimpleNamespace as NS
def render(path,superadmin=True,licensed_module_keys=None):
    home,sections=base.build_sidebar_sections(base.modules(),is_superadmin=superadmin,licensed_module_keys=licensed_module_keys)
    return base.ENV.get_template(base.PAGES.get(path,'dashboard.html')).render(request=NS(url=NS(path=path)),admin_username='operator',is_superadmin=superadmin,dashboard_item=home,nav_sections=sections,operations_permissions=['ncm:view','ncm:schedule'],security_permissions=['security:view','security:audit'])
base.render=render
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8775),base.Handler).serve_forever()
