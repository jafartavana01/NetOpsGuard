const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const server=spawn('python',['tests/ncm_scheduler/preview.py'],{stdio:['ignore','ignore','pipe']});let stderr='';server.stderr.on('data',d=>stderr+=d);
(async()=>{let browser;const checks=[],errors=[];const check=(name,ok)=>{checks.push({name,passed:!!ok});if(!ok)throw Error(name);};try{
 for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8774/ncm/schedules');break;}catch{await new Promise(r=>setTimeout(r,100));}}
 browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
 let saved={id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Daily',enabled:true,daily_run_time:'12:00',configuration_types:['running','startup'],device_ids:['d1'],device_group_ids:[],retention_days:7,execution_status:'completed',last_attempted_at:'2026-10-14T12:00:01Z',last_success_at:'2026-10-14T12:00:03Z',next_due_at:'2026-10-15T12:00:00Z',last_job_id:'j1',total_devices:1,succeeded:1,failed:0,execution_error:null};
 let mode='completed',writes=0;
 await page.route('https://**/*',r=>r.abort());
 await page.route('**/api/ncm/devices',r=>r.fulfill({json:[{device_id:'d1',device_name:'R1',ip_address:'192.0.2.1'}]}));
 await page.route('**/api/device-groups',r=>r.fulfill({json:[]}));
 await page.route('**/api/ncm/credentials/status',r=>r.fulfill({json:{configured:true}}));
 await page.route('**/api/ncm/schedules',r=>r.fulfill({json:[saved]}));
 await page.route('**/api/ncm/schedules/*/run-now',r=>{writes++;if(mode==='network')return r.abort();if(mode==='denied')return r.fulfill({status:403,json:{detail:'Permission denied'}});saved={...saved,execution_status:mode,execution_error:mode==='blocked'?'Configure System → Device Credentials':null};return r.fulfill({json:saved});});
 const go=async()=>{await page.goto('http://127.0.0.1:8774/ncm/schedules');await page.waitForTimeout(160);};
 const run=async()=>{page.once('dialog',d=>d.accept());await page.locator('[data-run]').click();await page.waitForTimeout(150);};
 await go();let text=await page.locator('#schedules-wrap').innerText();check('persisted completed counts visible',text.includes('completed')&&text.includes('1 succeeded / 0 failed / 1 total'));check('legacy UTC explicitly labelled',text.includes('UTC · legacy'));check('job archive link',await page.locator('a[href="/ncm/jobs?job=j1"]').count()===1);check('next due visible',text.includes('2026-10-15T12:00:00.000Z'));
 page.once('dialog',d=>d.dismiss());await page.locator('[data-run]').click();check('cancel sends no request',writes===0);
 await run();check('success requires completed response',(await page.locator('body').innerText()).includes('Schedule result: completed'));
 await go();mode='blocked';await run();check('blocked is not successful',(await page.locator('body').innerText()).includes('Schedule result: blocked'));check('actionable error visible',(await page.locator('#schedules-wrap').innerText()).includes('Device Credentials'));
 await go();mode='denied';await run();check('denial visible',(await page.locator('body').innerText()).includes('Permission denied'));check('denial no success toast',!(await page.locator('body').innerText()).includes('Schedule result: completed'));
 await go();mode='network';await run();check('network uncertainty explicit',(await page.locator('body').innerText()).includes('execution may have continued'));
 saved.execution_status='running';await page.locator('#refresh-schedules-btn').click();await page.waitForTimeout(100);check('running disabled',await page.locator('[data-run]').isDisabled());
 saved.execution_status='completed';saved.enabled=false;await go();check('disabled schedule cannot run',await page.locator('[data-run]').isDisabled());
 for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});await go();check('no page overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
 check('no uncaught JavaScript errors',errors.length===0);
}finally{await browser?.close();server.kill();console.log(JSON.stringify({passed:checks.filter(x=>x.passed).length,failed:checks.filter(x=>!x.passed).length,checks,errors},null,2));}})().catch(e=>{console.error(e,stderr);process.exitCode=1;});
