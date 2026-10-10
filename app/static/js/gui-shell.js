/* Presentation-only shell. Navigation is read from server-authorized DOM links. */
(function () {
  const sidebar = document.getElementById('app-sidebar'); if (!sidebar) return;
  const collapse = document.getElementById('sidebar-collapse-btn');
  const sections = [...sidebar.querySelectorAll('.nav-section')];
  const search = document.getElementById('nav-search-input');
  function setCollapsed(value) {
    document.body.classList.toggle('sidebar-collapsed',value);
    collapse.setAttribute('aria-expanded',String(!value));
    collapse.title = collapse.ariaLabel = value ? 'Expand sidebar' : 'Collapse sidebar';
    try { localStorage.setItem('netopsguard.sidebar.collapsed',String(value)); } catch (_) { /* preference unavailable */ }
  }
  let preference = false;
  try { preference = localStorage.getItem('netopsguard.sidebar.collapsed') === 'true'; } catch (_) {}
  setCollapsed(preference);
  collapse.addEventListener('click',() => setCollapsed(!document.body.classList.contains('sidebar-collapsed')));
  function openSection(section,open) {
    section.classList.toggle('is-collapsed',!open);
    section.querySelector('button').setAttribute('aria-expanded',String(open));
  }
  function active() {
    sidebar.querySelectorAll('.nav-item').forEach(link => {
      if(link.classList.contains('active')) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current');
    });
    sections.forEach(section => { const yes=!!section.querySelector('.active'); section.classList.toggle('has-active',yes); openSection(section,yes); });
    if (search.value) filter(search.value);
  }
  sections.forEach(section => section.querySelector('button').addEventListener('click',() => {
    const wasCollapsed=document.body.classList.contains('sidebar-collapsed');
    if (wasCollapsed) setCollapsed(false);
    const open=wasCollapsed || section.classList.contains('is-collapsed');
    sections.forEach(other => openSection(other,other===section && open));
  }));
  function filter(value) {
    const q=value.trim().toLowerCase(); let matches=0;
    sidebar.querySelectorAll('.nav-item').forEach(link => {
      const match=(link.dataset.keywords || link.textContent).toLowerCase().includes(q);
      link.toggleAttribute('data-search-hidden',!match); if(match) matches++;
    });
    sections.forEach(section => { const yes=!!section.querySelector('.nav-item:not([data-search-hidden])'); section.toggleAttribute('data-search-hidden',!yes); if(q && yes) openSection(section,true); });
    document.getElementById('nav-empty').hidden=matches>0;
    if(!q) sections.forEach(section=>openSection(section,!!section.querySelector('.active')));
  }
  search.addEventListener('input',()=>filter(search.value));
  search.addEventListener('keydown',e=>{if(e.key==='Escape'){search.value='';filter('');}});
  document.addEventListener('spa:navigated',() => { active(); const root=document.getElementById('view-root'); root.focus({preventScroll:true}); });
  active();
  const palette=document.getElementById('cmdk-backdrop'),input=document.getElementById('cmdk-input'),results=document.getElementById('cmdk-results');
  let opener=null,selected=0;
  function render(query) {
    results.replaceChildren(); selected=0;
    [...sidebar.querySelectorAll('a.nav-item')].filter(link=>(link.dataset.keywords || link.textContent).toLowerCase().includes(query.toLowerCase())).forEach(link => {
      const item=document.createElement('a'); item.href=link.getAttribute('href'); item.className='cmdk-item'; item.textContent=link.textContent.trim(); item.addEventListener('click',closePalette); results.append(item);
    });
    if(!results.children.length){const empty=document.createElement('p');empty.className='cmdk-empty';empty.textContent='No matching destinations.';results.append(empty);}
    highlight();
  }
  function highlight(){[...results.querySelectorAll('a')].forEach((link,i)=>link.classList.toggle('is-selected',i===selected));results.querySelector('.is-selected')?.scrollIntoView({block:'nearest'});}
  function closePalette(){palette.hidden=true;if(opener?.isConnected)opener.focus();}
  function openPalette(){opener=document.activeElement;palette.hidden=false;input.value='';render('');input.focus();}
  input.addEventListener('input',()=>render(input.value));
  palette.addEventListener('click',e=>{if(e.target===palette)closePalette();});
  document.addEventListener('keydown',e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){
      if(document.querySelector('.gui-dialog-backdrop'))return;
      e.preventDefault();palette.hidden?openPalette():closePalette();
    }
    if(palette.hidden)return;
    if(e.key==='Escape'){e.preventDefault();closePalette();}
    if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();selected=Math.max(0,Math.min(results.querySelectorAll('a').length-1,selected+(e.key==='ArrowDown'?1:-1)));highlight();}
    if(e.key==='Enter'&&document.activeElement===input){e.preventDefault();results.querySelectorAll('a')[selected]?.click();}
    if(e.key==='Tab'){const links=[input,...results.querySelectorAll('a')];const first=links[0],last=links.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
  });
  document.getElementById('shell-help-btn').addEventListener('click',()=>{
    const body=document.createElement('div');body.className='stack';
    for(const text of ['Use Ctrl+K to find a destination available to your account.','Collapse the sidebar for more workspace. Select a section icon to expand its destinations.','Configuration changes still require a valid candidate and explicit Apply. Blocked configuration diagnostics remain available on the Configuration page.','The displayed menu follows existing module, license and administrator visibility. Server permissions remain authoritative.']){const p=document.createElement('p');p.textContent=text;body.append(p);}
    NetOpsUI.openDrawer({title:'Console help',body});
  });
})();
