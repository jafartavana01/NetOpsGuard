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
  function comparisonControls(root, runs) {
    if (!root) return;
    root.innerHTML='<h2>Compare audit evidence</h2><p class="security-note">Choose two runs for the same device. Missing findings never establish remediation. Uploaded evidence is assessed as supplied, not independently verified against the device.</p><div class="filter-bar"><label>Previous audit <select data-previous aria-label="Previous audit"></select></label><label>Newer audit <select data-current aria-label="Newer audit"></select></label><button type="button" class="btn-secondary btn-small" data-compare>Compare</button></div><div data-result role="status" aria-live="polite"></div>';
    const previous=root.querySelector('[data-previous]'),current=root.querySelector('[data-current]'),button=root.querySelector('[data-compare]'),body=root.querySelector('[data-result]');
    for(const run of runs){for(const select of [previous,current]){const option=document.createElement('option');option.value=run.id||run.audit_run_id;option.textContent=run.device_name+' · '+dt(run.started_at)+' · '+run.source+' · '+run.status+' · '+option.value.slice(0,8);select.append(option);}}
    previous.selectedIndex=runs.length>1?1:0;
    button.disabled=runs.length<2;
    if(runs.length<2)body.textContent='Two recorded audit runs are required.';
    let active=true;
    AAAPlatform.onViewLeave(()=>{active=false;});
    button.onclick=async()=>{
      button.disabled=true;body.textContent='Comparing recorded evidence…';
      try{
        const response=await safeFetch('/api/security/audits/'+encodeURIComponent(previous.value)+'/compare/'+encodeURIComponent(current.value));
        let data;
        try { data=await response.json(); } catch { throw Error('Comparison response unavailable. No resolution is inferred.'); }
        if(!response.ok)throw Error(response.status===403?'Permission denied. Your role does not allow this operation.':response.status===401?'Session expired. Sign in again.':typeof data.detail==='string'?data.detail:'Comparison unavailable. No resolution is inferred.');
        if(!active)return;
        body.replaceChildren();
        const intro=document.createElement('p');intro.textContent=data.device_name+' · Previous '+data.from_run_id+' → Newer '+data.to_run_id;body.append(intro);
        const score=document.createElement('p');score.textContent=data.score_delta==null?'Score change unavailable: '+data.score_reason:'Comparable score change: '+(data.score_delta>0?'+':'')+data.score_delta;body.append(score);
        for(const warning of data.warnings||[]){const p=document.createElement('p');p.className='security-note';p.textContent=warning;body.append(p);}
        const labels={new:'New regression',first_observed:'First observed',resolved:'Confirmed resolved',persistent:'Persistent',indeterminate:'Indeterminate',manual_review:'Manual review'};
        for(const [category,label] of Object.entries(labels)){
          const section=document.createElement('section'),h=document.createElement('h3');h.textContent=label+' ('+(data.counts[category]||0)+')';section.append(h);
          for(const item of data.comparisons.filter(i=>i.category===category)){
            const details=document.createElement('details'),summary=document.createElement('summary');
            const sample=item.current[0]||item.previous[0];summary.textContent=item.key[1]+' · '+item.key[0]+' · '+(item.key[2]||'Device-wide')+' · '+sample.title;details.append(summary);
            const reason=document.createElement('p');reason.textContent=item.reason;details.append(reason);
            for(const [label,findings] of [['Previous',item.previous],['Newer',item.current]]){
              const title=document.createElement('h4');title.textContent=label+' evidence';details.append(title);
              if(!findings.length){const p=document.createElement('p');p.textContent='Not evaluated / no stored observation.';details.append(p);}
              for(const f of findings){const p=document.createElement('p');p.textContent='Status: '+f.status+' · Severity: '+f.severity;const pre=document.createElement('pre');pre.className='security-evidence';pre.textContent=(f.evidence||[]).join('\n')||'No separate evidence excerpts recorded; comparison requires a verified configuration capture and assessment manifest.';details.append(p,pre);}
            }
            section.append(details);
          }
          body.append(section);
        }
        evidence(body);
      }catch(e){if(active)body.textContent=e.message||'Comparison unavailable. No resolution is inferred.';}
      finally{if(active)button.disabled=runs.length<2;}
    };
  }
  window.SecurityUI={mount,scopeDocument,can,dt,badge,evidence,audit,safeFetch,comparisonControls};
})();
