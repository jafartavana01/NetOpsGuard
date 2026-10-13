/* GUI-07: actual templates and shared scripts, synthetic HTTP, no native/PG claim.
   No evidence files generated. GUI_CHROMIUM selects the installed browser. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const server=spawn('python',['tests/gui07/preview.py'],{cwd:path.resolve(__dirname,'../..'),stdio:['ignore','ignore','pipe']});
let stderr='';server.stderr.on('data',d=>stderr+=d);
const origin='http://127.0.0.1:8771';
(async()=>{
 let browser; const checks=[], errors=[], writes=[];
 const check=(name,ok)=>{checks.push({name,passed:!!ok});if(!ok)throw Error(name);};
 try {
  for(let i=0;i<60;i++){try{await fetch(origin+'/radius/attributes');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));await page.route('https://**/*',r=>r.abort());
  let failures={},aborts=new Set(),delay={},savedGroup='g1';
  let candidate={applicable:true,has_changes:true,diff:'+ permitted change',diagnostics:[]};
  const attributes=Array.from({length:30},(_,i)=>({name:'Attribute-'+i,qualified_name:'Vendor:Attribute-'+i,code:i,value_type:'string',vendor:'Vendor',values:{}}));
  const go=async p=>{await page.goto(origin+p);await page.waitForTimeout(150);};
  await page.route('**/api/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(req.method()!=='GET')writes.push({path:p,body:req.postDataJSON()});
   if(delay[p])await new Promise(r=>setTimeout(r,delay[p]));
   if(aborts.has(p))return route.abort();
   if(failures[p])return route.fulfill({status:failures[p],json:{detail:'Synthetic rejected request'}});
   const data={
    '/api/config/candidate':candidate,
    '/api/radius/attributes':{available:true,attributes,vendors:['Vendor'],note:'Fixture dictionary'},
    '/api/tacacs-groups':[{id:'g1',name:'ops'}],'/api/devices':[{id:'d1',name:'R1'}],'/api/device-groups':[{id:'dg1',name:'edge'}],
    '/api/radius/policies':[{id:'rp1',name:'Scoped',description:'',priority:10,enabled:true,action:'permit',condition_group_id:savedGroup,condition_group_name:'ops',condition_device_id:'d1',condition_device_name:'R1',condition_device_group_id:'dg1',condition_device_group_name:'edge',condition_service_type:'Administrative-User',attributes:[{attribute:'Saved:Custom',value:'unchanged'}]}],
   };
   if(req.method()!=='GET'&&p.startsWith('/api/radius/policies'))return route.fulfill({json:{id:'rp1'}});
   return data[p]!==undefined?route.fulfill({json:data[p]}):route.continue();
  });
  await go('/radius/attributes');
  check('first page pagination',await page.locator('#attr-prev').isDisabled()&&await page.locator('#attr-next').isEnabled());
  await page.locator('#attr-next').click();check('last page pagination',await page.locator('#attr-prev').isEnabled()&&await page.locator('#attr-next').isDisabled());
  await page.locator('#filter-search').fill('no match');
  check('empty filters disable both pagination controls',await page.locator('#attr-prev').isDisabled()&&await page.locator('#attr-next').isDisabled());
  check('empty filters explicitly explained',(await page.locator('#attr-wrap').textContent()).includes('No attributes match'));
  await page.locator('#filter-search').fill('');check('clearing filters restores first page',await page.locator('#attr-prev').isDisabled()&&await page.locator('#attr-next').isEnabled());
  check('technical table keyboard scroll region',await page.locator('#attr-wrap').getAttribute('tabindex')==='0');
  failures['/api/radius/attributes']=403;await go('/radius/attributes');check('dictionary denied is not empty inventory',(await page.locator('#attr-wrap').textContent()).includes('Access denied'));check('dictionary error pagination disabled',await page.locator('#attr-next').isDisabled());failures={};

  await go('/radius/policies');await page.locator('[data-edit=rp1]').click();
  check('saved attribute absent from dictionary preserved',await page.locator('.rp-attr-name').inputValue()==='Saved:Custom');
  check('saved service type absent from dictionary preserved',await page.locator('#rp-service-type').inputValue()==='Administrative-User');
  check('dialog accessible label',await page.locator('#rp-modal-backdrop [role=dialog]').getAttribute('aria-labelledby')==='rp-modal-title');
  await page.locator('#rp-name').fill('Edited');page.once('dialog',d=>d.dismiss());await page.locator('#rp-cancel').click();check('dirty cancel can be declined',await page.locator('#rp-modal-backdrop').isVisible());
  const save=page.locator('#rp-form button[type=submit]');
  failures['/api/radius/policies/rp1']=403;await save.click();await page.waitForTimeout(120);
  check('denied save stays in editor',await page.locator('#rp-modal-backdrop').isVisible());check('denied save displays backend failure',(await page.locator('#rp-error').textContent()).includes('Access denied'));check('failed save never success toast',await page.locator('.toast-success').count()===0);
  failures={};aborts.add('/api/radius/policies/rp1');await save.click();await page.waitForTimeout(120);check('network save error visible',(await page.locator('#rp-error').textContent()).includes('Connection interrupted'));check('network failure reenables save',await save.isEnabled());aborts.clear();
  failures['/api/radius/policies/rp1']=409;await save.click();await page.waitForTimeout(120);check('blocked policy response retained',(await page.locator('#rp-error').textContent()).includes('Synthetic rejected'));failures={};
  delay['/api/radius/policies/rp1']=300;await save.click();await page.keyboard.press('Escape');check('busy save cannot close editor',await page.locator('#rp-modal-backdrop').isVisible());check('busy save disabled',await save.isDisabled());await page.waitForTimeout(350);
  check('confirmed save closes editor',!await page.locator('#rp-modal-backdrop').isVisible());
  const payload=writes.at(-1).body;check('save retains every loaded restriction',payload.condition_group_id==='g1'&&payload.condition_device_id==='d1'&&payload.condition_device_group_id==='dg1'&&payload.condition_service_type==='Administrative-User');check('save retains unknown dictionary attribute',payload.attributes[0].attribute==='Saved:Custom');delay={};
  failures['/api/tacacs-groups']=500;await go('/radius/policies');check('failed options disable create',await page.locator('#new-policy-btn').isDisabled());await page.locator('[data-edit=rp1]').click();check('failed options prevent edit',!await page.locator('#rp-modal-backdrop').isVisible());check('option failure visible',await page.locator('#admin-page-state').isVisible());failures={};
  savedGroup='deleted-group';await go('/radius/policies');await page.locator('[data-edit=rp1]').click();check('stale scope reference not converted to Any',await page.locator('#rp-group').inputValue()==='deleted-group');await page.locator('#rp-cancel').click();savedGroup='g1';

  await go('/tacacs/config');check('valid changed candidate offers Apply',await page.locator('#apply-btn').isEnabled());
  failures['/api/config/apply']=403;page.once('dialog',d=>d.accept());await page.locator('#apply-btn').click();await page.waitForTimeout(120);check('denied Apply never success',await page.locator('.toast-success').count()===0&&await page.locator('.toast-error').count()===1);failures={};
  aborts.add('/api/config/apply');page.once('dialog',d=>d.accept());await page.locator('#apply-btn').click();await page.waitForTimeout(120);check('interrupted Apply reports unknown outcome',(await page.locator('.toast-error').last().textContent()).includes('outcome is unknown'));check('unknown Apply cannot accidentally repeat',await page.locator('#apply-btn').isDisabled());aborts.clear();
  candidate={applicable:false,has_changes:true,diagnostics:[{protocol:'tacacs',policy_name:'Blocked',code:'scope.reference_missing',reason:'Missing group',path:'tree'}]};await go('/tacacs/config');check('blocked candidate never offers Apply',await page.locator('#apply-btn').count()===0);check('blocked diagnostic preserved',(await page.locator('#candidate-panel').textContent()).includes('scope.reference_missing'));
  candidate={applicable:true,has_changes:false,diff:'',diagnostics:[]};await go('/tacacs/config');check('unchanged candidate remains distinct',(await page.locator('#candidate-panel').textContent()).includes('Up to date'));
  aborts.add('/api/config/candidate');await go('/tacacs/config');check('candidate network error is not up-to-date',(await page.locator('#candidate-panel').textContent()).includes('Connection interrupted')&&await page.locator('#apply-btn').count()===0);aborts.clear();

  // Legacy AAA dialogs share one guarded cancellation path; feature handlers still close them.
  await go('/tacacs/users');await page.locator('#add-user-btn').click();
  await page.locator('#user-username').fill('unsaved-user');await page.keyboard.press('Escape');
  check('Escape keeps dirty editor behind confirmation',await page.locator('#user-modal-backdrop').isVisible()&&await page.locator('#unsaved-changes-modal-backdrop').isVisible());
  check('safe confirmation choice focused',await page.locator('#unsaved-changes-keep-editing-btn').evaluate(e=>e===document.activeElement));
  await page.keyboard.press('Escape');check('Escape on confirmation keeps edits',!await page.locator('#unsaved-changes-modal-backdrop').isVisible()&&await page.locator('#user-username').inputValue()==='unsaved-user');
  await page.locator('#user-cancel-btn').click();check('Cancel also protects dirty editor',await page.locator('#unsaved-changes-modal-backdrop').isVisible());
  await page.locator('#unsaved-changes-keep-editing-btn').click();await page.locator('#user-modal-close-btn').click();
  await page.locator('#unsaved-changes-discard-btn').click();check('explicit discard closes editor',!await page.locator('#user-modal-backdrop').isVisible());
  check('legacy dialog restores opener focus',await page.locator('#add-user-btn').evaluate(e=>e===document.activeElement));
  await page.locator('#add-user-btn').click();await page.locator('#user-form').evaluate(e=>e.setAttribute('aria-busy','true'));await page.keyboard.press('Escape');
  check('busy legacy dialog cannot be dismissed',await page.locator('#user-modal-backdrop').isVisible());
  await page.locator('#user-form').evaluate(e=>e.removeAttribute('aria-busy'));await page.keyboard.press('Escape');check('clean legacy dialog closes with Escape',!await page.locator('#user-modal-backdrop').isVisible());
  await page.evaluate(()=>{const wrap=document.createElement('div');wrap.id='test-ops-table';wrap.innerHTML='<table><thead><tr><th>Device</th></tr></thead><tbody><tr><td>R2</td></tr><tr><td>R1</td></tr></tbody></table>';document.querySelector('main').append(wrap);OpsUI.table(wrap.id);AAAPlatform.makeTableSortable(wrap.querySelector('table'));});
  await page.locator('#test-ops-table input').fill('missing');check('operations filter empty state visible',await page.locator('#test-ops-table .ops-table-empty').isVisible());
  check('operations empty filter disables pagination',await page.locator('#test-ops-table button:disabled').count()===2);
  await page.locator('#test-ops-table input').fill(' R1 ');check('operations filter trims whitespace',await page.locator('#test-ops-table tbody tr:visible').count()===1);
  await page.locator('#test-ops-table input').fill('');await page.locator('#test-ops-table th').focus();await page.keyboard.press('Enter');
  check('keyboard sorting announces direction',await page.locator('#test-ops-table th').getAttribute('aria-sort')==='ascending');check('keyboard sorting retains rows',(await page.locator('#test-ops-table tbody tr').first().textContent())==='R1');

  // Race real shell navigation using delayed HTML responses (not backend calls).
  await page.route('**/slow-page',async r=>{await new Promise(x=>setTimeout(x,450));await r.fulfill({contentType:'text/html',body:'<title>Old</title><div id="view-root"><h1>Stale page</h1></div>'});});
  await page.evaluate(()=>{for(const [id,href] of [['slow','/slow-page'],['fast','/radius/attributes']]){const a=document.createElement('a');a.id=id;a.href=href;a.textContent=id;document.body.append(a);}document.getElementById('slow').click();document.getElementById('fast').click();});
  await page.waitForTimeout(650);check('latest navigation wins delayed response',page.url().endsWith('/radius/attributes')&&(await page.locator('h1').textContent())==='RADIUS Attributes');
  check('navigation focuses page heading',await page.locator('h1').evaluate(e=>e===document.activeElement));
  await page.route('**/restricted-page',r=>r.fulfill({status:303,headers:{location:'/radius/policies'}}));
  await page.evaluate(()=>{const a=document.createElement('a');a.href='/restricted-page';document.body.append(a);a.click();});await page.waitForTimeout(350);
  check('server redirect URL and view agree',page.url().endsWith('/radius/policies')&&await page.locator('#rp-wrap').count()===1);
  await page.goBack();await page.waitForTimeout(350);check('back restores actual view',await page.locator('#attr-wrap').count()===1);
  await page.goForward();await page.waitForTimeout(350);check('forward restores actual view',await page.locator('#rp-wrap').count()===1);
  await page.evaluate(()=>AAAWorkspace.details('Scope details', [['Scope','ops AND R1']]));await page.goBack();await page.waitForTimeout(350);check('history navigation cleans detail drawer',await page.locator('.gui-dialog').count()===0&&!await page.locator('.app-shell').evaluate(e=>e.inert));await page.goForward();await page.waitForTimeout(350);
  await page.reload();await page.waitForTimeout(150);check('refresh initializes once',await page.locator('#rp-form .admin-form-state').count()===1);

  await page.evaluate(()=>{AAAPlatform.toast('First');AAAPlatform.toast('Failure','error');});
  check('notifications have status and alert roles',await page.locator('#notification-stack [role=status]').count()===1&&await page.locator('#notification-stack [role=alert]').count()===1);
  const boxes=await page.locator('.toast').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom};}));check('notifications do not overlap',boxes[0].bottom<=boxes[1].top);
  await page.locator('.toast-error button').click();check('error notification dismissible',await page.locator('.toast-error').count()===0);
  failures['/api/auth/logout']=500;await page.locator('#logout-btn').click();await page.waitForTimeout(120);check('failed logout does not pretend signed out',page.url().endsWith('/radius/policies')&&await page.locator('#logout-btn').isEnabled());check('failed logout explains uncertainty',(await page.locator('.toast-error').textContent()).includes('Could not confirm'));failures={};

  for(const width of [360,390,768,1366,1920]){
   await page.setViewportSize({width,height:900});await go('/radius/attributes');
   check('attributes no page overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   check('table still readable '+width,await page.locator('#attr-wrap table').evaluate(e=>e.getBoundingClientRect().width>=600));
   await go('/radius/policies');await page.locator('[data-edit=rp1]').click();
   check('dialog fits viewport '+width,await page.locator('#rp-modal-backdrop .modal').evaluate(e=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1;}));
   await save.focus();await page.keyboard.press('Tab');check('dialog traps forward focus '+width,await page.locator('#rp-modal-close').evaluate(e=>e===document.activeElement));
   await page.keyboard.press('Escape');check('escape closes clean dialog '+width,!await page.locator('#rp-modal-backdrop').isVisible());
  }
  await page.setViewportSize({width:390,height:800});await page.locator('.mobile-nav-toggle').click();
  await page.locator('.sidebar a:visible').last().focus();
  // Select the actual last focusable control, including footer controls.
  await page.locator('.sidebar').evaluate(el=>[...el.querySelectorAll('a[href],button:not(:disabled),input:not(:disabled)')].filter(e=>e.getClientRects().length).at(-1).focus());
  await page.keyboard.press('Tab');check('mobile navigation traps focus',await page.locator('.sidebar').evaluate(el=>el.contains(document.activeElement)));
  await page.keyboard.press('Escape');check('mobile navigation restores toggle focus',await page.locator('.mobile-nav-toggle').evaluate(e=>e===document.activeElement));
  check('no uncaught browser errors',errors.length===0);
 } finally {if(browser)await browser.close();server.kill();console.log(JSON.stringify({passed:checks.filter(x=>x.passed).length,failed:checks.filter(x=>!x.passed).length,checks,errors},null,2));}
})().catch(e=>{console.error(e,stderr);process.exitCode=1;});
