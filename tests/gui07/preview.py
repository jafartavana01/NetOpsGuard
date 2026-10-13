"""Actual Jinja on loopback; synthetic HTTP only, no DB or daemon claim."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui01'))
import preview as base
for path, template in {
    '/radius/policies': 'radius_policies', '/radius/attributes': 'radius_attributes',
    '/platform/settings': 'platform_settings', '/tacacs/users': 'users',
}.items():
    base.PAGES[path] = template + '.html'
for name in ('accounting','policies','users','groups','devices','device_groups','sessions','access_events','command_sets','command_categories','effective_access','policy_simulator'):
    base.PAGES['/tacacs/'+name.replace('_','-')] = name+'.html'
for name in ('overview','archive','compare','diff','drift','jobs','schedules','change_control'):
    base.PAGES['/ncm/'+('changes' if name=='change_control' else name)] = 'ncm_'+name+'.html'
for name in ('jobs','templates','checks','audits'):
    base.PAGES['/network-ops/'+name] = 'network_ops_'+name+'.html'
for name in ('overview','devices','findings','compliance','reports','schedule'):
    base.PAGES['/security/'+name] = 'security_'+name+'.html'
for name in ('settings','admin_users','admin_roles','active_directory','modules','license'):
    base.PAGES['/platform/'+name.replace('_','-')] = ('platform_settings' if name=='settings' else name)+'.html'
base.PAGES['/radius/clients'] = 'radius_clients.html'
base.PAGES['/radius/server'] = 'radius_settings.html'
base.PAGES['/tacacs/aaa-health'] = 'aaa_health.html'
base.PAGES['/tacacs/diagnostics'] = 'diagnostics.html'
from types import SimpleNamespace as NS

def render(path, superadmin=True, licensed_module_keys=None):
    home, sections = base.build_sidebar_sections(base.modules(), is_superadmin=superadmin, licensed_module_keys=licensed_module_keys)
    return base.ENV.get_template(base.PAGES.get(path, 'dashboard.html')).render(
        request=NS(url=NS(path=path)), admin_username='review.operator', is_superadmin=superadmin,
        dashboard_item=home, nav_sections=sections,
        operations_permissions=['ncm:'+p for p in ('view','backup','download','diff','schedule','propose','approve','deploy')]+['network_ops:view','network_ops:execute','network_ops:templates','devices:view'],
        security_permissions=['security:view','security:audit','ncm:view','ncm:backup','devices:view'])
base.render = render
if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8771), base.Handler).serve_forever()
