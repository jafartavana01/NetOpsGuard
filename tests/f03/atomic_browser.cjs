/* Real editor JavaScript, synthetic HTTP responses. No database rollback claim. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'../..');
fs.mkdirSync(path.join(root,'docs/atomic-policy'),{recursive:true});
const server=spawn(process.env.GUI_PYTHON||'python',['tests/gui01/preview.py','8768'],{cwd:root,stdio:['ignore','ignore','pipe']});
let serverError='';server.stderr.on('data',d=>serverError+=d);
const ping=()=>new Promise((resolve,reject)=>http.get('http://127.0.0.1:8768/tacacs/policies',r=>{r.resume();r.on('end',resolve);}).on('error',reject));
(async()=>{let browser;const checks=[];try{
 for(let i=0;i<60;i++){try{await ping();break;}catch{await new Promise(r=>setTimeout(r,100));}}
 browser=await chromium.launch({headless:true,executablePath:process.env.GUI_CHROMIUM});
 const page=await browser.newPage();const errors=[],writes=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://**/*',r=>r.abort());
 let rejectSave=false;
 await page.route('**/api/policies**',async route=>{
  const req=route.request(),pathname=new URL(req.url()).pathname;
  if(['POST','PUT','DELETE'].includes(req.method())){
   writes.push({path:pathname,method:req.method(),body:req.postDataJSON()});
   return route.fulfill({status:rejectSave?409:200,json:rejectSave?{detail:{code:'policy.mutation.invalid_scope',message:'Policy was not saved.',diagnostics:[{reason:'Missing device'}]}}:{id:'saved'}});
  }
  if(pathname.endsWith('/condition-tree'))return route.fulfill({json:{has_migrated:false,tree:null}});
  return route.continue();
 });
 const check=(name,passed)=>{checks.push({name,passed:!!passed});if(!passed)throw Error(name);};
 const ready=async()=>{await page.goto('http://127.0.0.1:8768/tacacs/policies');await page.locator('[data-edit="p1"]').waitFor();};
 const submit=async()=>{const n=writes.length;await page.locator('#policy-form button[type="submit"]').click();await page.waitForFunction(()=>document.querySelector('#policy-modal-backdrop').hidden||!document.querySelector('#policy-form-error').hidden);await page.waitForTimeout(100);check('one authoritative mutation request',writes.length===n+1);return writes.at(-1);};
 await ready();await page.locator('#add-policy-btn').click();await page.locator('#policy-name').fill('restricted');
 await page.selectOption('#ms-devices-add-select','device:d1');await page.locator('#ms-devices-add-btn').click();
 let w=await submit();check('create carries tree in POST',w.method==='POST'&&w.body.scope_mode==='tree'&&JSON.stringify(w.body.condition_tree).includes('d1'));
 check('create carries complete security fields',['enabled','priority','default_priv_lvl','default_action','requires_manual_approval','manual_default_command_set_id','command_set_ids'].every(k=>Object.hasOwn(w.body,k)));
 await page.locator('#add-policy-btn').click();await page.locator('#policy-name').fill('catchall');w=await submit();check('intentional unrestricted explicit',w.body.scope_mode==='unrestricted'&&w.body.condition_tree===null);
 await page.locator('[data-edit="p1"]').click();w=await submit();check('edit carries complete tree in PUT',w.method==='PUT'&&w.path==='/api/policies/p1'&&w.body.scope_mode==='tree');
 check('edit preserves device and identity restriction',JSON.stringify(w.body.condition_tree).includes('d1')&&JSON.stringify(w.body.condition_tree).includes('g1'));
 rejectSave=true;await page.locator('[data-edit="p1"]').click();await submit();check('failure retains editor and exposes diagnostic',await page.locator('#policy-modal-backdrop').isVisible()&&(await page.locator('#policy-form-error').innerText()).includes('Missing device'));
 check('no second tree write',!writes.some(w=>w.path.endsWith('/condition-tree')));
 check('no JavaScript errors',errors.length===0);
 fs.writeFileSync(path.join(root,'docs/atomic-policy/browser-results.json'),JSON.stringify({checks,errors},null,2)+'\n');console.log(JSON.stringify({passed:checks.length,checks}));
 }catch(e){console.error(e,serverError);process.exitCode=1;}finally{if(browser)await browser.close();server.kill();}})();
