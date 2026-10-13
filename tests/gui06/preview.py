"""Loopback-only GUI-06 fixture server. Actual templates; no daemon or DB claim."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
for route,template in {
 '/platform/settings':'platform_settings','/platform/admin-users':'admin_users',
 '/platform/admin-roles':'admin_roles','/platform/active-directory':'active_directory',
 '/platform/modules':'modules','/platform/license':'license','/radius/server':'radius_settings',
 '/tacacs/diagnostics':'diagnostics','/tacacs/aaa-health':'aaa_health',
}.items():base.PAGES[route]=template+'.html'
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8770),base.Handler).serve_forever()
