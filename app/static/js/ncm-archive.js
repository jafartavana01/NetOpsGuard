window.OpsArchive = {mount() {
  const root=document.querySelector('.ops-workspace');
  if(!root || root.dataset.archiveMounted)return;
  root.dataset.archiveMounted='true';
  const view=root.closest('#view-root'),alive=()=>root.isConnected;
  const $=id=>view.querySelector('#'+id),esc=OpsUI.esc;
  let devices=[],rows=[],baselines=[],selected=new Set(),content='',lines=[],page=0,requestId=0,viewerRequest=0;
  const linePageSize=300;
  function renderExplorer(){
    const q=$('archive-device-search').value.toLowerCase(),group=$('archive-group').value;
    const list=devices.filter(d=>(!group||d.device_group_name===group)&&(!q||(d.device_name+' '+d.ip_address).toLowerCase().includes(q)));
    $('archive-explorer-list').innerHTML=list.length?list.map(d=>'<button type="button" class="ops-device" data-device="'+esc(d.device_id)+'" aria-pressed="'+($('filter-device').value===d.device_id)+'">'+esc(d.device_name)+'<small>'+esc(d.ip_address)+' · '+esc(d.device_group_name||'Ungrouped')+'</small><small>'+d.total_versions+' retained versions'+(d.last_backup_status==='failed'?' · Last backup failed':'')+'</small></button>').join(''):'<p class="ops-note">No devices match.</p>';
  }
  function render(){
    const type=$('filter-type').value,q=$('filter-search').value.toLowerCase();
    const list=rows.filter(r=>(!type||r.configuration_type===type)&&(!q||(r.device_name+' '+r.sha256).toLowerCase().includes(q)));
    const device=devices.find(d=>d.device_id===$('filter-device').value);
    $('archive-title').textContent=device?device.device_name+' · version history':'Recent archive · latest 500 versions';
    $('archive-context').textContent=device?(device.last_backup_status==='failed'?'Latest backup failed: '+(device.last_backup_error||'No detail recorded'):'Version history includes changed snapshots; unchanged backup attempts are recorded in Backup Jobs.'):'Select a device for its complete retained history. The global view shows the latest 500 versions.';
    $('archive-compare').disabled=selected.size!==2||!OpsUI.can('ncm:diff');
    $('archive-selection').textContent=selected.size+' of 2 versions selected';
    $('archive-table-wrap').innerHTML=list.length?'<table class="data-table"><thead><tr><th>Select</th><th>Device / version</th><th>Type</th><th>Size</th><th>Source</th><th>Archived</th><th>Actions</th></tr></thead><tbody>'+list.map(r=>{
      const b=baselines.find(b=>b.device_id===r.device_id&&b.configuration_type===r.configuration_type);
      return '<tr><td><input type="checkbox" data-select="'+esc(r.id)+'" aria-label="Select '+esc(r.device_name)+' version '+r.version_number+'" '+(selected.has(r.id)?'checked':'')+'></td><td>'+esc(r.device_name)+' <span class="cell-mono">#'+r.version_number+'</span><div class="content-sub" title="'+esc(r.sha256)+'">'+esc(r.sha256.slice(0,12))+'</div></td><td>'+esc(r.configuration_type)+'</td><td class="cell-mono">'+r.size_bytes+' B</td><td>'+esc(r.source)+'</td><td>'+esc(new Date(r.created_at).toLocaleString())+'</td><td class="cell-actions"><button class="btn-secondary btn-small" data-view="'+esc(r.id)+'">View</button>'+(b?.configuration_id&&b.configuration_id!==r.id&&OpsUI.can('ncm:diff')?'<a class="btn-secondary btn-small" href="/ncm/diff?device_id='+encodeURIComponent(r.device_id)+'&from='+encodeURIComponent(b.configuration_id)+'&to='+encodeURIComponent(r.id)+'">Compare baseline</a>':'')+'</td></tr>';
    }).join('')+'</tbody></table>':'<div class="empty-state"><strong>No archived configurations'+(device?' for '+esc(device.device_name):'')+'</strong><p>No snapshots match this selection. Check Backup Jobs for attempts and errors.</p><a href="/ncm/overview">Open backup overview</a></div>';
  }
  async function loadHistory(){
    const seq=++requestId,id=$('filter-device').value;selected.clear();renderExplorer();
    $('archive-table-wrap').textContent='Loading version history…';
    try{const data=await OpsUI.request(id?'/api/ncm/devices/'+encodeURIComponent(id)+'/history':'/api/ncm/configurations?limit=500');if(seq!==requestId||!alive())return;rows=data;render();}
    catch(e){if(seq===requestId&&alive()){$('archive-table-wrap').textContent=e.message;rows=[];$('archive-compare').disabled=true;}}
  }
  function renderViewer(){
    const q=$('viewer-search').value.toLowerCase();
    const indices=lines.map((_,i)=>i).filter(i=>!q||lines[i].toLowerCase().includes(q));
    page=Math.min(page,Math.max(0,Math.ceil(indices.length/linePageSize)-1));
    $('viewer-body').innerHTML=indices.slice(page*linePageSize,(page+1)*linePageSize).map(i=>'<div class="ncm-config-line'+(q?' is-match':'')+'"><span class="ncm-config-lineno">'+(i+1)+'</span><span class="ncm-config-text">'+esc(lines[i])+'</span></div>').join('');
    $('viewer-search-status').textContent=(q?indices.length+' matching lines · ':'')+'Showing '+(indices.length?page*linePageSize+1:0)+'–'+Math.min((page+1)*linePageSize,indices.length)+' of '+indices.length+' lines. Copy and download preserve the full original text.';
    $('viewer-prev').disabled=page===0;$('viewer-next').disabled=(page+1)*linePageSize>=indices.length;
  }
  async function openViewer(id){
    const seq=++viewerRequest;$('viewer-backdrop').hidden=false;$('viewer-body').textContent='Loading configuration…';$('viewer-meta').textContent='';$('viewer-search-status').textContent='';content='';lines=[];
    $('viewer-copy-btn').disabled=true;$('viewer-download-btn').hidden=true;
    try{const c=await OpsUI.request('/api/ncm/configurations/'+encodeURIComponent(id));if(seq!==viewerRequest||!alive())return;content=c.configuration_content;lines=content.split('\n');page=0;
      $('viewer-title').textContent=c.device_name+' — version #'+c.version_number;
      $('viewer-meta').textContent=c.configuration_type+' · '+c.source+' · '+new Date(c.created_at).toLocaleString()+' · SHA-256 '+c.sha256;
      $('viewer-download-btn').href='/api/ncm/configurations/'+encodeURIComponent(c.id)+'/download';$('viewer-download-btn').hidden=!OpsUI.can('ncm:download');$('viewer-copy-btn').disabled=false;$('viewer-search').value='';renderViewer();
    }catch(e){if(seq===viewerRequest&&alive())$('viewer-body').textContent=e.message;}
  }
  function close(){viewerRequest++;$('viewer-backdrop').hidden=true;}
  $('viewer-close-btn').onclick=close;
  $('viewer-backdrop').onclick=e=>{if(e.target===$('viewer-backdrop'))close();};
  $('viewer-search').oninput=()=>{page=0;renderViewer();};$('viewer-copy-btn').onclick=()=>OpsUI.copy(content);
  $('viewer-prev').onclick=()=>{page--;renderViewer();};$('viewer-next').onclick=()=>{page++;renderViewer();};
  $('viewer-wrap').onchange=e=>$('viewer-body').classList.toggle('ops-wrap',e.target.checked);
  $('viewer-expand').onclick=e=>{const expanded=$('viewer-backdrop').querySelector('.drawer').classList.toggle('ops-expanded');e.target.setAttribute('aria-pressed',String(expanded));};
  $('archive-table-wrap').onclick=e=>{const view=e.target.closest('[data-view]');if(view)openViewer(view.dataset.view);};
  $('archive-table-wrap').onchange=e=>{const id=e.target.dataset.select;if(!id)return;if(e.target.checked){const first=rows.find(r=>selected.has(r.id)),next=rows.find(r=>r.id===id);if(selected.size>=2||(first&&(first.device_id!==next.device_id||first.configuration_type!==next.configuration_type))){e.target.checked=false;AAAPlatform.toast('Choose two versions of the same device and configuration type.','error');return;}selected.add(id);}else selected.delete(id);$('archive-selection').textContent=selected.size+' of 2 versions selected';$('archive-compare').disabled=selected.size!==2||!OpsUI.can('ncm:diff');};
  $('archive-compare').onclick=()=>{const pair=rows.filter(r=>selected.has(r.id)).sort((a,b)=>new Date(a.created_at)-new Date(b.created_at)||a.version_number-b.version_number);if(pair.length===2&&OpsUI.can('ncm:diff'))location.href='/ncm/diff?device_id='+encodeURIComponent(pair[0].device_id)+'&from='+encodeURIComponent(pair[0].id)+'&to='+encodeURIComponent(pair[1].id);};
  $('archive-explorer-list').onclick=e=>{const b=e.target.closest('[data-device]');if(b){$('filter-device').value=b.dataset.device;loadHistory();}};
  $('filter-device').onchange=loadHistory;$('filter-type').onchange=render;$('filter-search').oninput=render;
  $('archive-device-search').oninput=renderExplorer;$('archive-group').onchange=renderExplorer;
  OpsUI.table('archive-table-wrap',{search:false});
  (async()=>{
    try{devices=await OpsUI.request('/api/ncm/devices');if(!alive())return;$('filter-device').innerHTML='<option value="">Recent archive</option>'+devices.map(d=>'<option value="'+esc(d.device_id)+'">'+esc(d.device_name)+'</option>').join('');$('archive-group').innerHTML='<option value="">All groups</option>'+[...new Set(devices.map(d=>d.device_group_name).filter(Boolean))].sort().map(g=>'<option>'+esc(g)+'</option>').join('');}
    catch(e){if(!alive())return;$('archive-explorer-list').textContent=e.message;return;}
    try{baselines=await OpsUI.request('/api/ncm/baselines');}catch{if(!alive())return;$('archive-baseline-state').textContent='Baseline links unavailable.';}
    if(!alive())return;
    const params=new URLSearchParams(location.search),id=params.get('device_id');if(id&&devices.some(d=>d.device_id===id))$('filter-device').value=id;
    await loadHistory();if(!alive())return;if(params.get('configuration_id'))openViewer(params.get('configuration_id'));
  })();
}};
