const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const server=spawn('python',['tests/platform/preview.py'],{stdio:['ignore','ignore','pipe']});let stderr='';server.stderr.on('data',d=>stderr+=d);
(async()=>{let browser;let passed=0;const errors=[];const check=(name,ok)=>{if(!ok)throw Error(name);passed++;};try{
for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8775/ncm/schedules');break;}catch{await new Promise(r=>setTimeout(r,100));}}
browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
let zone='Asia/Tehran',denied=false,writes=[],schedule={id:'a',name:'Legacy',enabled:true,daily_run_time:'02:00',schedule_timezone:null,configuration_types:['running'],device_ids:['d1'],device_group_ids:[],retention_days:7,next_due_at:'2026-10-15T02:00:00Z',last_attempted_at:'2026-10-14T02:00:00Z'};
await page.route('https://**/*',r=>r.abort());
await page.route('**/api/system/timezone',r=>r.fulfill({json:{timezone:zone,timezones:['UTC','Asia/Tehran','America/New_York']}}));
await page.route('**/api/platform-settings/timezone',r=>{writes.push(r.request().postDataJSON());if(denied)return r.fulfill({status:403,json:{detail:'Permission denied'}});zone=r.request().postDataJSON().timezone;return r.fulfill({json:{timezone:zone,restart_required:false}});});
await page.route('**/api/platform-settings',r=>r.fulfill({json:{web_host:'0.0.0.0',web_port:8420,https_enabled:true,tacacs_port:49,certificate:null}}));
await page.route('**/api/ncm/devices',r=>r.fulfill({json:[{device_id:'d1',device_name:'R1',ip_address:'192.0.2.1'}]}));
await page.route('**/api/device-groups',r=>r.fulfill({json:[]}));
await page.route('**/api/ncm/credentials/status',r=>r.fulfill({json:{configured:true}}));
await page.route('**/api/ncm/schedules**',r=>{if(r.request().method()==='PUT'||r.request().method()==='POST'){writes.push(r.request().postDataJSON());schedule={...schedule,...r.request().postDataJSON()};return r.fulfill({json:schedule});}return r.fulfill({json:[schedule]});});
await page.route('**/api/security/schedule',r=>r.fulfill({json:{enabled:false,ssh_username:'svc',has_password:true,daily_run_time:'02:00',schedule_timezone:null,last_run_at:'2026-10-14T02:00:00Z',last_run_status:'completed',last_run_summary:'Done',next_due_at:null}}));
const go=async path=>{await page.goto('http://127.0.0.1:8775'+path);await page.waitForTimeout(250);};
await go('/ncm/schedules');check('legacy zone labelled',(await page.locator('#schedules-wrap').innerText()).includes('UTC · legacy'));
check('legacy UTC next instant readable',(await page.locator('#schedules-wrap').innerText()).includes('2026-10-15T02:00:00.000Z'));
await page.locator('[data-edit]').click();await page.waitForTimeout(80);check('editing does not convert legacy',await page.locator('#schedule-timezone').inputValue()==='');check('legacy time unchanged',await page.locator('#schedule-time').inputValue()==='02:00');
await page.locator('#schedule-form button[type=submit]').click();await page.waitForTimeout(150);check('save legacy preserves UTC',writes.at(-1).schedule_timezone===null);
await page.locator('[data-edit]').click();await page.waitForTimeout(80);await page.locator('#schedule-timezone').selectOption('Asia/Tehran');await page.locator('#schedule-form button[type=submit]').click();await page.waitForTimeout(150);check('explicit conversion sent',writes.at(-1).schedule_timezone==='Asia/Tehran');
check('converted timezone displayed',(await page.locator('#schedules-wrap').innerText()).includes('Asia/Tehran'));
await page.locator('#add-schedule-btn').click();await page.waitForTimeout(80);check('new schedule uses app preference',await page.locator('#schedule-timezone').inputValue()==='Asia/Tehran');
await go('/security/schedule');check('audit legacy is not silently converted',await page.locator('#schedule-timezone').inputValue()==='');check('audit last execution includes UTC',(await page.locator('#schedule-last-run-body').innerText()).includes('UTC'));
await go('/platform/settings');check('active timezone visible',(await page.locator('#timezone-active').innerText()).includes('Asia/Tehran'));check('browser is suggestion only',(await page.locator('#timezone-suggestion').innerText()).includes('not saved automatically'));check('searchable IANA list',await page.locator('#timezone-options option').count()===3);check('installed version footer',/NetOpsGuard \d+\.\d+\.\d+\.\d+/.test(await page.locator('.sidebar-footer').first().innerText()));
await page.locator('#timezone-choice').fill('America/New_York');await page.locator('#timezone-save').click();await page.waitForTimeout(100);check('backend-confirmed change shown',(await page.locator('#timezone-active').innerText()).includes('America/New_York'));
denied=true;await page.locator('#timezone-choice').fill('UTC');await page.locator('#timezone-save').click();await page.waitForTimeout(100);check('denied update visible',(await page.locator('#timezone-error').innerText()).includes('Permission denied'));check('denial preserves active zone',(await page.locator('#timezone-active').innerText()).includes('America/New_York'));
for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});check('settings no horizontal clipping '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
check('no uncaught errors',errors.length===0);
}finally{await browser?.close();server.kill();console.log(JSON.stringify({passed,errors}));}})().catch(e=>{console.error(e,stderr);process.exitCode=1;});
