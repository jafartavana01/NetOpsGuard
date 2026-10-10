"""Opt-in isolated native verification of the actual generated EXTERNAL predicate.
No production server or AD connection. NATIVE_DAEMON and NATIVE_MAVIS_LIB must
point to the accepted locally built revision; NATIVE_OUTPUT is a scratch folder.
Synthetic backend verifies daemon source/membership behavior, not LDAP health.
"""
import os,pathlib,subprocess,socket,struct,hashlib,time,json,signal,sys
from test_external_authority import ExternalAuthorityTests, TOKEN
BIN=pathlib.Path(os.environ['NATIVE_DAEMON']).resolve()
LIB=pathlib.Path(os.environ['NATIVE_MAVIS_LIB']).resolve()
ROOT=pathlib.Path(os.environ['NATIVE_OUTPUT']).resolve();ROOT.mkdir(parents=True,exist_ok=True)
ENV={**os.environ,'LD_LIBRARY_PATH':str(LIB.parent)}
with socket.socket() as sock:
 sock.bind(('127.0.0.1',0));PORT=sock.getsockname()[1]
def bounded(args,seconds=5):
 p=subprocess.Popen(args,env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
 try:
  out=p.communicate(timeout=seconds)[0];return p.returncode,out.decode(errors='replace')
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);out=p.communicate()[0];return None,'TIMEOUT\n'+out.decode(errors='replace')
def crypt(body,sid,v,seq):
 pad=b'';last=b''
 while len(pad)<len(body):
  last=hashlib.md5(struct.pack('!I',sid)+b'probe'+bytes([v,seq])+last).digest();pad+=last
 return bytes(x^y for x,y in zip(body,pad))
def exact(s,n):
 b=b''
 while len(b)<n:
  x=s.recv(n-len(b))
  if not x:raise RuntimeError('connection closed')
  b+=x
 return b
def packet(s,typ,seq,body,sid):
 s.sendall(struct.pack('!BBBBII',0xc0,typ,seq,0,sid,len(body))+crypt(body,sid,0xc0,seq))
 v,t,q,flags,rsid,n=struct.unpack('!BBBBII',exact(s,12));b=exact(s,n)
 return b if flags&1 else crypt(b,rsid,v,q)
def request(user,kind,password='probe'):
 u=user.encode();port=b'tty0';addr=b'192.0.2.1';sid=int.from_bytes(os.urandom(4),'big')
 with socket.create_connection(('127.0.0.1',PORT),timeout=3) as s:
  s.settimeout(4)
  if kind=='auth':
   body=bytes([1,15,1,1,len(u),len(port),len(addr),0])+u+port+addr
   r=packet(s,1,1,body,sid);seq=3;steps=[r.hex()]
   while r[0] in [3,4,5] and seq<10:
    answer=u if r[0]==4 else password.encode()
    r=packet(s,1,seq,struct.pack('!HHB',len(answer),0,0)+answer,sid);seq+=2;steps.append(r.hex())
   return {'status':r[0],'replies':steps}
  args=[b'service=shell',b'cmd='+(b'show' if kind=='command' else b'')]
  if kind=='command':args.append(b'cmd-arg=version')
  b=bytes([6,15,1,1,len(u),len(port),len(addr),len(args)])+bytes(map(len,args))+u+port+addr+b''.join(args)
  r=packet(s,2,1,b,sid);return {'status':r[0],'reply':r.hex()}

fixture=ExternalAuthorityTests();fixture.setUp()
fixture.policy.condition_device_id='d'
from types import SimpleNamespace as NS
fixture.inv.devices=[NS(id='d',name='loop',device_group_id=None)]
expression=fixture.expression()
fixture.h.load('app/services/config_compiler.py','_mavis_block')
fixture.h.ns['security']=NS(decrypt_secret=lambda value:'fixture-only')
generated_mavis=fixture.h.call('_mavis_block',fixture.backend)
(ROOT/'generated-mavis.conf').write_text(generated_mavis)
(ROOT/'generated-expression.txt').write_text(expression+'\n')
backend=pathlib.Path(__file__).parent/'fixtures/external_backend.py'
# Retain exact generated module name, source and member predicate. Substitute
# only the module path/backend executable for isolated synthetic verification.
module_header=generated_mavis.splitlines()[0].replace('= external {','= '+str(LIB)+' {')
module=module_header+' exec = '+sys.executable+' '+sys.executable+' '+str(backend)+' bound }'
base='id = spawnd { background = no single process = yes listen { address = 127.0.0.1 port = PORT } }\nid = tac_plus-ng {\nMODULE\nmavis module third_test = LIB { exec = PY PY BACKEND third }\nuser backend = mavis\nlogin backend = mavis\nhost loop { address = 127.0.0.1 key = probe }\ngroup ops { }\ngroup other { }\nuser local { password login = clear probe member = ops }\nprofile allow { script { permit } }\nruleset {\nrule external { script { if (EXPRESSION) { profile = allow permit } } }\nFALLBACK\n}\n}\n'
base=base.replace('PORT',str(PORT)).replace('MODULE',module).replace('LIB',str(LIB)).replace('PY',sys.executable).replace('BACKEND',str(backend)).replace('EXPRESSION',expression)
# Also parse a complete database-derived candidate rendered by the actual
# compiler functions. Only external binary paths are substituted for this lab.
fixture.h.load('app/services/config_compiler.py','STATIC_PREAMBLE _host_block _group_block _user_block _radius_blocks')
fixture.h.ns['LOG_DIR']=str(ROOT)
fixture.h.ns['ACCOUNTING_FIELD_SEPARATOR']='::'
fixture.inv.devices[0].enabled=True
fixture.inv.devices[0].ip_address='127.0.0.1'
fixture.inv.devices[0].ipv6_address=None
fixture.inv.devices[0].shared_secret_encrypted='fixture'
full_candidate=fixture.h.call('compile_candidate',fixture.db())
(ROOT/'database-candidate.conf').write_text(full_candidate)
parse_candidate=full_candidate.replace('= external {','= '+str(LIB)+' {').replace(
 'exec = /usr/local/lib/mavis/mavis_tacplus_ads.pl',
 'exec = '+sys.executable+' '+sys.executable+' '+str(backend)+' bound')
parse_path=ROOT/'database-candidate-isolated.conf';parse_path.write_text(parse_candidate)
rc,out=bounded([str(BIN),'-P',str(parse_path)])
(ROOT/'database-candidate-parse.log').write_text(out)
if rc!=0:raise RuntimeError(f'Complete candidate parser failed: {rc}: {out}')
results=[]
for fallback in (False,True):
 mode='fallback' if fallback else 'restricted'
 config=base.replace('FALLBACK','rule fallback { script { profile = allow permit } }' if fallback else '')
 path=ROOT/(mode+'.conf');path.write_text(config)
 rc,out=bounded([str(BIN),'-P',str(path)]);(ROOT/(mode+'-parse.log')).write_text(out)
 if rc!=0:raise RuntimeError(f'Native parser failed: {rc}: {out}')
 with (ROOT/(mode+'.log')).open('w') as log:
  proc=subprocess.Popen([str(BIN),'-D','-d','-1',str(path)],env=ENV,stdout=log,stderr=log,start_new_session=True)
  try:
   for attempt in range(40):
    try:
     with socket.create_connection(('127.0.0.1',PORT),timeout=.1):pass
     break
    except OSError:
     if proc.poll() is not None:raise RuntimeError('Native daemon exited')
     time.sleep(.05)
   users=['external','local','third','nonmember','ungrouped']
   for user in users:
    for kind in ('exec','command','auth'):
     expected=1 if fallback or user=='external' else (2 if kind=='auth' else 16)
     actual=request(user,kind)
     results.append(dict(mode=mode,user=user,request=kind,expected=expected,actual=actual,
        outcome='PASS' if actual['status']==expected else 'FAIL'))
  finally:
   try:os.killpg(proc.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:proc.wait(timeout=2)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
(ROOT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
(ROOT/'build.json').write_text(json.dumps(dict(binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),version=bounded([str(BIN),'-v']),limitations=['Synthetic backend, no live LDAP','Local build, not installed server binary']),indent=2))
print(json.dumps({'tests':len(results),'passed':sum(r['outcome']=='PASS' for r in results),'failed':sum(r['outcome']=='FAIL' for r in results)}))
raise SystemExit(any(r['outcome']!='PASS' for r in results))
