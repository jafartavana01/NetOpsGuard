/* GUI-02 Operations Center. GET-only presentation; API security stays authoritative. */
(function () {
  'use strict';
  const count = value => Number.isInteger(value) && value >= 0;
  const obj = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const list = Array.isArray;
  const counts = value => obj(value) && ['success','failure','unknown'].every(k => count(value[k]));
  const endpoints = {
    system: {url:'/api/system/status', valid:d=>obj(d)&&obj(d.services)&&typeof d.database==='string'},
    devices: {url:'/api/devices', permission:'devices:view', href:'/tacacs/devices', valid:d=>list(d)&&d.every(x=>obj(x)&&typeof x.enabled==='boolean')},
    health: {url:'/api/tacacs-accounting/health?hours=24&limit=2000', permission:'accounting:view', href:'/tacacs/aaa-health', valid:d=>obj(d)&&count(d.permit_count)&&count(d.non_permit_count)&&count(d.distinct_users)&&list(d.hourly_activity)&&d.hourly_activity.every(p=>count(p.count)&&Number.isFinite(Date.parse(p.hour)))},
    sessions: {url:'/api/tacacs-accounting/sessions?active_only=true&limit=2000', permission:'accounting:view', href:'/tacacs/sessions', valid:d=>obj(d)&&count(d.active_count)&&list(d.sessions)},
    auth: {url:'/api/tacacs-accounting/access-events?kind=authentication&limit=10', window:true, permission:'accounting:view', href:'/tacacs/access-events', valid:d=>obj(d)&&counts(d.counts)&&list(d.rows)&&d.rows.every(obj)},
    decisions: {url:'/api/tacacs-accounting/access-events?kind=all&limit=10', window:true, permission:'accounting:view', href:'/tacacs/access-events', valid:d=>obj(d)&&counts(d.counts)&&list(d.rows)&&d.rows.every(obj)},
    security: {url:'/api/security/dashboard', permission:'security:view', href:'/security/overview', valid:d=>obj(d)&&count(d.devices_audited)&&count(d.failed_checks)&&list(d.severity_counts)&&d.severity_counts.every(x=>typeof x.severity==='string'&&count(x.count))&&(d.average_score===null||(Number.isFinite(d.average_score)&&d.average_score>=0&&d.average_score<=100))},
    ncm: {url:'/api/ncm/overview', permission:'ncm:view', href:'/ncm/overview', valid:d=>obj(d)&&['total_devices','devices_with_recent_backup','devices_with_failed_backup','devices_never_backed_up','total_configurations','configurations_changed_recently','active_jobs'].every(k=>count(d[k]))&&list(d.recent_changes)},
    drift: {url:'/api/ncm/drift', permission:'ncm:view', href:'/ncm/drift', valid:d=>obj(d)&&['total','in_sync','drifted','no_baseline','no_snapshot','baseline_gone','coverage_gaps'].every(k=>count(d[k]))},
    candidate: {url:'/api/config/candidate', permission:'config:view', href:'/tacacs/config', valid:d=>obj(d)&&typeof d.applicable==='boolean'&&typeof d.has_changes==='boolean'&&list(d.diagnostics)}
  };
  function node(tag, cls, text) {
    const el=document.createElement(tag); if(cls)el.className=cls;
    if(text!==undefined)el.textContent=String(text); return el;
  }
  const badge=(text,tone='neutral')=>node('span','badge badge-'+tone,text);
  const timeText=t=>Number.isFinite(Date.parse(t))?new Date(t).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}):'Unknown';
  function mount(root) {
    if(!root||root.dataset.mounted)return;
    root.dataset.mounted='true';
    let capabilities;try{capabilities=JSON.parse(root.dataset.capabilities||'{}');}catch{capabilities={};}
    let alive=true,busy=false,chart=null,chartVersion=0,directory={state:'idle'},chartPromise=null;
    const controllers=new Set(),state={};
    const find=id=>root.querySelector('#ops-'+id);
    const can=key=>capabilities[key]===true;
    const destination=href=>[...document.querySelectorAll('#sidebar-nav a.nav-item')].some(a=>a.getAttribute('href')===href);
    const permitted=spec=>!spec.permission||(can(spec.permission)&&destination(spec.href));
    const link=(label,href,permission)=> {
      if(!destination(href)||(permission&&!can(permission)))return null;
      const a=node('a','ops-link',label+' →');a.href=href;return a;
    };
    const append=(parent,...children)=>children.filter(Boolean).forEach(child=>parent.append(child));
    const button=(label,handler,cls='btn-secondary btn-small')=>{const b=node('button',cls,label);b.type='button';b.addEventListener('click',handler);return b;};
    const data=key=>state[key]?.status==='ok'?state[key].data:null;
    const available=key=>state[key]?.status==='ok';
    const textState=key=>({loading:'Loading…',expired:'Session expired — sign in again',restricted:'Not available for this account',forbidden:'Permission denied',unlicensed:'Not included in this license',disabled:'Source not available',error:'Unable to load this source'})[state[key]?.status]||'Unknown';
    function placeholder(key,title) {
      const box=node('div',state[key]?.status==='loading'?'loading-inline':'ops-unavailable');
      if(state[key]?.status==='loading'){const spinner=node('span','spinner');spinner.setAttribute('aria-hidden','true');box.setAttribute('role','status');box.append(spinner);}
      box.append(node('p','',title+' — '+textState(key)+'.'));
      if(state[key]?.status==='error')box.append(button('Retry',()=>refreshOne(key)));
      return box;
    }
    const empty=(title,description,action)=>{const e=node('div','empty-state');append(e,node('h3','',title),node('p','',description),action);return e;};
    function stat(parent,label,value,tone) {const row=node('div','ops-stat-line');append(row,node('span','',label),node('strong',tone?'text-'+tone:'',value));parent.append(row);}
    async function request(url,valid) {
      const controller=new AbortController();controllers.add(controller);
      const timeout=setTimeout(()=>controller.abort(),20000);
      try {
        const response=await AAAPlatform.authedFetch(url,{signal:controller.signal});
        if(!response.ok)return {status:response.status===401?'expired':response.status===403?'forbidden':response.status===402?'unlicensed':response.status===404?'disabled':'error'};
        const value=await response.json();if(!valid(value))return {status:'error'};
        return {status:'ok',data:value};
      }catch(_){return {status:'error'};}
      finally{clearTimeout(timeout);controllers.delete(controller);}
    }
    async function load(key) {
      const spec=endpoints[key];
      if(!permitted(spec)){state[key]={status:'restricted'};render(key);return;}
      state[key]={status:'loading'};render(key);
      const url=spec.url+(spec.window?'&since='+encodeURIComponent(new Date(Date.now()-86400000).toISOString()):'');
      const result=await request(url,spec.valid);
      if(!alive)return;state[key]=result;render(key);
    }
    function metric(label,value,sub,href,permission) {
      const a=link(label,href,permission);const card=a||node('div');card.className='card ops-metric'+(a?' card--interactive':'');card.replaceChildren();
      append(card,node('span','ops-metric-label',label),node('strong','metric-value',value),node('p','',sub));return card;
    }
    function renderMetrics() {
      const devices=data('devices'),h=data('health'),sessions=data('sessions'),auth=data('auth'),security=data('security');
      const total=auth?auth.counts.success+auth.counts.failure:0;
      find('metrics').replaceChildren(
        metric('Devices',devices?devices.length:'—',devices?devices.filter(d=>d.enabled).length+' enabled':textState('devices'),available('devices')?'/tacacs/devices':'','devices:view'),
        metric('AAA users seen',h?h.distinct_users:'—',h?'Command records · last 24 hours, sampled':textState('health'),available('health')?'/tacacs/aaa-health':'','accounting:view'),
        metric('Active sessions',sessions?sessions.active_count:'—',sessions?'Correlated from accounting log tail':textState('sessions'),available('sessions')?'/tacacs/sessions':'','accounting:view'),
        metric('Authentication success',auth&&total?(100*auth.counts.success/total).toFixed(1)+'%':'—',auth?(total?total+' known outcomes · '+auth.counts.unknown+' unknown':'No known authentication outcomes')+' · 24h sample':textState('auth'),available('auth')?'/tacacs/access-events':'','accounting:view'),
        metric('Failed security checks',security&&security.devices_audited?security.failed_checks:'—',security?(security.devices_audited?security.devices_audited+' devices audited':'No completed audits'):textState('security'),available('security')?'/security/findings':'','security:view')
      );
    }
    function service(unit) {
      const sys=data('system'),value=sys?.services?.[unit];
      if(!sys)return {label:'Unknown',tone:'neutral',detail:textState('system')};
      if(!value||value.error)return {label:'Unknown',tone:'neutral',detail:'Service status unavailable'};
      if(value.active_state==='active')return {label:'Running',tone:'success',detail:unit};
      if(['failed','inactive'].includes(value.active_state))return {label:value.active_state==='failed'?'Failed':'Inactive',tone:value.active_state==='failed'?'danger':'warning',detail:unit};
      return {label:value.active_state||'Unknown',tone:'neutral',detail:unit};
    }
    function healthItem(title,label,tone,detail,action) {
      const e=node('div','ops-health-item');append(e,node('h3','',title),badge(label,tone),node('p','',detail),action);return e;
    }
    function renderHealth() {
      const tac=service('tac-plus-ng.service'),sys=data('system');
      const dirAllowed=can('directory:check')&&destination('/platform/active-directory')&&!['forbidden','unlicensed','expired'].includes(directory.state);
      const dirButton=dirAllowed?button(directory.state==='loading'?'Checking…':'Check directory',checkDirectory,'btn-ghost'):null;
      if(dirButton)dirButton.disabled=directory.state==='loading';
      find('health').replaceChildren(
        healthItem('TACACS+ service',tac.label,tac.tone,'Process status',link('Inspect','/tacacs/aaa-health','accounting:view')),
        healthItem('Directory',directory.state==='loading'?'Checking':directory.state==='ok'?(directory.data.success?'Check passed':'Check failed'):'Unknown',directory.state==='ok'?(directory.data.success?'success':'warning'):'neutral',(directory.checked?'Last attempt '+directory.checked+'. ':'')+({forbidden:'Permission denied',expired:'Session expired',error:'Check could not complete',unlicensed:'Not included in this license'}[directory.state]||(directory.state==='ok'?directory.data.message:dirAllowed?'Refreshes every 60 seconds':'No accessible directory check')),dirButton),
        healthItem('Database',sys?(sys.database==='connected'?'Connected':'Unavailable'):'Unknown',sys?(sys.database==='connected'?'success':'danger'):'neutral','Management database'),
        healthItem('Configuration management',available('ncm')?'Available':'Unknown',available('ncm')?'info':'neutral',available('ncm')?'Summary API responded':textState('ncm'),available('ncm')?link('Open NCM','/ncm/overview','ncm:view'):null),
        healthItem('Security Center',available('security')?'Available':'Unknown',available('security')?'info':'neutral',available('security')?'Summary API responded':textState('security'),available('security')?link('Open Security','/security/overview','security:view'):null)
      );
    }
    async function checkDirectory() {
      if(!alive||directory.state==='loading'||!can('directory:check')||!destination('/platform/active-directory')||['forbidden','unlicensed','expired'].includes(directory.state))return;
      directory={...directory,state:'loading'};renderHealth();
      const result=await request('/api/ad-settings/health',d=>obj(d)&&typeof d.success==='boolean'&&typeof d.message==='string');
      if(!alive)return;directory={state:result.status,data:result.data,checked:new Date().toLocaleTimeString()};renderHealth();renderAttention();
    }
    function chartsLoaded() {
      if(window.Chart)return Promise.resolve();
      if(chartPromise)return chartPromise;
      chartPromise=new Promise((resolve,reject)=>{
        const s=document.createElement('script');let finished=false;
        const finish=ok=>{if(finished)return;finished=true;clearTimeout(timer);if(ok&&window.Chart)resolve();else{s.remove();chartPromise=null;reject(new Error('Chart unavailable'));}};
        const timer=setTimeout(()=>finish(false),10000);
        s.src='https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js';s.onload=()=>finish(true);s.onerror=()=>finish(false);document.head.append(s);
      });return chartPromise;
    }
    async function renderActivity() {
      const version=++chartVersion,wrap=find('activity'),h=data('health');if(chart){chart.destroy();chart=null;}
      if(!h){wrap.replaceChildren(placeholder('health','AAA activity'));return;}
      const points=h.hourly_activity,total=points.reduce((n,p)=>n+p.count,0);
      if(!total){const w=h.activity_window;wrap.replaceChildren(empty('No command authorization activity',w?`No timestamped command records in the last ${w.hours} hours of the sampled log. ${w.outside_window} records outside the window; ${w.unknown_timestamp} with unknown timestamps.`:'No timestamped command records in the last 24 hours of the bounded log sample.'));return;}
      const canvas=node('canvas');canvas.setAttribute('role','img');canvas.setAttribute('aria-label',total+' command authorization records across '+points.length+' hourly buckets, last 24 hours, sampled log.');
      wrap.replaceChildren(canvas);
      try{await chartsLoaded();}catch(_){if(alive&&version===chartVersion)wrap.replaceChildren(empty('Chart unavailable',total+' command authorization records in the 24-hour sample.'),button('Retry chart',renderActivity));return;}
      if(!alive||version!==chartVersion)return;
      const theme=NetOpsUI.chartOptions();
      chart=new Chart(canvas,{type:'bar',data:{labels:points.map(p=>new Date(p.hour).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false})),datasets:[{label:'Command authorization records',data:points.map(p=>p.count),backgroundColor:theme.palette.info,borderRadius:3,maxBarThickness:20}]},options:{responsive:true,maintainAspectRatio:false,animation:false,plugins:{legend:{display:false},tooltip:{displayColors:false}},scales:{x:{grid:{display:false},ticks:{color:theme.color,font:theme.font,maxRotation:0,maxTicksLimit:8}},y:{beginAtZero:true,grid:{color:theme.borderColor},ticks:{color:theme.color,font:theme.font,precision:0}}}}});
    }
    function renderResults() {
      const wrap=find('results'),h=data('health');if(!h){wrap.replaceChildren(placeholder('health','Authorization results'));return;}
      const total=h.permit_count+h.non_permit_count;
      if(!total){wrap.replaceChildren(empty('No authorization outcomes','No non-empty command decision results in the last 24 hours of the sampled log.'));return;}
      const heading=node('div','ops-outcome-total');append(heading,node('strong','',total.toLocaleString()),node('span','','recorded results'));
      const bar=node('div','ops-outcome-bar');bar.setAttribute('aria-hidden','true');
      for(const value of [h.permit_count,h.non_permit_count]){const part=node('span');part.style.width=(100*value/total)+'%';bar.append(part);}
      const facts=node('div','ops-facts');
      for(const [label,value,tone] of [['Permit',h.permit_count,'success'],['Non-permit',h.non_permit_count,'danger']]){const item=node('div');append(item,node('strong','text-'+tone,value.toLocaleString()),node('span','text-muted',label+' · '+(100*value/total).toFixed(1)+'%'));facts.append(item);}
      wrap.replaceChildren(heading,bar,facts,node('p','ops-footnote text-muted','Non-permit includes every non-empty result other than permit. This is not authentication success.' ));
      append(wrap,link('Inspect AAA health','/tacacs/aaa-health','accounting:view'));
    }
    function renderSecurity() {
      const wrap=find('security'),d=data('security');if(!d){wrap.replaceChildren(placeholder('security','Security posture'));return;}
      if(!d.devices_audited){wrap.replaceChildren(empty('No security audits yet','Run an audit from Security Center to establish device posture.',link('Open Security Center','/security/overview','security:view')));return;}
      const score=node('div','ops-score'),value=node('div','ops-score-value',d.average_score===null?'—':d.average_score);value.append(node('span','',' / 100'));
      append(score,value,node('p','content-sub',d.devices_audited+' devices · latest completed audits'));
      const facts=node('div','cluster');
      for(const sev of ['critical','high','medium','low','info']){const row=d.severity_counts.find(s=>s.severity===sev);facts.append(badge((row?row.count:0)+' '+sev,sev==='critical'||sev==='high'?'danger':sev==='medium'?'warning':'neutral'));}
      wrap.replaceChildren(score,facts,node('p','ops-footnote text-muted','Severity counts reflect failed checks. No audit is not the same as a clean audit.'));
      append(wrap,link('Open Security Center','/security/overview','security:view'));
    }
    function renderNcm() {
      const wrap=find('ncm'),d=data('ncm');if(!d){wrap.replaceChildren(placeholder('ncm','Configuration posture'));return;}
      if(!d.total_devices){wrap.replaceChildren(empty('No enabled devices','Add a device before establishing configuration backup coverage.',link('Open NCM','/ncm/overview','ncm:view')));return;}
      const facts=node('div','ops-stat-list');
      stat(facts,'Successful backup within 48 hours',d.devices_with_recent_backup+' / '+d.total_devices,'success');
      stat(facts,'No backup job history',d.devices_never_backed_up,d.devices_never_backed_up?'warning':null);
      stat(facts,'Latest backup job failed',d.devices_with_failed_backup,d.devices_with_failed_backup?'danger':null);
      stat(facts,'Snapshots added within 48 hours',d.configurations_changed_recently);
      wrap.replaceChildren(facts);
      if(!d.total_configurations)wrap.append(node('p','content-sub','No configuration backups stored yet.'));
      if(d.recent_changes.length){const recent=node('details','context-help');recent.append(node('summary','','Recent snapshots'));for(const c of d.recent_changes.slice(0,3)){const row=node('div','ops-snapshot');append(row,node('span','',c.device_name+' · version '+c.version_number),node('time','',Number.isFinite(Date.parse(c.created_at))?new Date(c.created_at).toLocaleString():'Time unavailable'));recent.append(row);}wrap.append(recent);}
      append(wrap,link('Open backups','/ncm/overview','ncm:view'));
    }
    function renderDrift() {
      const wrap=find('drift'),d=data('drift');wrap.className='ops-subsection';
      if(!d){wrap.replaceChildren(placeholder('drift','Baseline comparison'));return;}
      wrap.replaceChildren();
      stat(wrap,'Archived running configuration matches baseline',d.in_sync);
      stat(wrap,'Archived running configuration differs',d.drifted,d.drifted?'warning':null);
      stat(wrap,'Coverage gaps',d.coverage_gaps,d.coverage_gaps?'warning':null);
      append(wrap,link('Inspect drift','/ncm/drift','ncm:view'));
    }
    function renderRecent() {
      const wrap=find('recent');wrap.replaceChildren();
      for(const key of ['auth','decisions'])if(!available(key))wrap.append(placeholder(key,key==='auth'?'Authentication':'Authorization'));
      const rows=[...(data('auth')?.rows||[]).map(r=>({...r,eventType:'authentication'})),...(data('decisions')?.rows||[]).map(r=>({...r,eventType:r.is_login?'session authorization':'command authorization'}))].sort((a,b)=>(Date.parse(b.timestamp)||0)-(Date.parse(a.timestamp)||0)).slice(0,8);
      if(!rows.length&&available('auth')&&available('decisions'))wrap.append(empty('No recent AAA events','Authentication and authorization records from the sampled last 24 hours will appear here.'));
      for(const r of rows){const row=node('article','ops-event'),time=node('time','',timeText(r.timestamp));if(Number.isFinite(Date.parse(r.timestamp))){time.dateTime=r.timestamp;time.title=new Date(r.timestamp).toLocaleString();}
        const content=node('div');append(content,node('div','ops-event-type',r.eventType),node('div','technical',(r.user||'Unknown user')+' → '+(r.device||'Unknown device')));if(r.command)content.append(node('span','technical',r.command));
        const isAuth=r.eventType==='authentication',positive=isAuth?r.outcome==='success':String(r.result).toLowerCase()==='permit';
        const known=isAuth?['success','failure'].includes(r.outcome):typeof r.result==='string'&&r.result.trim().length>0;
        append(row,time,content,badge(!known?'Unknown':positive?(isAuth?'Success':'Permit'):(isAuth?'Failure':'Non-permit'),!known?'neutral':positive?'success':'danger'));wrap.append(row);
      }
      if(available('auth')||available('decisions'))append(wrap,link('View all access events','/tacacs/access-events','accounting:view'));
    }
    function renderAttention() {
      const wrap=find('attention');wrap.replaceChildren();const items=[];
      const add=(severity,message,href,permission,details)=>items.push({severity,message,href,permission,details});
      const sys=data('system');let systemIncomplete=false;
      if(sys){for(const [unit,label] of [['tac-plus-ng.service','TACACS+ service'],['aaa-platform.service','NetOpsGuard API service']]){const s=service(unit);if(!['Running','Failed','Inactive'].includes(s.label))systemIncomplete=true;if(s.label==='Failed'||s.label==='Inactive')add(s.label==='Failed'?'Critical':'Warning',label+' is '+s.label.toLowerCase());}
        if(sys.database!=='connected')add('Critical','Management database connectivity check failed.');}
      const candidate=data('candidate');
      if(candidate&&!candidate.applicable)add('Critical','AAA configuration is blocked. Deployed configuration is unchanged.','/tacacs/config','config:view',candidate.diagnostics);
      else if(candidate?.has_changes)add('Info','A valid AAA candidate has unapplied changes.','/tacacs/config','config:view');
      const security=data('security');
      if(security)for(const sev of ['critical','high']){const n=security.severity_counts.find(x=>x.severity===sev)?.count||0;if(n)add(sev==='critical'?'Critical':'High',n+' '+sev+' failed security checks in latest device audits.','/security/findings','security:view');}
      const ncm=data('ncm'),drift=data('drift');
      if(ncm?.devices_with_failed_backup)add('Warning',ncm.devices_with_failed_backup+(ncm.devices_with_failed_backup===1?' device has':' devices have')+' a failed latest backup job.','/ncm/jobs','ncm:view');
      if(ncm?.devices_never_backed_up)add('Warning',ncm.devices_never_backed_up+(ncm.devices_never_backed_up===1?' enabled device has':' enabled devices have')+' no backup job history.','/ncm/overview','ncm:view');
      if(drift?.drifted)add('Warning',drift.drifted+(drift.drifted===1?' archived running configuration differs':' archived running configurations differ')+' from baseline.','/ncm/drift','ncm:view');
      if(data('auth')?.counts.failure)add('Warning',data('auth').counts.failure+' authentication failures in the 24-hour log sample.','/tacacs/access-events','accounting:view');
      if(directory.state==='ok'&&!directory.data.success)add('Warning','Directory check: '+directory.data.message,'/platform/active-directory','directory:check');
      if(directory.state==='error')add('Warning','Directory connectivity check could not complete.','/platform/active-directory','directory:check');
      const rank={Critical:0,High:1,Warning:2,Info:3};items.sort((a,b)=>rank[a.severity]-rank[b.severity]);
      find('attention-count').textContent=items.length+' observations';
      for(const item of items){const row=node('article','ops-attention-item'),body=node('div');append(body,node('p','',item.message),item.href?link('Inspect',item.href,item.permission):null);
        if(item.details?.length){const details=node('details','context-help');details.append(node('summary','',item.details.length+' scope diagnostics'));for(const d of item.details)details.append(node('p','ops-diag',(d.protocol||'')+': '+(d.policy_name||'Policy')+' — '+(d.reason||'Invalid scope')+' · '+(d.path||'')+' · '+(d.code||'')+(d.object_id?' · '+d.object_id:'')));body.append(details);}
        append(row,badge(item.severity,['Critical','High'].includes(item.severity)?'danger':item.severity==='Warning'?'warning':'info'),body);wrap.append(row);}
      const checked=['system','security','ncm','drift','candidate','auth'],pending=checked.some(k=>state[k]?.status==='loading'),unavailable=systemIncomplete||checked.some(k=>state[k]?.status!=='ok');
      if(!items.length)wrap.append(empty(pending?'Checking observations…':'No observations from available sources',unavailable?'Coverage is partial. Restricted or unavailable sources are not an all-clear.':'Based on the current sampled logs and stored snapshots.'));
      else if(unavailable)wrap.append(node('p','ops-footnote text-muted','Coverage is partial: some sources are restricted, loading or unavailable.'));
    }
    function renderBuild() {
      const wrap=find('build'),d=data('system');if(!d){wrap.replaceChildren(placeholder('system','Service and build details'));return;}
      const dl=node('dl','ops-tech-grid');
      for(const [unit,label] of [['tac-plus-ng.service','TACACS+ Service'],['aaa-platform.service','NetOpsGuard API']]){append(dl,node('dt','',label),node('dd','technical',unit+' · '+service(unit).label));}
      append(dl,node('dt','','Database'),node('dd','',d.database==='connected'?'Connected':'Unavailable'),node('dt','','Status checked'),node('dd','',d.checked_at?new Date(d.checked_at).toLocaleString():'Not supplied'));
      for(const [key,value] of Object.entries({...d.build_info,operating_system:d.os})){if(value==null)continue;append(dl,node('dt','',key.replaceAll('_',' ')),node('dd','technical',typeof value==='object'?JSON.stringify(value):value));}
      wrap.replaceChildren(dl);
    }
    function renderActions() {
      const wrap=find('actions');wrap.replaceChildren();
      const actions=[['Add device','/tacacs/devices','devices:write','devices'],['Run security audit','/security/overview','security:audit','security'],['Backup configurations','/ncm/overview','ncm:backup','ncm'],['Run command','/network-ops/jobs','network_ops:execute',null],['Scan network','/tacacs/devices','devices:write','devices'],['Manage policies','/tacacs/policies','policies:write',null]];
      for(const [label,href,permission,source] of actions){const read=permission==='network_ops:execute'?'network_ops:view':permission==='policies:write'?'policies:view':null;
        if(!can(permission)||(read&&!can(read))||(source&&!available(source)))continue;
        const a=link(label,href,permission);if(a){a.textContent=label;a.className='btn-secondary btn-small';wrap.append(a);}}
      if(!wrap.children.length)wrap.append(node('span','content-sub','No available action shortcuts for this account.'));
    }
    function render(key) {
      if(!alive)return;renderMetrics();renderHealth();renderAttention();renderActions();
      if(key==='health'){renderActivity();renderResults();}
      if(key==='auth'||key==='decisions')renderRecent();
      if(key==='security')renderSecurity();if(key==='ncm')renderNcm();if(key==='drift')renderDrift();if(key==='system')renderBuild();
    }
    function updateStamp() {
      const denied=Object.values(state).filter(s=>s.status==='restricted'||s.status==='forbidden'||s.status==='unlicensed'||s.status==='disabled').length;
      const failed=Object.values(state).filter(s=>s.status==='error').length;
      find('updated').textContent='Refresh completed '+new Date().toLocaleTimeString()+(failed?' · '+failed+' source errors':'')+(denied?' · limited access':'');
    }
    async function refreshOne(key) {if(busy||!alive)return;busy=true;find('refresh').disabled=true;try{await load(key);if(alive)updateStamp();}finally{busy=false;if(alive)find('refresh').disabled=false;}}
    async function refresh() {
      if(busy||!alive)return;busy=true;find('refresh').disabled=true;find('refresh').setAttribute('aria-busy','true');find('updated').textContent='Refreshing available sources…';
      try{await Promise.allSettled(Object.keys(endpoints).map(load));if(alive)updateStamp();}
      finally{busy=false;if(alive){find('refresh').disabled=false;find('refresh').removeAttribute('aria-busy');}}
    }
    const directoryTimer=setInterval(checkDirectory,60000);
    AAAPlatform.onViewLeave(()=>{alive=false;clearInterval(directoryTimer);chartVersion++;controllers.forEach(c=>c.abort());if(chart)chart.destroy();});
    find('refresh').addEventListener('click',refresh);refresh();checkDirectory();
  }
  window.NetOpsDashboard={mount};
})();
