/* GUI-05 presentation helpers. No audit decisions or score recalculation. */
(() => {
  const esc=AAAPlatform.escapeHtml;
  const dt=v=>v?new Date(v).toLocaleString():'Not recorded';
  const badge=s=>'<span class="security-badge" data-state="'+esc(s||'unknown')+'">'+esc(({na:'Not applicable',manual_review:'Manual review',warn:'Partial control'})[s]||s||'Unknown')+'</span>';
  const can=k=>{try{return JSON.parse(document.getElementById('security-grants')?.textContent||'[]').includes(k);}catch{return false;}};
  function scopeDocument(){
    // Capture this view's actual nodes. Late responses may update detached nodes,
    // but can never find IDs belonging to a subsequent SPA view.
    const roots=[...document.getElementById('view-root').children];
    const query=s=>roots.flatMap(r=>[...(r.matches(s)?[r]:[]),...r.querySelectorAll(s)]);
    return new Proxy(document,{get(target,key){
      if(key==='getElementById')return id=>query('#'+CSS.escape(id))[0]||null;
      if(key==='querySelector')return s=>query(s)[0]||null;
      if(key==='querySelectorAll')return query;
      if(key==='addEventListener')return (type,fn,options)=>{target.addEventListener(type,fn,options);AAAPlatform.onViewLeave(()=>target.removeEventListener(type,fn,options));};
      const v=target[key];return typeof v==='function'?v.bind(target):v;
    }});
  }
  function evidence(root){
    root.querySelectorAll('.diff-view:not([data-tools]),.security-evidence:not([data-tools])').forEach(pre=>{
      pre.dataset.tools='true';const original=pre.textContent,bar=document.createElement('div');bar.className='security-evidence-tools';
      const copy=document.createElement('button');copy.type='button';copy.className='btn-secondary btn-small';copy.textContent='Copy exact text';copy.onclick=()=>OpsUI.copy(original);
      const label=document.createElement('label'),wrap=document.createElement('input');wrap.type='checkbox';wrap.onchange=()=>pre.classList.toggle('is-wrapped',wrap.checked);label.append(wrap,' Wrap lines');bar.append(copy,label);pre.before(bar);
    });
  }
  async function safeFetch(url,options){try{return await AAAPlatform.authedFetch(url,options);}catch{return {ok:false,status:0,json:async()=>({detail:'Connection interrupted. Refresh audit history to check the recorded result before retrying.'})};}}
  function mount(){
    const root=document.querySelector('.security-workspace');if(!root||root.dataset.mounted)return;root.dataset.mounted='true';
    const view=root.closest('#view-root'),isSuper=JSON.parse(document.getElementById('security-superadmin').textContent);
    const grants={'#open-audit-modal-btn,#run-audit-btn,#bulk-audit-btn,.device-select,#select-all-visible':'security:audit','#ncm-backup-now-btn':'ncm:backup'};
    function enhance(){
      for(const [selector,key] of Object.entries(grants))if(!can(key))view.querySelectorAll(selector).forEach(el=>{el.dataset.securityDenied='true';if('disabled' in el)el.disabled=true;});
      if(!isSuper)view.querySelectorAll('#report-run-again-btn,a[href="/security/schedule"]').forEach(el=>el.dataset.securityDenied='true');
      evidence(view);
    }
    enhance();const observer=new MutationObserver(enhance);observer.observe(view,{childList:true,subtree:true});
    const click=e=>{if(e.target.closest('[data-security-denied]')){e.preventDefault();e.stopImmediatePropagation();}};view.addEventListener('click',click,true);
    const overlays=[...view.querySelectorAll('.modal-backdrop,.drawer-backdrop')],openers=new WeakMap();
    overlays.forEach(el=>{el.classList.add('security-overlay');const panel=el.querySelector('.modal,.drawer');panel?.setAttribute('role','dialog');panel?.setAttribute('aria-modal','true');if(panel&&!panel.hasAttribute('aria-labelledby'))panel.setAttribute('aria-label','Security details');});
    const focus=new MutationObserver(records=>records.forEach(({target:el})=>{if(!el.hidden){openers.set(el,document.activeElement);requestAnimationFrame(()=>{if(el.isConnected&&!el.hidden)el.querySelector('.modal-close-btn')?.focus();});}else if(openers.get(el)?.isConnected)openers.get(el).focus();}));
    overlays.forEach(el=>focus.observe(el,{attributes:true,attributeFilter:['hidden']}));
    const keys=e=>{const el=overlays.find(el=>!el.hidden);if(!el)return;if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();el.querySelector('.modal-close-btn')?.click();}if(e.key==='Tab'){const n=[...el.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter(n=>n.getClientRects().length);if(!n.length)return;if(e.shiftKey&&(document.activeElement===n[0]||!el.contains(document.activeElement))){e.preventDefault();n.at(-1).focus();}else if(!e.shiftKey&&(document.activeElement===n.at(-1)||!el.contains(document.activeElement))){e.preventDefault();n[0].focus();}}};document.addEventListener('keydown',keys,true);
    AAAPlatform.onViewLeave(()=>{observer.disconnect();focus.disconnect();document.removeEventListener('keydown',keys,true);view.removeEventListener('click',click,true);root.querySelectorAll('canvas').forEach(c=>window.Chart?.getChart(c)?.destroy());});
  }
  async function audit(id){
    const body=document.createElement('div');body.className='security-audit-body';body.textContent='Loading saved audit…';
    let active=true;const dialog=NetOpsUI.openDrawer({title:'Saved audit',body,beforeClose:()=>{active=false;return true;}});if(!dialog)return;AAAPlatform.onViewLeave(()=>{active=false;dialog.close();});
    try{const r=await OpsUI.request('/api/security/audits/'+encodeURIComponent(id));if(!active)return;
      body.innerHTML='<p>'+esc(r.device_name)+' · '+badge(r.status)+' · '+esc(r.source)+'</p><p class="cell-mono">'+esc(r.id)+'</p><p>Started '+esc(dt(r.started_at))+'<br>Completed '+esc(dt(r.completed_at))+'</p><p>Recorded score: '+esc(r.overall_score??'Unavailable')+'</p>'+(r.status!=='completed'?'<p class="security-note">This run is not a completed assessment. Historical failure detail is not supplied by the current audit response. Missing findings do not establish a pass or resolution.</p>':'')+'<p class="security-note">Saved observations; no manual resolution or suppression workflow.</p>';
      for(const f of [...r.findings,...r.correlation_findings]){
        const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=f.title+' · '+f.severity+' · '+f.status;details.append(summary);
        for(const [label,value] of [['Check',f.check_id],['Domain',f.domain],['Detail',f.detail],['Recommendation',f.recommendation||'No recommendation supplied.']]){const p=document.createElement('p');p.textContent=label+': '+value;details.append(p);}
        for(const [label,value] of [['Observed evidence',(f.evidence||[]).map(String).join('\n')],['Suggested configuration (not executed)',f.fix_command]]){if(!value)continue;const h=document.createElement('h3');h.textContent=label;const pre=document.createElement('pre');pre.className='security-evidence';pre.textContent=value;details.append(h,pre);}body.append(details);
      }
      if(!r.findings.length&&!r.correlation_findings.length){const p=document.createElement('p');p.textContent=r.status==='completed'?'No observations stored for this completed audit.':'Results unavailable for this run.';body.append(p);}evidence(body);
    }catch(e){if(active)body.textContent=e.message;}
  }
  window.SecurityUI={mount,scopeDocument,can,dt,badge,evidence,audit,safeFetch};
})();
