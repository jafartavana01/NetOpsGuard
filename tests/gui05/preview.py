"""Synthetic loopback preview; renders actual templates, never deploy this server."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
for name in ('overview','devices','findings','compliance','reports','schedule'):
    base.PAGES['/security/'+name]='security_'+name+'.html'
for device in ('d1','d2','d3','d4'):
    base.PAGES['/security/devices/'+device]='security_device_detail.html'
base.PAGES['/security/reports/12']='security_report_detail.html'
def render(path,superadmin=True,licensed_module_keys=None):
    home,sections=base.build_sidebar_sections(base.modules(),is_superadmin=superadmin,licensed_module_keys=licensed_module_keys)
    grants=['security:view','security:audit','ncm:view','ncm:backup','devices:view'] if superadmin else ['security:view']
    return base.ENV.get_template(base.PAGES.get(path,'security_overview.html')).render(request=NS(url=NS(path=path)),admin_username='review.operator',is_superadmin=superadmin,dashboard_item=home,nav_sections=sections,security_permissions=grants)
base.render=render
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8769),base.Handler).serve_forever()
