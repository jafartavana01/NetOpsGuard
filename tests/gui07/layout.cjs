/* Responsive checks across real application templates with existing synthetic fixtures.
   No generated screenshot archives; no deployment/integration claim. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const server=spawn('python',['tests/gui07/preview.py'],{stdio:['ignore','ignore','pipe']});
let stderr='';server.stderr.on('data',d=>stderr+=d);
const data=Object.assign({},...['03','04','05','06'].map(n=>require('../gui'+n+'/fixtures.cjs').fixtures()));
const paths=['/dashboard',...['accounting','policies','users','groups','devices','device-groups','sessions','access-events','command-sets','command-categories','effective-access','policy-simulator','config','aaa-health','diagnostics'].map(n=>'/tacacs/'+n),...['overview','archive','compare','diff','drift','jobs','schedules','changes'].map(n=>'/ncm/'+n),...['jobs','templates','checks','audits'].map(n=>'/network-ops/'+n),...['overview','devices','findings','compliance','reports','schedule'].map(n=>'/security/'+n),...['settings','admin-users','admin-roles','active-directory','modules','license'].map(n=>'/platform/'+n),'/radius/server','/radius/clients'];
(async()=>{let browser;const checks=[],errors=[];try{
 for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8771/dashboard');break;}catch{await new Promise(r=>setTimeout(r,100));}}
 browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});const page=await browser.newPage();page.on('pageerror',e=>errors.push({url:page.url(),error:e.message}));
 await page.route('https://**/*',r=>r.request().url().includes('/Chart.js/')?r.fulfill({path:process.env.GUI_CHART_JS,contentType:'application/javascript'}):r.abort());
 await page.route('**/api/**',r=>{const p=new URL(r.request().url()).pathname;return data[p]!==undefined?r.fulfill({json:data[p]}):r.continue();});
 for(const width of [390,768,1440])for(const path of paths){
  await page.setViewportSize({width,height:900});await page.goto('http://127.0.0.1:8771'+path);await page.waitForTimeout(130);
  const result=await page.evaluate(()=>({heading:!!document.querySelector('h1'),overflow:document.documentElement.scrollWidth>innerWidth+1,offenders:[...document.querySelectorAll('main *')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>innerWidth+1&&!e.closest('.table-scroll,.ops-table,.aaa-table-scroll,[style*="overflow"],.diff-view');}).slice(0,8).map(e=>e.tagName+'#'+e.id+'.'+e.className)}));
  checks.push({path,width,passed:result.heading&&!result.overflow,...(!result.heading||result.overflow?{detail:result}:{})});
 }
 console.log(JSON.stringify({passed:checks.filter(x=>x.passed).length,failed:checks.filter(x=>!x.passed).length,failures:checks.filter(x=>!x.passed),errors},null,2));
 if(checks.some(x=>!x.passed)||errors.length)process.exitCode=1;
}finally{await browser?.close();server.kill();}})().catch(e=>{console.error(e,stderr);process.exitCode=1;server.kill();});
