/* Actual templates/scripts, synthetic API fixtures. No production credentials. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs');const path=require('node:path');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'docs/gui01/screenshots');fs.mkdirSync(out,{recursive:true});
const server=spawn(process.env.GUI_PYTHON||'python',['tests/gui01/preview.py','8765'],{cwd:root,stdio:['ignore','ignore','pipe']});
let serverError='';server.stderr.on('data',d=>serverError+=d);
(async()=>{
 let browser;
 try {
  for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8765/dashboard');break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true,executablePath:process.env.GUI_CHROMIUM});
  const context=await browser.newContext({viewport:{width:1440,height:900}});
  // Use an explicitly supplied copy of the same pinned Chart.js version; no live CDN dependency.
  if(!process.env.GUI_CHART_JS)throw new Error('Set GUI_CHART_JS to Chart.js 4.5.1 chart.umd.min.js');
  await context.route('https://**/*',route=>route.request().url()==='https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.1/chart.umd.min.js'
   ?route.fulfill({path:process.env.GUI_CHART_JS,contentType:'application/javascript'}):route.abort());
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const screenshots=[];const checks=[];
  function check(name,ok){checks.push({name,passed:!!ok});if(!ok)console.log('FAIL',name);}
  const pages=[['dashboard','/dashboard'],['policies','/tacacs/policies'],['groups','/tacacs/groups'],['devices','/tacacs/devices'],['sessions','/tacacs/sessions'],['access-events','/tacacs/access-events'],['security-center','/security/overview']];
  for(const [name,url] of pages){
   await page.goto('http://127.0.0.1:8765'+url);await page.waitForTimeout(500);
   // Baseline Devices does not load this panel on entry; use its existing Refresh action.
   if(name==='devices'){
    await page.locator('#unknown-refresh-btn').click();
    await page.waitForFunction(()=>document.querySelector('#unknown-wrap').textContent.includes('Nothing unrecognised'));
    await page.evaluate(()=>window.scrollTo(0,0));
   }
   await page.screenshot({path:path.join(out,name+'-1440.png'),fullPage:true});screenshots.push(name+'-1440.png');
   check(name+' shell visible',await page.locator('#app-sidebar').isVisible());
   check(name+' no document horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(name==='access-events')check('date field icon space retained',await page.locator('#filter-since').evaluate(el=>parseInt(getComputedStyle(el).paddingLeft)>=30));
   if(name==='devices')check('unknown device Refresh finishes loading',!(await page.locator('#unknown-wrap').innerText()).includes('Loading'));
  }
  await page.goto('http://127.0.0.1:8765/tacacs/policies');
  check('desktop mobile toggle hidden',!(await page.locator('.mobile-nav-toggle').isVisible()));
  check('search icon space retained',await page.locator('#nav-search-input').evaluate(el=>parseInt(getComputedStyle(el).paddingLeft)>=30));
  await page.locator('#sidebar-collapse-btn').click();check('sidebar collapsed',await page.locator('body').evaluate(el=>el.classList.contains('sidebar-collapsed')));
  await page.reload();check('collapse preference persists',await page.locator('body').evaluate(el=>el.classList.contains('sidebar-collapsed')));
  await page.screenshot({path:path.join(out,'policies-collapsed-1440.png')});screenshots.push('policies-collapsed-1440.png');
  await page.locator('[data-section-key="access"] .nav-section-toggle').click();check('section icon expands rail',!(await page.locator('body').evaluate(el=>el.classList.contains('sidebar-collapsed'))));
  await page.locator('#nav-search-input').fill('groups');check('navigation search matches',await page.locator('a[href="/tacacs/groups"]').first().isVisible());
  await page.locator('#nav-search-input').fill('zzmissing');check('search empty state',await page.locator('#nav-empty').isVisible());await page.locator('#nav-search-input').fill('');
  await page.keyboard.press('Control+k');check('keyboard palette opens',await page.locator('#cmdk-backdrop').isVisible());await page.locator('#cmdk-input').fill('dashboard');await page.keyboard.press('Enter');await page.waitForTimeout(400);check('palette navigates actual route',new URL(page.url()).pathname==='/dashboard');
  await page.locator('#shell-help-btn').click();check('drawer focus inside',await page.evaluate(()=>document.querySelector('.gui-dialog').contains(document.activeElement)));await page.keyboard.press('Shift+Tab');check('drawer focus trapped',await page.evaluate(()=>document.querySelector('.gui-dialog').contains(document.activeElement)));
  await page.screenshot({path:path.join(out,'help-drawer-1440.png')});screenshots.push('help-drawer-1440.png');await page.keyboard.press('Escape');await page.waitForTimeout(60);check('drawer restores focus',await page.locator('#shell-help-btn').evaluate(el=>el===document.activeElement));
  await page.evaluate(()=>{const n=document.createElement('input');window.guard=NetOpsUI.openDrawer({title:'Unsaved fixture',body:n,beforeClose:()=>false});});await page.keyboard.press('Escape');check('drawer close veto respected',await page.locator('.gui-dialog').isVisible());await page.reload();
  for(const size of [{width:1920,height:1080},{width:1366,height:768},{width:820,height:1180}]){
   await page.setViewportSize(size);await page.goto('http://127.0.0.1:8765/tacacs/groups');await page.waitForTimeout(200);
   await page.screenshot({path:path.join(out,'groups-'+size.width+'.png'),fullPage:true});screenshots.push('groups-'+size.width+'.png');
   check('groups '+size.width+' no document overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.locator('.mobile-nav-toggle').click();check('tablet nav expanded attribute',await page.locator('.mobile-nav-toggle').getAttribute('aria-expanded')==='true');await page.keyboard.press('Escape');check('tablet Escape closes nav',await page.locator('.mobile-nav-toggle').getAttribute('aria-expanded')==='false');
  await page.setViewportSize({width:1440,height:900});await page.goto('http://127.0.0.1:8765/dashboard?role=operator');
  check('operator navigation omits superadmin destination',await page.locator('#sidebar-nav a[href="/platform/admin-users"]').count()===0);
  await page.keyboard.press('Control+k');await page.locator('#cmdk-input').fill('admin users');check('palette cannot invent gated destination',await page.locator('#cmdk-results a').count()===0);await page.keyboard.press('Escape');
  for(const state of ['valid-changed','valid-unchanged','blocked']){
   await page.route('**/api/config/candidate',route=>route.fulfill({json:{applicable:state!=='blocked',has_changes:state==='valid-changed',diff:state==='valid-changed'?'-old\n+new':'',candidate:'fixture',active:'fixture',uncompilable_policies:[],diagnostics:state==='blocked'?[{protocol:'tacacs',policy_name:'fixture',reason:'Missing group',code:'scope.reference_missing',path:'legacy.condition_group_id',object_id:'missing'}]:[]}}));
   await page.goto('http://127.0.0.1:8765/tacacs/config');await page.waitForTimeout(200);
   check(state+' page Apply state',await page.locator('#apply-btn').isVisible() === (state==='valid-changed'));
   if(state!=='valid-unchanged'){await page.locator('#global-apply-config-btn').click();await page.waitForTimeout(100);check(state+' shell Apply state',await page.locator('#global-apply-confirm-btn').isVisible()===(state==='valid-changed'));}
   if(state==='blocked'){await page.screenshot({path:path.join(out,'configuration-blocked-1440.png')});screenshots.push('configuration-blocked-1440.png');}
   await page.unroute('**/api/config/candidate');
  }
  const report={checks,errors,screenshots,serverError,fixtureNotice:'Synthetic data; pinned Chart.js 4.5.1 supplied locally; no live DB/auth/AAA.'};
  fs.writeFileSync(path.join(root,'docs/gui01/browser-results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({checks:checks.length,failed:checks.filter(c=>!c.passed).length,errors}));
  if(checks.some(c=>!c.passed)||errors.length)process.exitCode=1;
 }finally{if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e,serverError);server.kill('SIGTERM');process.exitCode=1;});
