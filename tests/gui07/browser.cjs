/* GUI-07 shared-shell browser checks. Actual Jinja templates, synthetic API responses only.
 * Run: GUI_CHROMIUM=/path/to/chromium node tests/gui07/browser.cjs
 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const server=spawn('python',['tests/gui06/preview.py'],{cwd:root,stdio:['ignore','ignore','pipe']});
let serverErrors=''; server.stderr.on('data',d=>serverErrors+=d);
(async()=>{
  let browser,passes=0;
  const check=(name,passed)=>{if(!passed)throw new Error(name);passes++;};
  try {
    let ready=false;
    for(let i=0;i<70;i++) {
      try {const res=await fetch('http://127.0.0.1:8770/platform/settings');if(res.ok){ready=true;break;}}catch(_){}
      await new Promise(r=>setTimeout(r,100));
    }
    if(!ready)throw new Error('GUI-06 fixture server did not start: '+serverErrors);
    browser=await chromium.launch({executablePath:process.env.GUI_CHROMIUM,headless:true});
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    let candidate={applicable:true,has_changes:true,diff:'--- current\n+++ candidate\n+ test'};
    let candidateNetworkFailure=false,applyFailure='',applyRequests=0;
    await page.route('**/api/config/candidate',route=>
      candidateNetworkFailure?route.abort('failed'):route.fulfill({json:candidate}));
    await page.route('**/api/config/apply',route=>{
      applyRequests++;
      if(applyFailure==='network')return route.abort('failed');
      if(applyFailure==='http')return route.fulfill({status:422,json:{detail:{message:'Synthetic rejection'}}});
      return route.fulfill({json:{status:'ok'}});
    });
    await page.goto('http://127.0.0.1:8770/platform/settings');
    const apply=page.locator('#global-apply-config-btn'),dialog=page.locator('#global-apply-modal-backdrop');
    await apply.waitFor({state:'visible',timeout:6000});
    await apply.click();
    await page.locator('#global-apply-confirm-btn').waitFor({state:'visible'});
    check('global modal visible',await dialog.isVisible());
    check('initial focus on Cancel',await page.evaluate(()=>document.activeElement?.id==='global-apply-cancel-btn'));
    check('background inert',await page.locator('.app-shell').evaluate(el=>el.inert));
    await page.keyboard.press('Escape');
    check('Escape closes modal',await dialog.isHidden());
    check('background restored',!(await page.locator('.app-shell').evaluate(el=>el.inert)));
    check('focus returns to opener',await page.evaluate(()=>document.activeElement?.id==='global-apply-config-btn'));
    await apply.click();
    await page.locator('#global-apply-confirm-btn').waitFor({state:'visible'});
    await page.locator('#global-apply-diff').focus();
    await page.keyboard.press('Shift+Tab');
    check('reverse Tab wraps',await page.evaluate(()=>document.activeElement?.id==='global-apply-confirm-btn'));
    await page.keyboard.press('Escape');
    candidateNetworkFailure=true;
    await apply.click();
    check('candidate fetch error presented',await page.locator('#global-apply-error').isVisible());
    check('candidate failure cannot Apply',await page.locator('#global-apply-confirm-btn').isHidden());
    await page.keyboard.press('Escape');
    candidateNetworkFailure=false;
    candidate={applicable:false,has_changes:false,diagnostics:[{protocol:'tacacs',policy_name:'restricted',reason:'missing scope',path:'scope',code:'scope.invalid'}]};
    await apply.click();
    check('blocked candidate shown',(await page.locator('#global-apply-title').textContent()).includes('blocked'));
    check('blocked candidate cannot Apply',await page.locator('#global-apply-confirm-btn').isHidden());
    await page.keyboard.press('Escape');
    candidate={applicable:true,has_changes:true,diff:'--- current\n+++ candidate\n+ test'};
    await apply.click();
    await page.locator('#global-apply-confirm-btn').waitFor({state:'visible'});
    applyFailure='network';
    await page.locator('#global-apply-confirm-btn').click();
    check('interrupted Apply described',(await page.locator('#global-apply-error').textContent()).includes('Verify deployed'));
    check('ambiguous Apply stays open',await dialog.isVisible());
    check('exactly one POST',applyRequests===1);
    await page.keyboard.press('Escape');
    applyFailure='http';
    await apply.click();
    await page.locator('#global-apply-confirm-btn').waitFor({state:'visible'});
    await page.locator('#global-apply-confirm-btn').click();
    check('HTTP rejection visible',(await page.locator('#global-apply-error').textContent()).includes('Synthetic rejection'));
    await page.keyboard.press('Escape');
    await page.keyboard.press('Control+k');
    const palette=page.locator('#cmdk-backdrop');
    check('command palette opens',await palette.isVisible());
    check('palette focuses search',await page.evaluate(()=>document.activeElement?.id==='cmdk-input'));
    await page.locator('#cmdk-input').fill('admin');
    check('palette finds authorized destinations',await page.locator('#cmdk-results a').count()>0);
    await page.keyboard.press('Escape');
    check('palette Escape closes',await palette.isHidden());
    check('palette restores scroll lock',await page.evaluate(()=>document.body.style.overflow===''));
    await page.setViewportSize({width:390,height:844});
    await apply.click();
    check('mobile modal usable',await page.locator('#global-apply-cancel-btn').isVisible());
    await page.keyboard.press('Escape');
    console.log('GUI-07 focused browser checks passed: '+passes);
  } finally {await browser?.close();server.kill('SIGTERM');}
})().catch(err=>{console.error(err,serverErrors);server.kill('SIGTERM');process.exitCode=1;});
