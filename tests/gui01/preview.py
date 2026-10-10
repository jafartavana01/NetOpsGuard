"""Local-only visual fixture server. Actual Jinja templates; no app/DB startup.
API data are synthetic and returned solely by this test server. Never deploy it.
"""
import ast,json,sys,mimetypes
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from jinja2 import Environment,FileSystemLoader,select_autoescape
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.modules.sidebar import build_sidebar_sections
from app.modules.registry import NavEntry

def value(node):
 if isinstance(node,ast.List):return [value(x) for x in node.elts]
 if isinstance(node,ast.Call) and getattr(node.func,'id','')=='NavEntry':return NavEntry(**{k.arg:value(k.value) for k in node.keywords})
 return ast.literal_eval(node)
def modules():
 rows=[]
 for p in (ROOT/'app/modules').glob('*_module.py'):
  for n in ast.walk(ast.parse(p.read_text())):
   if isinstance(n,ast.Call) and getattr(n.func,'id','')=='Module':
    kw={k.arg:k.value for k in n.keywords}
    rows.append(NS(key=value(kw['key']),name=value(kw['name']),nav_entries=value(kw.get('nav_entries',ast.List(elts=[]))),mandatory=value(kw.get('mandatory',ast.Constant(False)))))
 return rows
ENV=Environment(loader=FileSystemLoader(ROOT/'app/templates'),autoescape=select_autoescape())
PAGES={'/dashboard':'dashboard.html','/tacacs/policies':'policies.html','/tacacs/groups':'groups.html','/tacacs/devices':'devices.html','/tacacs/sessions':'sessions.html','/tacacs/access-events':'access_events.html','/security/overview':'security_overview.html','/tacacs/config':'config.html'}
def render(path,superadmin=True,licensed_module_keys=None):
 home,sections=build_sidebar_sections(modules(),is_superadmin=superadmin,licensed_module_keys=licensed_module_keys)
 return ENV.get_template(PAGES.get(path,'dashboard.html')).render(request=NS(url=NS(path=path)),admin_username='review.operator',is_superadmin=superadmin,dashboard_item=home,nav_sections=sections)
DEVICE=dict(id='d1',name='R1',ip_address='192.0.2.10',enabled=True,device_group_id=None,description='Distribution router',vendor='Cisco',platform='ios',has_secret=True,has_radius_secret=False,radius_enabled=False,ipv6_address=None)
GROUP=dict(id='g1',name='ops',description='Operations team',ad_group_name='AAA-ops',authority='EXTERNAL',external_source_id='00112233-4455-6677-8899-aabbccddeeff',external_source_name='netopsguard_ad_00112233445566778899aabbccddeeff',binding_status='valid',binding_diagnostics=[],member_count=0,referenced_by_policy_names=['R1_ops'])
POLICY=dict(id='p1',name='R1_ops',priority=10,enabled=True,description='Operations access to R1',default_priv_lvl=15,default_action='deny',condition_group_id='g1',condition_group_name='ops',condition_device_id='d1',condition_device_name='R1',condition_device_group_id=None,condition_device_group_name=None,command_sets=[],condition_summary='Group ops AND device R1',requires_manual_approval=False)

def api(path):
 if path=='/api/tacacs-groups':return [GROUP]
 if path=='/api/devices':return [DEVICE]
 if path=='/api/policies':return [POLICY]
 if path=='/api/tacacs-groups/external-sources':return [dict(id=GROUP['external_source_id'],name=GROUP['external_source_name'],host='ad.example.test',enabled=True,group_prefix='AAA-',use_memberof=True)]
 if path=='/api/config/candidate':return dict(applicable=True,has_changes=False,diff='',candidate='fixture',active='fixture',diagnostics=[],uncompilable_policies=[])
 if path=='/api/system/status':return dict(database='connected',services={'tac-plus-ng.service':{'active_state':'active'},'aaa-platform.service':{'active_state':'active'}},build_info={},os='Synthetic preview environment')
 if 'sessions' in path:return dict(sessions=[],total=0)
 if 'access-events' in path:return dict(rows=[],counts={},matched=0,total_in_log=0)
 if 'recent-activity' in path:return dict(rows=[],minutes=5)
 if 'health' in path:return dict(permit_count=1280,non_permit_count=24,distinct_devices=12,distinct_users=28,total_records_in_tail=1304,hourly_activity=[])
 if path=='/api/security/dashboard':return dict(average_score=None,previous_average_score=None,devices_audited=0,manual_review_findings=0,failed_checks=0,compliance_score=None,severity_counts=[],domain_scores=[],score_trend=[],compliance=[],risky_devices=[],top_risks=[],heatmap=[],heatmap_domains=[],score_explanation=None,manual_review=None)
 if '/api/ncm/' in path:return dict(total_devices=0,devices_with_recent_backup=0,devices_never_backed_up=0,devices_with_failed_backup=0,total_configurations=0,configurations_changed_recently=0,recent_changes=[])
 if 'group-members' in path:return dict(members=[],total=0)
 if path=='/api/monitoring/settings':return dict(enabled=False,placeholder_key='')
 if path=='/api/monitoring/unrecognized':return dict(devices=[])
 if path=='/api/network-scan/unknown-devices':return dict(devices=[],note='Synthetic preview: no unrecognized devices.')
 if path=='/api/aaa-template':return dict(template='',platform_ip='192.0.2.1')
 return []
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  url=urlsplit(self.path);path=url.path
  if path.startswith('/static/'):
   file=(ROOT/'app'/path.lstrip('/')).resolve()
   if not file.is_relative_to((ROOT/'app/static').resolve()) or not file.is_file():self.send_error(404);return
   body=file.read_bytes();kind=mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
  elif path.startswith('/api/'):
   body=json.dumps(api(path)).encode();kind='application/json'
  else:body=render(path,parse_qs(url.query).get('role')!=['operator']).encode();kind='text/html'
  self.send_response(200);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body)
if __name__=='__main__':
 ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1]) if len(sys.argv)>1 else 8765),Handler).serve_forever()
