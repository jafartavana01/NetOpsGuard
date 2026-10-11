/* Browser checks use real Jinja/JS and synthetic HTTP; not live AAA certification. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const {fixtures}=require('./fixtures.cjs');
const root=path.resolve(__dirname,'../..'),out=process.env.GUI03_EVIDENCE||path.join(root,'docs/gui03/evidence');
fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
const server=spawn(process.env.GUI_PYTHON||'python',['tests/gui03/preview.py'],{cwd:root,stdio:['ignore','ignore','pipe']});
let serverError='';server.stderr.on('data',d=>serverError+=d);
(async()=>{let browser;const checks=[],errors=[],requests=[],shots=[];
 const check=(name,passed)=>{checks.push({name,passed:!!passed});if(!passed)throw Error(name);};
 try{
  for(let i=0;i<70;i++){try{await fetch('http://127.0.0.1:8767/tacacs/accounting');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true,executablePath:process.env.GUI_CHROMIUM});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://**/*',r=>r.abort());
  let data=fixtures(),status={};
  await page.route('**/api/**',async route=>{
   const req=route.request(),u=new URL(req.url());requests.push({path:u.pathname,query:u.search,method:req.method()});
   if(u.pathname.endsWith('/export'))return route.fulfill({contentType:'text/csv',body:'user,result\noperator,permit\n'});
   if(u.pathname.includes('group-members'))return route.fulfill({json:{results:[{username:'directory.operator',display_name:'Directory Operator'}],error:null}});
   if(Object.hasOwn(data,u.pathname))return route.fulfill({status:status[u.pathname]||200,json:data[u.pathname]});
   return route.continue();
  });
  const go=async name=>{await page.goto('http://127.0.0.1:8767/tacacs/'+name);await page.waitForTimeout(350);};
  const shot=async name=>{const file=name+'.png';await page.waitForTimeout(250);await page.screenshot({path:path.join(out,'screenshots',file),fullPage:true,animations:'disabled'});shots.push(file);};
  await go('accounting');await page.locator('#accounting-table-wrap tbody tr').first().waitFor();
  check('accounting permit green check-circle',await page.locator('#accounting-table-wrap .aaa-success svg circle').count()===1);
  check('accounting deny red x-circle',await page.locator('#accounting-table-wrap .aaa-danger').innerText()==='Denied');
  check('accounting unsupported/auth success neutral',await page.locator('#accounting-table-wrap .aaa-neutral').count()===2);
  await shot('accounting-outcomes-1440');
  await page.locator('#filter-result').fill('deny');await page.locator('#filter-user').fill('operator');await page.locator('#filter-device').fill('R1');await page.locator('#filter-search').fill('show');
  await page.locator('#filter-since').fill('2026-10-10T12:00');await page.locator('#filter-until').fill('2026-10-10T16:00');
  await page.locator('#apply-filters-btn').click();await page.waitForTimeout(150);
  const q=requests.filter(r=>r.path==='/api/tacacs-accounting').at(-1).query;
  check('accounting filter query preserved',['result=deny','user=operator','device=R1','search=show','since=','until='].every(x=>q.includes(x)));
  await page.locator('#export-btn').click();await page.waitForTimeout(100);
  check('CSV export uses identical filters',requests.findLast(r=>r.path.endsWith('/export')).query===q);
  await page.locator('[data-record="1"]').click();check('raw evidence drawer',(await page.locator('.gui-drawer').innerText()).includes('SYNTHETIC accounting record: deny'));await page.keyboard.press('Escape');
  await page.locator('#clear-filters-btn').click();await page.waitForTimeout(150);check('clear filters removes query',requests.filter(r=>r.path==='/api/tacacs-accounting').at(-1).query==='');
  await page.locator('.aaa-table-tools input').fill('does-not-exist');check('loaded row search empty state',await page.locator('#accounting-table-wrap > .empty-state').isVisible());
  await go('policies');await page.locator('[data-scope="p2"]').waitFor();
  check('policy headings redesigned',(await page.locator('#policies-table-wrap thead').textContent()).includes('Who'));
  check('tree preserves OR in overview',(await page.locator('#policies-table-wrap').innerText()).includes('Device = R1 OR Device group = edge'));
  check('external authority visible in tree summary',(await page.locator('#policies-table-wrap').innerText()).includes('[EXTERNAL]'));
  await page.locator('[data-scope="p2"]').click();check('scope detail parentheses retained',(await page.locator('.gui-drawer').innerText()).includes('(Group = ops [EXTERNAL] AND (Device = R1 OR Device group = edge))'));await shot('policy-scope-drawer');await page.keyboard.press('Escape');
  await page.locator('[data-edit="p2"]').click();check('policy editor is wide drawer',await page.locator('#policy-modal-backdrop .modal').evaluate(e=>e.getBoundingClientRect().width)>800);await shot('policy-editor');await page.locator('#policy-cancel-btn').click();
  data['/api/policies/p2/condition-tree']={has_migrated:true,tree:null};await go('policies');check('missing tree not Any',(await page.locator('tr[data-row-index="1"]').innerText()).includes('Unresolved'));data=fixtures();
  await go('groups');await page.locator('[data-binding="g1"]').waitFor();
  check('runtime source ID removed from main table',!(await page.locator('#groups-table-wrap').innerText()).includes('netopsguard_ad_source1'));
  check('external membership not local count',(await page.locator('[data-members-for="g1"]').innerText()).includes('directory members'));
  await page.locator('[data-binding="g1"]').click();check('binding details preserve runtime name',(await page.locator('.gui-drawer').innerText()).includes('netopsguard_ad_source1'));await shot('group-binding-drawer');await page.keyboard.press('Escape');
  await go('users');await page.locator('[data-user-detail="u2"]').click();check('directory membership caveat in user detail',(await page.locator('.gui-drawer').innerText()).includes('not a full directory inventory'));await page.keyboard.press('Escape');
  await go('devices');check('inventory default, scan hidden',await page.locator('#device-inventory').isVisible()&&!await page.locator('#device-provisioning').isVisible());
  await page.locator('[data-device-view="monitoring"]').click();check('monitoring accessible separately',await page.locator('#monitoring-enabled-toggle').isVisible());await shot('devices-monitoring');
  await page.locator('[data-device-view="provisioning"]').click();check('provisioning safety warning remains',(await page.locator('#device-provisioning').innerText()).includes('real configuration to real devices'));await shot('devices-provisioning');
  check('switching workflows does not write',requests.every(r=>r.method==='GET'));
  await go('device-groups');await page.locator('[data-members="dg1"]').click();await page.locator('[data-remove-device-member="d1"]').waitFor();await page.locator('#device-members-search').fill('nomatch');check('device member filter',!await page.locator('[data-remove-device-member="d1"]').isVisible());await page.locator('#device-members-search').fill('R1');await shot('device-group-members');
  await go('sessions');await page.locator('[data-index="0"]').click();check('session evidence limits visible',(await page.locator('#session-detail-body').innerText()).includes('not confirmed authorization decisions'));check('session drawer wide',await page.locator('#session-modal-backdrop .modal').evaluate(e=>e.getBoundingClientRect().width)>800);await shot('session-detail');await page.locator('#session-detail-close-btn').click();
  await go('command-sets');await page.locator('[data-rules="cs1"]').click();check('rule regex and policy references visible',(await page.locator('.gui-drawer').innerText()).includes('^show running-config')&&(await page.locator('.gui-drawer').innerText()).includes('R1_ops'));await shot('command-set-rules');await page.keyboard.press('Escape');
  await go('policy-simulator');await page.locator('#sim-username').fill('operator');await page.locator('#sim-form button[type="submit"]').click();await page.locator('#sim-result h2').first().waitFor();check('simulator result clearly unverified',(await page.locator('#sim-result').innerText()).includes('not authorization evidence'));await shot('simulator-result');
  await go('effective-access');await page.locator('#lookup-name').fill('operator');await page.locator('#lookup-btn').click();await page.locator('#access-result table').waitFor();check('effective access not deployed guarantee',(await page.locator('#access-result').innerText()).includes('Deployed access is not verified'));await shot('effective-access-result');
  check('candidate validity separate from simulator certainty',(await page.locator('#analysis-candidate-context').innerText()).includes('does not verify simulator support'));
  data['/api/config/candidate']={applicable:false,diagnostics:[{policy_name:'Missing_scope',code:'scope.reference_missing',reason:'Missing group'}]};await go('policy-simulator');check('invalid candidate explicitly disclosed',(await page.locator('#analysis-candidate-context').innerText()).includes('Invalid / blocked candidate')&&(await page.locator('#analysis-candidate-context').innerText()).includes('scope.reference_missing'));await shot('simulator-blocked-context');data=fixtures();
  await go('access-events');check('authentication outcomes distinct',(await page.locator('#ae-wrap').innerText()).includes('Success')&&(await page.locator('#ae-wrap').innerText()).includes('Failure')&&(await page.locator('#ae-wrap').innerText()).includes('Unknown'));
  await page.locator('[data-event-detail="1"]').click();check('authentication detail not command authorization',(await page.locator('.gui-drawer').innerText()).includes('not a command authorization decision'));await shot('access-event-detail');await page.keyboard.press('Escape');
  for(const name of ['accounting','policies','users','groups','devices','device-groups','sessions','access-events','command-sets','command-categories','effective-access','policy-simulator']){
   await go(name);
   check(name+' main renders',await page.locator('.aaa-workspace h1').count()===1);
   for(const width of [1366,1440,1920,2560]){
    await page.setViewportSize({width,height:1000});await page.waitForTimeout(50);
    check(name+' no document overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await shot(name+'-'+width);
   }
  }
  await page.setViewportSize({width:1440,height:1000});
  data['/api/tacacs-accounting']={records:[],matched:0,total_in_log:0};await go('accounting');check('empty accounting explicit',(await page.locator('#accounting-table-wrap').innerText()).includes('No matching'));await shot('accounting-empty');
  status['/api/tacacs-accounting']=500;await go('accounting');check('accounting failure not empty',(await page.locator('#accounting-table-wrap').innerText()).includes('Could not load'));await shot('accounting-error');status={};data=fixtures();
  data['/api/tacacs-accounting'].records=Array.from({length:27},(_,i)=>({...data['/api/tacacs-accounting'].records[0],user:'operator'+i}));data['/api/tacacs-accounting'].matched=27;
  await go('accounting');check('loaded accounting pagination limits visible rows',await page.locator('#accounting-table-wrap tbody tr:visible').count()===25);await page.locator('.aaa-table-tools button').filter({hasText:'Next'}).click();check('next page shows remaining rows',await page.locator('#accounting-table-wrap tbody tr:visible').count()===2);data=fixtures();
  data['/api/tacacs-accounting'].records[0].result='"><img src=x onerror=alert(1)>';await go('accounting');check('result injection escaped',await page.locator('#accounting-table-wrap img').count()===0);
  data=fixtures();await go('policies');await page.locator('#sidebar-nav a[href="/tacacs/groups"]').evaluate(e=>e.click());await page.waitForURL('**/tacacs/groups');await page.locator('[data-binding="g1"]').waitFor();check('SPA remount table tools exactly once',await page.locator('#groups-table-wrap .aaa-table-tools').count()===1);
  await page.locator('[data-binding="g1"]').click();await page.keyboard.press('Shift+Tab');check('detail drawer traps keyboard focus',await page.evaluate(()=>document.querySelector('.gui-dialog').contains(document.activeElement)));await page.keyboard.press('Escape');check('detail drawer restores trigger focus',await page.locator('[data-binding="g1"]').evaluate(e=>e===document.activeElement));
  check('no JavaScript exceptions',errors.length===0);
 }catch(e){checks.push({name:e.message,passed:false});console.error(e,serverError);process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({checks,errors,screenshots:shots,requests,notice:'Synthetic HTTP fixtures; actual templates and JavaScript. No live AAA, DB or provisioning verification.'},null,2));console.log(JSON.stringify({checks:checks.length,failed:checks.filter(c=>!c.passed).length,errors}));if(browser)await browser.close();server.kill();}
})();
