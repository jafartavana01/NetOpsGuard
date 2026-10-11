"""Loopback-only visual fixtures; actual templates, no DB or live AAA writes."""
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'gui01'))
import preview as base
for name in ('accounting','policies','users','groups','devices','device_groups','sessions','access_events','command_sets','command_categories','effective_access','policy_simulator'):
    base.PAGES['/tacacs/'+name.replace('_','-')]=name+'.html'
if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1',8767),base.Handler).serve_forever()
