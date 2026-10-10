"""GUI-02 isolated visual fixture server: real templates, no production DB/auth."""
import sys,json
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import urlsplit,parse_qs
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gui01'))
import preview as base
from app.web.dashboard_context import dashboard_capabilities
class FakeDB:
 def __init__(self,permissions):self.permissions=permissions
 def query(self,*args):return self
 def filter(self,*args):return self
 def first(self):return NS(permissions=self.permissions)
class Handler(base.Handler):
 def do_GET(self):
  url=urlsplit(self.path)
  if url.path!='/dashboard':return super().do_GET()
  role=parse_qs(url.query).get('role',['admin'])[0]
  admin=NS(is_superadmin=role=='admin',role_id=None if role=='legacy' else 'role')
  permissions=['accounting:view'] if role=='reader' else []
  home,sections=base.build_sidebar_sections(base.modules(),is_superadmin=admin.is_superadmin)
  html=base.ENV.get_template('dashboard.html').render(request=NS(url=NS(path='/dashboard')),admin_username='preview.operator',is_superadmin=admin.is_superadmin,dashboard_item=home,nav_sections=sections,dashboard_capabilities=dashboard_capabilities(admin,FakeDB(permissions)))
  self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(html.encode())
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8766),Handler).serve_forever()
