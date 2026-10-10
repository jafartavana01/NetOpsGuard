/* Real History UI; synthetic HTTP fixtures. No production database or daemon. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'docs/restoration-fix');
fs.mkdirSync(out,{recursive:true});
const server=spawn(process.env.GUI_PYTHON||'python',['tests/gui01/preview.py','8767'],{cwd:root,stdio:['ignore','ignore','pipe']});
let stderr='';server.stderr.on('data',x=>stderr+=x);
(async()=>{
 let browser;const checks=[],errors=[];let mode='missing',restores=0,historyReads=0;
 const check=(name,value)=>checks.push({name,passed:!!value});
 try{
  for(let i=0;i<60;i++){try{await new Promise((resolve,reject)=>require('node:http').get('http://127.0.0.1:8767/tacacs/policies',res=>{res.resume();res.on('end',resolve);}).on('error',reject));break;}catch{await new Promise(r=>setTimeout(r,100));}}
  browser=await chromium.launch({headless:true,executablePath:process.env.GUI_CHROMIUM});
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.route('https://**/*',route=>route.abort());
  await page.route('**/api/policies/p1/versions**',async route=>{
   if(route.request().method()==='GET'){
    historyReads++;return route.fulfill({json:{versions:[{id:'v1',version_number:1,created_at:'2026-01-01T12:00:00Z',created_by:'reviewer',change_description:'Synthetic history'}]}});
   }
   restores++;
   if(mode==='network')return route.abort();
   if(mode==='success')return route.fulfill({json:{policy:{},warnings:[]}});
   if(mode==='forbidden')return route.fulfill({status:403,json:{detail:'Permission denied'}});
   return route.fulfill({status:409,json:{detail:{code:'policy.restore.invalid',restored:false,
    message:'Restore requires review. The current policy and deployed configuration have not changed.',
    diagnostics:[{code:'policy.restore.reference_missing',object_type:'device',object_name:'<img src=x onerror="window.unwanted=true">',reason:'The historical reference no longer resolves uniquely.'}]}}});
  });
  await page.goto('http://127.0.0.1:8767/tacacs/policies');
  await page.locator('[data-history="p1"]').click();
  await page.locator('[data-restore="v1"]').click();
  const box=page.locator('#history-restore-error');await box.waitFor({state:'visible'});
  check('structured restore failure visible', (await box.innerText()).includes('Restore requires review'));
  check('current policy preservation explained',(await box.innerText()).includes('have not changed'));
  check('missing object and diagnostic visible',(await box.innerText()).includes('policy.restore.reference_missing'));
  check('diagnostic rendered as text',await box.locator('img').count()===0 && !await page.evaluate(()=>window.unwanted));
  check('failed restore does not reload history as success',historyReads===1&&restores===1);
  check('history remains open',await page.locator('#history-modal-backdrop').isVisible());
  await page.screenshot({path:path.join(out,'history-restoration-blocked.png'),fullPage:true});
  mode='forbidden';await page.locator('[data-restore="v1"]').click();
  await page.waitForFunction(()=>document.querySelector('#history-restore-error').textContent==='Could not restore this version.');
  check('generic failure is not reported as successful',await box.isVisible());
  mode='network';await page.locator('[data-restore="v1"]').click();
  await page.waitForFunction(()=>document.querySelector('#history-restore-error').textContent.includes('Reload history'));
  check('unknown network result requires state check',(await box.innerText()).includes('before retrying'));
  mode='success';await page.locator('[data-restore="v1"]').click();
  await page.waitForFunction(()=>document.querySelector('#history-restore-error').hidden);
  for(let i=0;i<20&&historyReads<2;i++)await page.waitForTimeout(50);
  check('successful restore refreshes history',historyReads===2);
  check('successful restore clears old diagnostic',await box.isHidden());
 }catch(e){errors.push(e.stack||String(e));}
 finally{if(browser)await browser.close();server.kill();}
 fs.writeFileSync(path.join(out,'history-browser-results.json'),JSON.stringify({checks,errors,fixtureNotice:'Synthetic HTTP data with actual production History UI. Not HTTP/database/native integration.',serverError:stderr},null,2));
 console.log(JSON.stringify({checks:checks.length,passed:checks.filter(x=>x.passed).length,errors}));
 if(errors.length||checks.some(x=>!x.passed))process.exitCode=1;
})();
