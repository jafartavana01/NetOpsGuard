/* Real templates/shared JS with controlled API responses; no device claims. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const server=spawn('python',['tests/security_comparison/preview.py'],{stdio:['ignore','ignore','pipe']});let stderr='';server.stderr.on('data',d=>stderr+=d);
(async()=>{let browser;let passed=0;const errors=[];const check=(name,ok)=>{if(!ok)throw Error(name);passed++;};try{
for(let i=0;i<60;i++){try{await fetch('http://127.0.0.1:8776/security/reports');break;}catch{await new Promise(r=>setTimeout(r,100));}}
browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});const page=await browser.newPage({viewport:{width:1280,height:1000}});page.on('pageerror',e=>errors.push(e.message));
const rows=[{audit_run_id:'new',device_name:'R1',source:'live',status:'completed',started_at:'2026-01-02T00:00:00Z',overall_score:80},{audit_run_id:'old',device_name:'R1',source:'upload',status:'completed',started_at:'2026-01-01T00:00:00Z',overall_score:60}];
const finding={status:'fail',severity:'high',title:'SSH <img src=x onerror="window.bad=true">',evidence:['<script>window.bad=true</script>'],check_id:'SSH',domain:'Management'};
const categories=['new','first_observed','resolved','persistent','indeterminate','manual_review'];
let mode='ok',calls=0,release;
await page.route('https://**/*',r=>r.abort());
await page.route('**/api/security/findings**',r=>r.fulfill({json:[]}));
await page.route('**/api/security/devices',r=>r.fulfill({json:[]}));
await page.route('**/api/security/batches',r=>r.fulfill({json:[]}));
await page.route('**/api/security/activity?limit=100',r=>r.fulfill({json:rows}));
await page.route('**/api/security/audits/*/compare/*',async r=>{calls++;if(mode==='network')return r.abort();if(mode==='denied')return r.fulfill({status:403,json:{detail:'Permission denied'}});if(mode==='same')return r.fulfill({status:409,json:{detail:'Choose two distinct audit executions.'}});if(mode==='slow')await new Promise(resolve=>release=resolve);return r.fulfill({json:{device_name:'R1',from_run_id:'old',to_run_id:'new',score_delta:null,score_reason:'Assessment scope changed.',warnings:['Coverage differs.'],counts:Object.fromEntries(categories.map(c=>[c,1])),comparisons:categories.map(c=>({category:c,key:['Management','SSH','Gi1',''],reason:c==='indeterminate'?'Check was not evaluated.':'Recorded classification: '+c,previous:[finding],current:c==='indeterminate'?[]:[{...finding,status:c==='resolved'?'pass':'fail'}]}))}});});
await page.goto('http://127.0.0.1:8776/security/reports');await page.waitForSelector('[data-compare]');
check('default previous is older',await page.locator('[data-previous]').inputValue()==='old');check('default current is newer',await page.locator('[data-current]').inputValue()==='new');
await page.locator('[data-compare]').click();await page.waitForSelector('[data-result] details');
for(const title of ['New regression (1)','First observed (1)','Confirmed resolved (1)','Persistent (1)','Indeterminate (1)','Manual review (1)'])check(title,(await page.locator('[data-result]').innerText()).includes(title));
check('missing delta is not zero',(await page.locator('[data-result]').innerText()).includes('Score change unavailable: Assessment scope changed.'));
await page.locator('[data-result] summary').first().focus();await page.keyboard.press('Enter');check('keyboard opens evidence',await page.locator('[data-result] details').first().getAttribute('open')!==null);
check('previous and newer labelled',(await page.locator('[data-result] details').first().innerText()).includes('Previous evidence')&&(await page.locator('[data-result] details').first().innerText()).includes('Newer evidence'));
check('evidence escaped',await page.locator('[data-result] img,[data-result] script').count()===0);check('no injected execution',await page.evaluate(()=>!window.bad));
mode='denied';await page.locator('[data-compare]').click();await page.waitForFunction(()=>document.querySelector('[data-result]').textContent.includes('Permission denied'));check('denial clears stale success',await page.locator('[data-result] details').count()===0);
mode='same';await page.locator('[data-compare]').click();await page.waitForFunction(()=>document.querySelector('[data-result]').textContent.includes('distinct'));check('invalid pair error shown',await page.locator('[data-compare]').isEnabled());
mode='network';await page.locator('[data-compare]').click();await page.waitForFunction(()=>!document.querySelector('[data-compare]').disabled);check('network error not success',await page.locator('[data-result] details').count()===0);
mode='ok';await page.locator('[data-compare]').click();await page.waitForSelector('[data-result] details');
for(const width of [390,768,1280]){await page.setViewportSize({width,height:1000});check('responsive comparison '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
mode='slow';await page.locator('[data-compare]').click();await page.waitForTimeout(80);check('no overlapping compare',await page.locator('[data-compare]').isDisabled());release();await page.waitForFunction(()=>!document.querySelector('[data-compare]').disabled);
mode='slow';release=null;await page.locator('[data-compare]').click();
for(let i=0;i<30&&!release;i++)await new Promise(r=>setTimeout(r,20));
await page.locator('.security-nav a[href="/security/findings"]').click();await page.waitForURL('**/security/findings');
check('SPA leaves comparison',await page.locator('#audit-comparison').count()===0);release();await page.waitForTimeout(100);
check('late response cannot write new view',await page.locator('[data-result]').count()===0);
mode='ok';await page.locator('.security-nav a[href="/security/reports"]').click();await page.waitForURL('**/security/reports');await page.waitForSelector('[data-compare]');
const before=calls;await page.locator('[data-compare]').click();await page.waitForSelector('[data-result] details');check('repeat visit has one handler',calls===before+1);
check('no browser errors',errors.length===0);
}finally{await browser?.close();server.kill();console.log(JSON.stringify({passed,errors}));}})().catch(e=>{console.error(e,stderr);process.exitCode=1;});
