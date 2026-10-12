/* Presentation helpers only. Existing endpoints remain authoritative. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => AAAPlatform.escapeHtml(String(value ?? ''));
  function can(key) {
    try { return JSON.parse($('operations-permissions')?.textContent || '[]').includes(key); }
    catch { return false; }
  }
  function mount() {
    const root = document.querySelector('.ops-workspace');
    if (!root || root.dataset.mounted) return;
    root.dataset.mounted = 'true';
    const scope = root.closest('#view-root');
    const grants = location.pathname.startsWith('/ncm/') ? {
      '#open-backup-modal-btn,#run-backup-btn':'ncm:backup',
      '#viewer-download-btn':'ncm:download',
      '#run-compare-btn,#raw-diff-btn,#run-diff-btn,#current-prev-btn,a[href^="/ncm/diff?"]':'ncm:diff',
      '#add-schedule-btn,#schedule-form button[type=submit],[data-edit],[data-delete],[data-set-baseline],#baseline-save':'ncm:schedule',
      '#new-candidate-btn,#candidate-form button[type=submit],[data-action=submit]':'ncm:propose',
      '[data-action=approve],[data-action=reject]':'ncm:approve',
      '[data-action=deploy],[data-rollback]':'ncm:deploy',
    } : {
      '#new-job-btn,#job-form button[type=submit],#run-checks-btn,#run-audit-btn':'network_ops:execute',
      '#add-template-btn,#template-form button[type=submit],[data-edit],[data-delete],#add-audit-btn,#audit-form button[type=submit]':'network_ops:templates',
    };
    function permissions() {
      for (const [selector,key] of Object.entries(grants)) {
        scope.querySelectorAll(selector).forEach(el => {
          if (!can(key)) {el.dataset.opsDenied='true';el.setAttribute('aria-disabled','true');if('disabled' in el)el.disabled=true;}
        });
      }
    }
    permissions();
    const observer = new MutationObserver(permissions);
    observer.observe(scope,{childList:true,subtree:true});
    const denyClick=e=>{if(e.target.closest('[data-ops-denied]')){e.preventDefault();e.stopImmediatePropagation();}};
    scope.addEventListener('click',denyClick,true);
    // Adapt existing feature dialogs without replacing their save/close handlers.
    const overlays=[...scope.querySelectorAll('.modal-backdrop,.drawer-backdrop')];
    const openers=new WeakMap();
    overlays.forEach(el=>{el.classList.add('ops-overlay');const panel=el.querySelector('.modal,.drawer');if(panel){panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.tabIndex=-1;const heading=panel.querySelector('h2');if(heading){if(!heading.id)heading.id=el.id+'-title';panel.setAttribute('aria-labelledby',heading.id);}}});
    const focusObserver=new MutationObserver(records=>{for(const m of records){const el=m.target;if(!overlays.includes(el))continue;if(!el.hidden){openers.set(el,document.activeElement);requestAnimationFrame(()=>{if(!el.hidden)el.querySelector('.modal-close-btn,button,input,select')?.focus();});}else{const opener=openers.get(el);if(opener?.isConnected)opener.focus();}}});
    overlays.forEach(el=>focusObserver.observe(el,{attributes:true,attributeFilter:['hidden']}));
    const keys=e=>{const el=overlays.find(el=>!el.hidden);if(!el)return;if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();el.querySelector('.modal-close-btn')?.click();}if(e.key==='Tab'){const nodes=[...el.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter(n=>n.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(!first)return;if(e.shiftKey&&(document.activeElement===first||!el.contains(document.activeElement))){e.preventDefault();last.focus();}else if(!e.shiftKey&&(document.activeElement===last||!el.contains(document.activeElement))){e.preventDefault();first.focus();}}};
    document.addEventListener('keydown',keys,true);
    AAAPlatform.onViewLeave(()=>{observer.disconnect();focusObserver.disconnect();scope.removeEventListener('click',denyClick,true);document.removeEventListener('keydown',keys,true);});
    scope.querySelectorAll('input[placeholder],select').forEach(el=>{
      if(!el.labels?.length&&!el.hasAttribute('aria-label'))el.setAttribute('aria-label',el.placeholder||el.id.replaceAll('-',' '));
    });
  }
  function table(id,{search=true,pageSize=25}={}) {
    const wrap=$(id);if(!wrap)return;
    wrap.classList.add('ops-table');
    function attach(){
      const t=wrap.querySelector('table');if(!t||t.dataset.opsTable)return;
      t.dataset.opsTable='true';
      wrap.querySelector('.ops-table-tools')?.remove();
      const rows=[...t.tBodies[0].rows];let page=0;
      const bar=document.createElement('div');bar.className='ops-table-tools';
      bar.innerHTML=(search?'<input type="search" aria-label="Filter loaded rows" placeholder="Filter loaded rows…">':'')+'<span aria-live="polite"></span><button type="button" class="btn-secondary btn-small">Previous</button><button type="button" class="btn-secondary btn-small">Next</button>';
      wrap.insertBefore(bar,t);
      const input=bar.querySelector('input'),info=bar.querySelector('span'),[prev,next]=bar.querySelectorAll('button');
      function render(){const q=input?.value.toLowerCase()||'';const list=rows.filter(r=>r.textContent.toLowerCase().includes(q));page=Math.min(page,Math.max(0,Math.ceil(list.length/pageSize)-1));rows.forEach(r=>r.hidden=true);list.slice(page*pageSize,(page+1)*pageSize).forEach(r=>r.hidden=false);info.textContent=`${list.length? page*pageSize+1:0}–${Math.min((page+1)*pageSize,list.length)} of ${list.length} loaded rows`;prev.disabled=page===0;next.disabled=(page+1)*pageSize>=list.length;}
      input?.addEventListener('input',()=>{page=0;render();});prev.onclick=()=>{page--;render();};next.onclick=()=>{page++;render();};render();
    }
    attach();const observer=new MutationObserver(attach);observer.observe(wrap,{childList:true});
    AAAPlatform.onViewLeave(()=>observer.disconnect());
  }
  function pickerFilter(listId,placeholder='Search devices or groups…') {
    const list=$(listId);if(!list)return;
    const input=document.createElement('input');input.type='search';input.placeholder=placeholder;input.setAttribute('aria-label',placeholder);input.className='ops-picker-search';
    list.before(input);input.addEventListener('input',()=>{list.querySelectorAll('label').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(input.value.toLowerCase()));});
  }
  async function request(url,options) {
    const res=await AAAPlatform.authedFetch(url,options);
    if(!res.ok)throw Error(res.status===403?'Your role does not allow this operation.':'Unable to load this data. Try again.');
    return res.json();
  }
  async function copy(text) {try{await navigator.clipboard.writeText(text);AAAPlatform.toast('Copied.');}catch{AAAPlatform.toast('Clipboard access was blocked.','error');}}
  window.OpsUI={mount,can,table,pickerFilter,request,copy,esc};
})();
