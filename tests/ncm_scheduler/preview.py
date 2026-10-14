"""Actual schedule template; browser API replies are controlled fixtures."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
from types import SimpleNamespace as NS
def render(path,superadmin=True,licensed_module_keys=None):
    home,sections=base.build_sidebar_sections(base.modules(),is_superadmin=superadmin,licensed_module_keys=licensed_module_keys)
    return base.ENV.get_template(base.PAGES[path]).render(request=NS(url=NS(path=path)),admin_username="operator",is_superadmin=superadmin,dashboard_item=home,nav_sections=sections,operations_permissions=["ncm:view","ncm:schedule"] if superadmin else ["ncm:view"])
base.render=render
base.PAGES['/ncm/schedules']='ncm_schedules.html'
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8774),base.Handler).serve_forever()
