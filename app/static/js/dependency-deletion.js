/* Desired-state deletion only. Every mutation is reinspected by the server. */
(function () {
  'use strict';
  const endpoints = {device:'/api/devices',device_group:'/api/device-groups',user:'/api/tacacs-users',user_group:'/api/tacacs-groups',command_set:'/api/command-sets',command_category:'/api/command-categories'};
  const pages = {'/tacacs/devices':'device','/tacacs/device-groups':'device_group','/tacacs/users':'user','/tacacs/groups':'user_group','/tacacs/command-sets':'command_set','/tacacs/command-categories':'command_category'};
  const impact = 'Deleting this policy may change effective network authorization after configuration is applied. A later policy or fallback may grant access previously denied.';
  const staged = 'Changes affect saved desired configuration only. Running AAA configuration remains unchanged until a separate successful Apply.';
  function el(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; }
  function button(text, fn, danger=false) { const b=el('button',text,danger?'btn-danger btn-small':'btn-secondary btn-small'); b.type='button'; b.addEventListener('click',fn); return b; }
  async function api(path, payload) {
    const r=await AAAPlatform.authedFetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await r.json();
    if(!r.ok) { const e=new Error(typeof data.detail==='string'?data.detail:data.detail?.message||'Request failed. No successful mutation was confirmed.'); e.detail=data.detail; throw e; }
    return data;
  }
  async function open(targets, onChanged=()=>location.reload()) {
    const body=el('div',undefined,'dependency-dialog');
    let report, busy=false;
    const dialog=NetOpsUI.openDrawer({title:'Deletion dependency review',body,beforeClose:()=>!busy});
    if(!dialog)return;
    async function refresh() {
      body.replaceChildren(el('p','Inspecting current dependencies…'));
      try {report=await api('/api/dependencies/inspect',{targets}); render();}
      catch(e) {body.replaceChildren(el('p',e.message,'text-danger'),button('Retry',refresh));}
    }
    function render() {
      body.replaceChildren(el('h3',report.objects.map(o=>o.name).join(', ')),el('p',staged,'dependency-warning'));
      body.append(el('p',`${report.total_selected} selected · ${report.safe_to_delete} safe to delete · ${report.blocked} blocked · ${report.policies.length} directly dependent policies`,'dependency-summary'));
      body.append(el('p','Preview only. The server rechecks objects and references inside the deletion transaction; changed dependencies require another review.'));
      if(!report.dependencies.length)body.append(el('p','No blocking dependencies found. Review the object names before confirming.'));
      for(const d of report.dependencies) {
        const card=el('section',undefined,'dependency-card');
        card.append(el('strong',`${d.referencing_name} — ${d.enabled===null?'Association':d.enabled?'Enabled':'Disabled'}`));
        card.append(el('p',`${d.protocol||d.referencing_type} · ${d.dependency_type==='empty_group'?'Removing these members would leave referenced group membership empty or unknown':d.dependency_type} · ${d.blocks_deletion?'Blocks deletion':'Informational'}`));
        const details=el('details'); details.append(el('summary','Reference details'),el('code',d.reference_location)); card.append(details);
        if(d.referencing_type==='policy') {
          card.append(button('View Policy',()=>viewPolicy(d,card)));
          if(report.can_delete_policy)card.append(button('Delete Policy',()=>confirmIndividual(d),true));
          if(!d.automated_cleanup)card.append(el('p','This is a membership consequence, not a direct reference. Add/reassign members or explicitly edit the policy; automatic policy cleanup is unavailable.'));
        } else if(d.blocks_deletion)card.append(el('p','Automatic cleanup is unsupported. Resolve this association in its owning workspace.'));
        body.append(card);
      }
      const actions=el('div',undefined,'dependency-actions');
      if(report.can_delete&&!report.blocked)actions.append(button('Delete Selected Object'+(targets.length>1?'s':''),()=>preview('delete'),true));
      if(report.can_cleanup&&report.policies.length) {
        actions.append(button('Remove All Dependencies',()=>preview('cleanup'),true));
        if(!report.dependencies.some(d=>d.blocks_deletion&&!d.automated_cleanup))actions.append(button('Remove Dependencies and Delete Object',()=>preview('cleanup_delete'),true));
      }
      actions.append(button('Refresh Dependencies',refresh),button('Cancel',()=>dialog.close())); body.append(actions);
    }
    async function viewPolicy(d, card) {
      try {
        const path=d.protocol==='radius'?'/api/radius/policies/':'/api/policies/';
        const p=await api(path+d.referencing_id);
        const detail=el('pre',JSON.stringify(p,null,2)); detail.className='dependency-policy-detail';
        card.querySelector('.dependency-policy-detail')?.remove();card.append(detail);
        if(d.protocol!=='radius') { const tree=await api('/api/policies/'+d.referencing_id+'/condition-tree'); detail.textContent+='\n'+JSON.stringify(tree,null,2); }
      }catch(e){AAAPlatform.toast(e.message,'error');}
    }
    async function confirmIndividual(d) {
      const selected=[{type:d.protocol==='radius'?'radius_policy':'policy',id:d.referencing_id}];
      try { const fresh=await api('/api/dependencies/inspect',{targets:selected}); confirmation('delete',fresh,selected,`Delete policy ${d.referencing_name} (${d.enabled?'Enabled':'Disabled'})`,true); }
      catch(e){AAAPlatform.toast(e.message,'error');}
    }
    async function preview(operation) {
      try { const fresh=await api('/api/dependencies/inspect',{targets}); report=fresh; confirmation(operation,fresh,targets,operation==='cleanup'?'Remove All Dependencies — retain selected objects':operation==='cleanup_delete'?'Remove Dependencies and Delete Object':'Delete selected objects'); }
      catch(e){AAAPlatform.toast(e.message,'error');}
    }
    function confirmation(operation,fresh,selected,title,individual=false) {
      body.replaceChildren(el('h3',title),el('p',impact,'dependency-warning'),el('p',staged));
      body.append(el('p',operation==='cleanup'?'Only the directly dependent policies below will be deleted. Original objects will be retained.':operation==='cleanup_delete'?'The listed policies and original objects will be deleted in ONE transaction.':'The selected objects below will be deleted.'));
      const list=el('ul');
      for(const p of operation==='delete'?[]:fresh.policies)list.append(el('li',`${p.protocol}: ${p.name} — ${p.enabled?'Enabled':'Disabled'}`));
      for(const o of fresh.objects)list.append(el('li',`${operation==='cleanup'?'Retained':'Deleted'}: ${o.name}${typeof o.enabled==='boolean'?' — '+(o.enabled?'Enabled':'Disabled'):''}`));
      body.append(list,el('p',`${operation==='delete'?0:fresh.policies.length} directly dependent policies scheduled for deletion.`));
      const label=el('label','Type DELETE to confirm this destructive operation');
      const input=el('input');input.autocomplete='off';input.setAttribute('aria-label','Type DELETE');label.append(input);body.append(label);
      const error=el('p',undefined,'text-danger');error.setAttribute('role','alert');body.append(error);
      const go=button('Confirm deletion',async()=>{
        if(input.value!=='DELETE'||busy)return;
        busy=true;dialog.panel.setAttribute('aria-busy','true');go.disabled=true;
        try {
          const result=await api('/api/dependencies/execute',{targets:selected,operation,revision:fresh.revision,confirmation:'DELETE'});
          AAAPlatform.toast('Saved desired configuration. Running AAA configuration was not changed.');
          if(!result.candidate.applicable)AAAPlatform.toast('Other configuration errors remain; Apply is still blocked.','error');
          busy=false;dialog.panel.removeAttribute('aria-busy');
          if(individual||operation==='cleanup')await refresh();
          else {await dialog.close();await onChanged();}
        }catch(e){busy=false;dialog.panel.removeAttribute('aria-busy');error.textContent=e.message+' Refresh Dependencies before trying again.';go.disabled=true;body.append(button('Refresh Dependencies',refresh));}
      },true);
      go.disabled=true;input.addEventListener('input',()=>{go.disabled=input.value!=='DELETE';});
      body.append(go,button('Back to dependencies',refresh));input.focus();
    }
    await refresh();
  }

  async function repairPanel() {
    const body=el('div',undefined,'dependency-dialog'); const dialog=NetOpsUI.openDrawer({title:'Repair missing policy references',body});if(!dialog)return;
    body.append(el('p','Loading missing references…'));
    try {
      const data=await api('/api/dependencies/orphans');body.replaceChildren(el('p',staged));
      if(!data.policies.length)body.append(el('p','No missing object IDs were found. Historical NULL scope loss cannot be inferred; other invalid conditions require policy review.'));
      for(const p of data.policies) {
        const card=el('section',undefined,'dependency-card');card.append(el('h3',`${p.name} — ${p.protocol} — ${p.enabled?'Enabled':'Disabled'}`));
        const replacements=[];
        for(const missing of p.missing) {
          card.append(el('p',`Missing ${missing.object_type}: ${missing.object_id||'no identifier'}`),el('code',missing.path));
          const label=el('label','Replace with an existing object');const select=el('select');select.setAttribute('aria-label','Replacement for '+missing.object_type);select.append(new Option('Choose a replacement…',''));label.append(select);card.append(label);
          try { const rows=await api(endpoints[missing.object_type]);for(const row of rows)select.append(new Option(row.name||row.username,row.id)); }
          catch(e){card.append(el('p','Replacement inventory unavailable: '+e.message));}
          replacements.push({missing,select});
        }
        const error=el('p',undefined,'text-danger');error.setAttribute('role','alert');card.append(error);
        if(data.can_repair) {
          const confirm=el('label',' I confirm replacing these missing restrictions; Boolean operators and all other policy settings must remain unchanged.');const check=el('input');check.type='checkbox';confirm.prepend(check);card.append(confirm);
          const save=button('Save atomic repair',async()=>{
            if(!check.checked||replacements.some(r=>!r.select.value)){error.textContent='Choose every replacement and confirm the repair.';return;}
            dialog.panel.setAttribute('aria-busy','true');save.disabled=true;
            try {
              const result=await api('/api/dependencies/repair/'+p.id,{revision:p.revision,confirmation:'REPAIR',replacements:replacements.map(r=>({condition_id:r.missing.condition_id,field:r.missing.field,replacement_id:r.select.value}))});
              card.replaceChildren(el('h3',p.name),el('p',result.candidate.applicable?'Repair saved. Candidate validation passed; review and Apply separately.':'Repair saved. Other candidate errors remain; Apply is still blocked.'));
            }catch(e){error.textContent=e.message;save.disabled=false;}
            finally{dialog.panel.removeAttribute('aria-busy');}
          });card.append(save);
          card.append(button('Delete Entire Policy',async()=>{await dialog.close();open([{type:p.protocol==='radius'?'radius_policy':'policy',id:p.id}]);},true));
        }
        body.append(card);
      }
    }catch(e){body.replaceChildren(el('p',e.message,'text-danger'));}
    body.append(button('Cancel',()=>dialog.close()));
  }

  function mount() {
    const main=document.querySelector('main.content');if(!main)return;
    if(['/tacacs/policies','/tacacs/config','/tacacs/configuration','/radius/policies'].includes(location.pathname)&&!main.querySelector('[data-reference-repair]')) {
      const b=button('Repair Missing References',repairPanel);b.dataset.referenceRepair='true';main.querySelector('.content-head')?.append(b);
    }
    const type=pages[location.pathname];if(!type)return;
    for(const table of main.querySelectorAll('table')) {
      const deletions=[...table.querySelectorAll('button[data-delete]')];if(!deletions.length)continue;
      let tools=table._dependencyTools;
      if(!tools) {
        const selected=new Set(),bar=el('div',undefined,'dependency-selection'),status=el('span','0 selected');
        const sync=()=>{status.textContent=selected.size+' selected';};
        const visible=()=>[...table.querySelectorAll('input[data-dependency-select]')].filter(c=>c.getClientRects().length);
        bar.append(button('Select visible rows',()=>{visible().forEach(c=>{c.checked=true;selected.add(c.value);});sync();}),button('Clear selection',()=>{selected.clear();table.querySelectorAll('input[data-dependency-select]').forEach(c=>c.checked=false);sync();}),status,button('Bulk Delete',()=>{
          if(!selected.size){AAAPlatform.toast('Select at least one object.','error');return;}
          open([...selected].map(id=>({type,id})));
        },true),el('span','Visible loaded rows only; maximum 200 objects per operation.'));
        table.parentElement.insertBefore(bar,table);tools={selected,sync};table._dependencyTools=tools;
      }
      deletions.forEach(b=>{
        const row=b.closest('tr');if(row.querySelector('[data-dependency-select]'))return;
        const check=el('input');check.type='checkbox';check.value=b.dataset.delete;check.dataset.dependencySelect='true';check.setAttribute('aria-label','Select '+row.cells[0].textContent.trim());
        check.addEventListener('change',()=>{if(check.checked)tools.selected.add(check.value);else tools.selected.delete(check.value);tools.sync();});row.cells[0].prepend(check);
      });
    }
  }
  window.DependencyUI={open,repairPanel};
  let scheduled=false;
  new MutationObserver(()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;mount();});}).observe(document.body,{childList:true,subtree:true});
  mount();
})();
