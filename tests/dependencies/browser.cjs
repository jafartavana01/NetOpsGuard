/* Real templates and JS; synthetic dependency API responses, not DB verification. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path');
const {fixtures}=require('../gui03/fixtures.cjs');
const root=path.resolve(__dirname,'../..'),out=process.env.DEPENDENCY_EVIDENCE||path.join(root,'docs/dependencies/evidence');
fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});
const server=spawn(process.env.GUI_PYTHON||'python',['tests/gui03/preview.py'],{cwd:root,stdio:['ignore','ignore','pipe']});
let serverError='';server.stderr.on('data',d=>serverError+=d);
(async()=>{let browser;const checks=[],errors=[],mutations=[],shots=[];
const check=(name,value)=>{checks.push({name,passed:!!value});if(!value)throw Error(name);};
try{
 for(let i=0;i<60;i++){try{const response=await fetch('http://127.0.0.1:8767/tacacs/devices');await response.arrayBuffer();break;}catch{await new Promise(r=>setTimeout(r,100));}}
 browser=await chromium.launch({headless:true,executablePath:process.env.GUI_CHROMIUM});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://**/*',r=>r.abort());
 let blocked=true,canWrite=true,stale=false,historyOnly=false;const data=fixtures();
 function report(targets){
  const policy=targets[0].type==='policy';
  const deps=blocked&&!policy?[{object_type:targets[0].type,object_id:targets[0].id,object_name:'edge',dependency_type:'direct',referencing_type:'policy',referencing_id:'p1',referencing_name:'deny_R1',reference_location:'tree.groups[g1].conditions[c1]',blocks_deletion:true,automated_cleanup:true,enabled:true,protocol:'tacacs'}]:[];
  if(historyOnly)deps.push({object_type:'device',object_id:targets[0].id,object_name:'R1',dependency_type:'association',referencing_type:'security_audit_findings',referencing_id:'f1',referencing_name:'security_audit_findings',reference_location:'device_id',blocks_deletion:false,automated_cleanup:false,enabled:null,protocol:null});
  return {objects:targets.map(t=>({...t,name:policy?'deny_R1':'edge'})),dependencies:deps,policies:deps.some(d=>d.blocks_deletion)?[{id:'p1',name:'deny_R1',enabled:true,protocol:'tacacs'}]:[],total_selected:targets.length,safe_to_delete:deps.some(d=>d.blocks_deletion)?0:targets.length,blocked:deps.some(d=>d.blocks_deletion)?targets.length:0,revision:'a'.repeat(64),can_delete:canWrite,can_cleanup:canWrite,can_delete_policy:canWrite};
 }
 await page.route('**/api/**',async route=>{
  const req=route.request(),u=new URL(req.url());
  if(u.pathname==='/api/dependencies/inspect')return route.fulfill({json:report(req.postDataJSON().targets)});
  if(u.pathname==='/api/dependencies/execute'){
   const body=req.postDataJSON();mutations.push(body);
   if(stale)return route.fulfill({status:409,json:{detail:{code:'dependency.stale',message:'Dependencies changed. Review again.'}}});
   blocked=false;return route.fulfill({json:{candidate:{applicable:true,diagnostics:[]},deployed_configuration_changed:false}});
  }
  if(u.pathname==='/api/dependencies/orphans')return route.fulfill({json:{can_repair:canWrite,policies:[{id:'p1',name:'deny_R1',enabled:true,protocol:'tacacs',revision:'b'.repeat(64),missing:[{object_type:'device',object_id:'missing-router-id',condition_id:'c1',field:null,path:'tree.groups[g1].conditions[c1]'}]}]}});
  if(u.pathname.startsWith('/api/dependencies/repair/')){mutations.push(req.postDataJSON());return route.fulfill({json:{candidate:{applicable:true},deployed_configuration_changed:false}});}
  if(u.pathname==='/api/policies/p1')return route.fulfill({json:{name:'deny_R1',enabled:true,default_action:'deny'}});
  if(u.pathname==='/api/policies/p1/condition-tree')return route.fulfill({json:{has_migrated:true,tree:{logical_operator:'AND',conditions:[]}}});
  if(u.pathname.includes('group-members'))return route.fulfill({json:{results:[],error:null}});
  if(Object.hasOwn(data,u.pathname))return route.fulfill({json:data[u.pathname]});
  return route.continue();
 });
 const go=async(name)=>{await page.goto('http://127.0.0.1:8767/tacacs/'+name);await page.waitForTimeout(300);};
 const shot=async(name)=>{await page.screenshot({path:path.join(out,'screenshots',name+'.png'),fullPage:true,animations:'disabled'});shots.push(name+'.png');};
 const close=async()=>{await page.keyboard.press('Escape');await page.waitForTimeout(50);};
 await go('device-groups');await page.locator('[data-delete]').first().click();
 await page.getByRole('button',{name:'Remove All Dependencies',exact:true}).waitFor();
 check('direct dependency visible',(await page.locator('.gui-drawer').innerText()).includes('deny_R1'));
 check('no delete-object while blocked',await page.getByRole('button',{name:'Delete Selected Object',exact:true}).count()===0);
 check('running state disclaimer',(await page.locator('.gui-drawer').innerText()).includes('Running AAA configuration remains unchanged'));
 await shot('dependency-blocked-dialog');
 await page.getByRole('button',{name:'View Policy',exact:true}).click();await page.waitForTimeout(100);
 check('view policy available',(await page.locator('.dependency-policy-detail').innerText()).includes('default_action'));
 await page.getByRole('button',{name:'Remove All Dependencies',exact:true}).click();
 await page.getByRole('button',{name:'Confirm deletion',exact:true}).waitFor();
 check('button confirmation available without typing',await page.getByRole('button',{name:'Confirm deletion',exact:true}).isEnabled());
 check('no typed DELETE input',await page.getByLabel('Type DELETE',{exact:true}).count()===0);
 check('safe initial focus',await page.getByRole('button',{name:'Cancel',exact:true}).evaluate(e=>e===document.activeElement));
 check('cleanup retains original object',(await page.locator('.gui-drawer').innerText()).includes('Retained: edge'));
 check('deny fallthrough warning',(await page.locator('.gui-drawer').innerText()).includes('fallback may grant access previously denied'));
 await shot('remove-all-dependencies-confirmation');
 await page.getByRole('button',{name:'Confirm deletion',exact:true}).click();
 await page.getByRole('button',{name:'Delete Selected Object',exact:true}).waitFor();
 check('cleanup single server transaction',mutations.at(-1).operation==='cleanup');
 check('object retained and dependencies refreshed',await page.getByRole('button',{name:'Delete Selected Object',exact:true}).isVisible());await close();
 blocked=true;await page.locator('[data-delete]').first().click();await page.getByRole('button',{name:'Delete Policy',exact:true}).click();
 await page.getByRole('button',{name:'Confirm deletion',exact:true}).click();await page.getByRole('button',{name:'Delete Selected Object',exact:true}).waitFor();
 check('individual policy deletion explicit',mutations.at(-1).targets[0].type==='policy'&&mutations.at(-1).operation==='delete');await close();
 blocked=true;await page.locator('[data-delete]').first().click();await page.getByRole('button',{name:'Remove Dependencies and Delete Object',exact:true}).click();await page.getByRole('button',{name:'Confirm deletion',exact:true}).waitFor();
 check('combined transaction described',(await page.locator('.gui-drawer').innerText()).includes('ONE transaction'));await shot('combined-cleanup-confirmation');await close();
 await go('devices');await page.locator('[data-dependency-select]').first().waitFor();await page.getByRole('button',{name:'Select visible rows',exact:true}).click();
 check('bulk selects visible objects',await page.locator('[data-dependency-select]:checked').count()>0);await shot('bulk-selection');
 await page.getByRole('button',{name:'Bulk Delete',exact:true}).click();await page.getByRole('button',{name:'Refresh Dependencies',exact:true}).waitFor();check('bulk preview includes totals',(await page.locator('.gui-drawer').innerText()).includes('selected ·'));await shot('bulk-dependency-preview');await close();
 await go('policies');await page.getByRole('button',{name:'Repair Missing References',exact:true}).click();await page.getByRole('button',{name:'Save atomic repair',exact:true}).waitFor();
 check('repair shows missing ID and path',(await page.locator('.gui-drawer').innerText()).includes('missing-router-id')&&(await page.locator('.gui-drawer').innerText()).includes('conditions[c1]'));await shot('missing-reference-repair');
 await page.getByRole('button',{name:'Save atomic repair',exact:true}).click();check('repair requires selection and confirmation',(await page.locator('.gui-drawer [role=alert]').innerText()).includes('Choose every replacement'));
 await page.getByLabel('Replacement for device',{exact:true}).selectOption('d1');await page.locator('.dependency-card input[type=checkbox]').check();await page.getByRole('button',{name:'Save atomic repair',exact:true}).click();await page.waitForTimeout(100);
 check('repair submits reference replacement only',mutations.at(-1).replacements[0].replacement_id==='d1'&&mutations.at(-1).confirmation==='REPAIR');
 check('repair never applies automatically',(await page.locator('.gui-drawer').innerText()).includes('Apply separately'));await close();
 blocked=false;stale=true;await go('devices');await page.locator('[data-delete]').first().click();await page.getByRole('button',{name:'Delete Selected Object',exact:true}).click();await page.getByRole('button',{name:'Confirm deletion',exact:true}).click();await page.waitForTimeout(100);
 check('stale preview cannot retry without refresh',await page.getByRole('button',{name:'Confirm deletion',exact:true}).isDisabled());
 check('stale conflict disclosed',(await page.locator('.gui-drawer').innerText()).includes('Dependencies changed'));await shot('stale-preview-conflict');await close();
 stale=false;blocked=false;historyOnly=true;await page.locator('[data-delete]').first().click();await page.getByRole('button',{name:'Delete Selected Object',exact:true}).waitFor();
 check('historical findings do not fill dialog with cards',await page.locator('.dependency-card').count()===0);
 check('audit history retention explained',(await page.locator('.gui-drawer').innerText()).includes('Security audit history is retained'));
 await page.getByRole('button',{name:'Delete Selected Object',exact:true}).click();const beforeCancel=mutations.length;
 await page.getByRole('button',{name:'Cancel',exact:true}).click();check('cancel never submits deletion',mutations.length===beforeCancel);historyOnly=false;
 canWrite=false;blocked=true;await page.locator('[data-delete]').first().click();await page.getByRole('button',{name:'Refresh Dependencies',exact:true}).waitFor();check('read-only dependency viewer has no cleanup',await page.getByRole('button',{name:'Remove All Dependencies',exact:true}).count()===0);await close();
 for(const name of ['devices','device-groups','users','groups','command-sets','command-categories']){await go(name);check(name+' bulk controls',await page.getByRole('button',{name:'Bulk Delete',exact:true}).count()===1);}
 check('no JavaScript errors',errors.length===0);
}catch(e){checks.push({name:e.message,passed:false});console.error(e,serverError);process.exitCode=1;}
finally{fs.writeFileSync(path.join(out,'browser-results.json'),JSON.stringify({checks,errors,mutations,screenshots:shots,notice:'Synthetic API responses, real production templates. Separate database tests exercise transactions.'},null,2));console.log(JSON.stringify({checks:checks.length,failed:checks.filter(c=>!c.passed).length,errors}));if(browser)await browser.close();server.kill();}
})();
