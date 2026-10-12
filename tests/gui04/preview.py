"""Loopback synthetic preview of actual GUI-04 templates, no live devices."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
for name in ('overview','archive','compare','diff','drift','jobs','schedules','change_control'):
    base.PAGES['/ncm/'+('changes' if name=='change_control' else name)]='ncm_'+name+'.html'
for name in ('jobs','job_detail','templates','checks','audits'):
    base.PAGES['/network-ops/'+name.replace('_','-')]='network_ops_'+name+'.html'
base.PAGES['/network-ops/jobs/jnet1']='network_ops_job_detail.html'
def render(path,superadmin=True,licensed_module_keys=None):
    home,sections=base.build_sidebar_sections(base.modules(),is_superadmin=superadmin,licensed_module_keys=licensed_module_keys)
    permissions=['ncm:'+p for p in ('view','backup','download','diff','schedule','propose','approve','deploy')]+['network_ops:view','network_ops:execute','network_ops:templates','devices:view'] if superadmin else ['ncm:view','network_ops:view']
    return base.ENV.get_template(base.PAGES[path]).render(request=NS(url=NS(path=path)),admin_username='review.operator',is_superadmin=superadmin,dashboard_item=home,nav_sections=sections,operations_permissions=permissions)
base.render=render
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8768),base.Handler).serve_forever()
