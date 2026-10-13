/* GUI-03 presentation helpers. No authorization evaluation or mutation. */
(function (root) {
  'use strict';
  const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function outcome(value, kind = 'authorization') {
    const v = String(value ?? '').trim().toLowerCase();
    // Only actual result tokens. Authentication success is NOT command permit.
    const positive = kind === 'authentication' ? v === 'success' : v === 'permit';
    const negative = kind === 'authentication' ? v === 'failure' : v === 'deny';
    return {tone: positive ? 'success' : negative ? 'danger' : 'neutral',
      label: positive ? (kind === 'authentication' ? 'Success' : 'Permitted') : negative ? (kind === 'authentication' ? 'Failure' : 'Denied') : 'Unknown',
      mark: positive ? 'check' : negative ? 'x' : 'minus'};
  }
  function outcomeBadge(value, kind) {
    const o = outcome(value, kind);
    const path = o.mark === 'check' ? '<path d="m7 12 3 3 7-7"/>' : o.mark === 'x' ? '<path d="m8 8 8 8m0-8-8 8"/>' : '<path d="M8 12h8"/>';
    return `<span class="aaa-outcome aaa-${o.tone}" title="Parsed result: ${escape(value || 'not supplied')}"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/>${path}</svg>${o.label}</span>`;
  }
  const DIM = {user:'who',user_group:'who',device:'where',device_group:'where',source_ip:'where'};
  const LABEL = {user:'User',user_group:'Group',device:'Device',device_group:'Device group',source_ip:'Source IP'};
  const OPS = {equal:'=',not_equal:'≠',is_in_cidr:'in CIDR',is_not_in_cidr:'not in CIDR'};
  function leaf(c, refs) {
    if (!c || !DIM[c.object_type] || !OPS[c.operator] || (c.object_type!=='source_ip' && !['equal','not_equal'].includes(c.operator))) return {text:'Unsupported condition — inspect configuration',dims:new Set(['unknown']),uncertain:true};
    let value = c.value, uncertain = false;
    if (c.object_type !== 'source_ip') {
      const obj = (refs[c.object_type] || []).find(r => r.id === c.referenced_object_id);
      value = obj ? (obj.username || obj.name) : `Unresolved reference (${c.referenced_object_id || 'missing ID'})`;
      uncertain = !obj;
      if (obj && c.object_type === 'user_group') value += ` [${obj.authority || 'LEGACY'}]`;
    } else if (!value) { value = 'Missing value'; uncertain = true; }
    return {text:`${LABEL[c.object_type]} ${OPS[c.operator]} ${value}`,dims:new Set([DIM[c.object_type]]),uncertain};
  }
  function treeSummary(tree, refs = {}, depth = 0) {
    if (!tree || depth > 40 || !['AND','OR','NOT'].includes(tree.logical_operator) || !Array.isArray(tree.conditions) || !Array.isArray(tree.child_groups))
      return {text:'Unresolved / unsupported condition tree',dims:new Set(['unknown']),uncertain:true,parts:[]};
    const parts = [...tree.conditions.map(c => leaf(c, refs)), ...tree.child_groups.map(g => treeSummary(g, refs, depth + 1))];
    if (!parts.length) return {text:'Empty condition tree — requires validation',dims:new Set(['unknown']),uncertain:true,parts};
    const inner = parts.map(p => p.text).join(tree.logical_operator === 'OR' ? ' OR ' : ' AND ');
    // The existing engine defines NOT as NOT(all child predicates).
    return {text:tree.logical_operator === 'NOT' ? `NOT (${inner})` : `(${inner})`,
      dims:new Set(parts.flatMap(p => [...p.dims])),uncertain:parts.some(p => p.uncertain),parts};
  }
  function policySummary(p, tree, refs = {}) {
    if (p.has_condition_tree) {
      const summary = treeSummary(tree, refs);
      let parts = summary.parts;
      if (!tree || tree.logical_operator !== 'AND') parts = [summary];
      const mixed = !parts.length || parts.some(s => s.dims.size > 1 || s.dims.has('unknown'));
      const dimension = d => {
        if (mixed) return summary.uncertain ? 'Unresolved scope — inspect' : 'Complex conditions';
        const selected = parts.filter(s => s.dims.has(d));
        return selected.length ? selected.map(s => s.text).join(' AND ') : 'Any (dimension unrestricted)';
      };
      return {who:dimension('who'),where:dimension('where'),full:summary.text,uncertain:summary.uncertain};
    }
    const clauses = [];
    const scope = (id, name, label) => {
      if (id) { const text = name ? `${label} = ${name}` : `${label}: Unresolved reference (${id})`; clauses.push(text); return text; }
      return null;
    };
    let who = scope(p.condition_group_id, p.condition_group_name, 'Group');
    if(who && p.condition_group_name) {
      const g=(refs.user_group || []).find(g=>g.id===p.condition_group_id);
      who += ` [${g?.authority || 'authority unavailable'}]`;
    }
    const device = scope(p.condition_device_id, p.condition_device_name, 'Device');
    const group = scope(p.condition_device_group_id, p.condition_device_group_name, 'Device group');
    return {who:who || 'Any (dimension unrestricted)',where:[device,group].filter(Boolean).join(' AND ') || 'Any (dimension unrestricted)',
      full:clauses.join(' AND ') || 'Unrestricted in stored legacy fields. Historical lost NULL scope cannot be distinguished here.',uncertain:clauses.some(s => s.includes('Unresolved reference'))};
  }
  function details(title, entries) {
    const body = document.createElement('div'); body.className = 'aaa-details';
    for (const [label, value] of entries) {
      const h = document.createElement('h3'); h.textContent = label;
      const p = document.createElement('p'); p.className = 'aaa-detail-value'; p.textContent = String(value ?? 'Not available');
      body.append(h, p);
    }
    const drawer = root.NetOpsUI.openDrawer({title,body});
    if (drawer) root.AAAPlatform.onViewLeave(() => drawer.close());
    return drawer;
  }
  async function suggestions(input, endpoint, field) {
    if (!input) return;
    try {
      const r=await root.AAAPlatform.authedFetch(endpoint);if(!r.ok)return;
      const rows=await r.json();if(!Array.isArray(rows)||!input.isConnected)return;
      const list=document.createElement('datalist');list.id=input.id+'-suggestions';
      rows.forEach(row=>{const option=document.createElement('option');option.value=row[field] || '';list.append(option);});
      document.getElementById(list.id)?.remove();input.after(list);input.setAttribute('list',list.id);
    } catch (_) { /* Optional suggestions: free text remains usable. */ }
  }
  async function policyReferences(userId, groupId) {
    try {
      const r=await root.AAAPlatform.authedFetch('/api/policies');if(!r.ok)return 'Policy references unavailable (permission or request failure).';
      const policies=await r.json();const names=[];let incomplete=false;
      function mentions(node,depth=0) {
        if(!node || depth>40){incomplete=true;return false;}
        return (node.conditions||[]).some(c=>(c.object_type==='user'&&c.referenced_object_id===userId)||(groupId&&c.object_type==='user_group'&&c.referenced_object_id===groupId)) || (node.child_groups||[]).some(g=>mentions(g,depth+1));
      }
      for(const p of policies){
        if(p.has_condition_tree){
          const t=await root.AAAPlatform.authedFetch('/api/policies/'+encodeURIComponent(p.id)+'/condition-tree');
          if(!t.ok){incomplete=true;continue;}const data=await t.json();if(mentions(data.tree))names.push(p.name);
        } else if(groupId && p.condition_group_id===groupId)names.push(p.name);
      }
      return (names.join(', ') || 'No direct references found')+(incomplete?' · Partial: some condition details unavailable.':'')+'\nReferences include negated conditions. Catch-all and indirect directory matches are not enumerated; this is not an effective-access result.';
    }catch(_){return 'Policy references unavailable; not an indication of no access.';}
  }
  async function candidateContext(box) {
    if(!box)return;
    box.textContent='Checking candidate validation context…';
    try {
      const r=await root.AAAPlatform.authedFetch('/api/config/candidate');
      if(!box.isConnected)return;
      if(!r.ok){box.textContent='Candidate validation unavailable. Analysis remains unverified; review Configuration with the required permission.';return;}
      const data=await r.json();if(!box.isConnected)return;
      if(data.applicable===false) {
        box.textContent='Invalid / blocked candidate. Evaluator results below cannot establish deployable access.\n'+(data.diagnostics||[]).map(d=>`${d.policy_name || 'Policy'} · ${d.code || 'validation error'}: ${d.reason || 'Review Configuration'}`).join('\n');
      } else if(data.applicable===true) {
        box.textContent='Candidate validation passed at page load. This does not verify simulator support or deployed access; later edits require a fresh Configuration review.';
      } else box.textContent='Candidate validity unknown. Analysis remains unverified.';
    }catch(_){if(box.isConnected)box.textContent='Candidate validation unavailable. Analysis remains unverified.';}
  }
  function inventoryTable(wrap) {
    const table = wrap.querySelector(':scope > table');
    if (!table || table.dataset.aaaEnhanced) return;
    table.dataset.aaaEnhanced = 'true';
    const rows = [...table.tBodies[0].rows];
    const bar = document.createElement('div'); bar.className = 'aaa-table-tools';
    const label = document.createElement('label'); label.textContent = 'Filter loaded rows';
    const input = document.createElement('input'); input.type = 'search'; input.placeholder = 'Name, scope, status…'; label.append(input);
    const count = document.createElement('span'); count.className = 'content-sub'; count.setAttribute('aria-live','polite');
    const prev = document.createElement('button'), next = document.createElement('button');
    for (const b of [prev,next]) { b.type='button'; b.className='btn-secondary btn-small'; }
    prev.textContent='Previous'; next.textContent='Next';
    const empty = document.createElement('p'); empty.className='empty-state'; empty.textContent='No loaded rows match this filter.'; empty.hidden=true;
    let page = 0; const size = 25;
    function render() {
      const q=input.value.trim().toLowerCase(), visible=rows.filter(r => r.textContent.toLowerCase().includes(q));
      page=Math.min(page,Math.max(0,Math.ceil(visible.length/size)-1));
      const selected=new Set(visible.slice(page*size,(page+1)*size));
      rows.forEach(r => { r.hidden=!selected.has(r); if(r.classList.contains('draggable-row')) r.draggable=!q && rows.length<=size; });
      count.textContent=`${visible.length ? page*size+1 : 0}–${Math.min((page+1)*size,visible.length)} of ${visible.length} loaded rows`;
      prev.disabled=page===0; next.disabled=(page+1)*size>=visible.length; empty.hidden=visible.length>0;
    }
    input.addEventListener('input',()=>{page=0;render();}); prev.addEventListener('click',()=>{page--;render();});next.addEventListener('click',()=>{page++;render();});
    bar.append(label,count,prev,next); wrap.prepend(bar);
    const scroller=document.createElement('div');scroller.className='aaa-table-scroll';scroller.tabIndex=0;scroller.setAttribute('role','region');scroller.setAttribute('aria-label','Scrollable results table');
    table.before(scroller);scroller.append(table);wrap.append(empty);render();
  }
  function mount() {
    const main=document.querySelector('#view-root .aaa-workspace');if(!main)return;
    main.querySelectorAll('[data-aaa-table]').forEach(inventoryTable);
  }
  const api={escape,outcome,outcomeBadge,treeSummary,policySummary,details,suggestions,policyReferences,candidateContext,mount};
  root.AAAWorkspace=api;
  if(typeof module!=='undefined')module.exports=api;
  if(typeof document!=='undefined') {
    document.addEventListener('DOMContentLoaded',()=>{
      const view=document.getElementById('view-root');if(!view)return;
      new MutationObserver(mount).observe(view,{childList:true,subtree:true});mount();
    });
  }
})(typeof window==='undefined'?globalThis:window);
