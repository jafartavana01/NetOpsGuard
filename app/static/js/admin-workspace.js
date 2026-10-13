/* GUI-06 presentation only. Server permissions and mutation APIs remain authoritative. */
(() => {
  'use strict';
  const esc = value => AAAPlatform.escapeHtml(String(value ?? ''));
  // Presentation masking, not a substitute for redaction at the log source.
  const redact = value => String(value ?? '')
    .replace(/-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)/g, '[private key redacted]')
    .replace(/\b((?:bind[_ -]?password|password|passwd|secret|api[_ -]?key|access[_ -]?token|session[_ -]?token|authorization|radius\.key|key)["']?\s*[=:]\s*)("(?:\\.|[^"\n])*"|'(?:\\.|[^'\n])*'|[^\n,;]+)/gi, '$1[redacted]')
    .replace(/([a-z][a-z0-9+.-]*:\/\/)[^\s/@:]+:[^\s/@]+@/gi, '$1[redacted]@');
  function view() {
    const root = document.querySelector('.admin-workspace');
    const doc = SecurityUI.scopeDocument();
    const $ = id => doc.getElementById(id);
    let alive = true;
    const watched = new Map();
    const cleanups = [];
    const error = (id, message) => { const el = typeof id === 'string' ? $(id) : id; if (el) { el.textContent = redact(message); el.hidden = false; } };
    const notice = message => { if (alive) error('admin-page-state', message); };
    async function request(url, options) {
      let response;
      try { response = await AAAPlatform.authedFetch(url, options); }
      catch { throw Error('Connection interrupted. Refresh the saved state before retrying a change.'); }
      if (!alive) throw Error('View closed.');
      let data = null;
      if (response.status !== 204) {
        try { data = await response.json(); } catch { throw Error('The server returned an unreadable response. Refresh before retrying.'); }
      }
      if (!response.ok) {
        const detail = typeof data?.detail === 'string' ? data.detail : Array.isArray(data?.detail) ? data.detail.map(d => d.msg).join('; ') : '';
        throw Error(response.status === 403 ? 'Access denied. Your account cannot perform this operation.' : response.status === 401 ? 'Session expired. Sign in again.' : redact(detail) || 'Request failed (' + response.status + ').');
      }
      return data;
    }
    const json = (method, data) => ({method, headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
    async function run(button, target, task, scope) {
      const btn = typeof button === 'string' ? $(button) : button;
      const owner = scope || btn?.closest('form') || btn;
      if (owner?.dataset.busy) return;
      const inputs = owner ? [...owner.querySelectorAll('input,select,textarea,button'), ...(owner.matches('button') ? [owner] : [])] : [];
      const previous = inputs.map(el => [el, el.disabled]);
      if (owner) {owner.dataset.busy = 'true';owner.setAttribute('aria-busy','true');}
      previous.forEach(([el]) => el.disabled = true);
      if (target && $(target)) $(target).hidden = true;
      try { await task(); }
      catch (e) { if (alive) error(target || 'admin-page-state', e.message); }
      finally { previous.forEach(([el, disabled]) => el.disabled = disabled); if (owner) {delete owner.dataset.busy;owner.removeAttribute('aria-busy');} }
    }
    function watch(id) {
      const form = $(id); if (!form || watched.has(form)) return;
      const label = document.createElement('p'); label.className = 'admin-form-state'; label.setAttribute('aria-live','polite'); form.prepend(label);
      const entry = {dirty:false,label}; watched.set(form,entry);
      const change = () => { entry.dirty=true;label.textContent='Unsaved changes'; };
      form.addEventListener('input', change); form.addEventListener('change', change);
    }
    function clean(id, message='') { const entry=watched.get($(id));if(entry){entry.dirty=false;entry.label.textContent=message;} }
    const dirty = id => !!watched.get($(id))?.dirty;
    function close(id) {
      const backdrop=$(id);const forms=[...backdrop.querySelectorAll('form')];
      if(forms.some(f=>f.dataset.busy))return false;
      if(forms.some(f=>watched.get(f)?.dirty)&&!window.confirm('Discard unsaved changes?'))return false;
      forms.forEach(f=>clean(f.id));backdrop.querySelectorAll('input[type=password],textarea[data-secret],input[type=file]').forEach(el=>el.value='');backdrop.hidden=true;return true;
    }
    // Existing dialog DOM, with scoped keyboard handling and cleanup on SPA leave.
    const overlays=[...doc.querySelectorAll('.modal-backdrop,.drawer-backdrop')],openers=new WeakMap();
    const observer=new MutationObserver(records=>records.forEach(({target})=>{
      if(!target.hidden){openers.set(target,document.activeElement);requestAnimationFrame(()=>{if(alive&&!target.hidden)target.querySelector('.modal-close-btn')?.focus({preventScroll:true});});}
      else if(openers.get(target)?.isConnected)openers.get(target).focus({preventScroll:true});
    }));
    overlays.forEach(el=>{el.classList.add('admin-overlay');const panel=el.querySelector('.modal,.drawer');if(panel){panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');const h=panel.querySelector('h2');if(h){h.id=h.id||el.id+'-heading';panel.setAttribute('aria-labelledby',h.id);}}observer.observe(el,{attributes:true,attributeFilter:['hidden']});});
    const keys=e=>{const el=overlays.find(x=>!x.hidden);if(!el)return;
      if(e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();el.querySelector('.modal-close-btn')?.click();}
      if(e.key==='Tab'){const items=[...el.querySelectorAll('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]')].filter(x=>x.getClientRects().length);if(!items.length)return;const first=items[0],last=items.at(-1);if(e.shiftKey&&(document.activeElement===first||!el.contains(document.activeElement))){e.preventDefault();last.focus();}else if(!e.shiftKey&&(document.activeElement===last||!el.contains(document.activeElement))){e.preventDefault();first.focus();}}
    };
    const unsaved=()=>[...watched.values()].some(e=>e.dirty);
    const leave=e=>{if(unsaved()){e.preventDefault();e.returnValue='';}};
    const navigation=e=>{const a=e.target.closest('a[href]');if(a&&!a.hasAttribute('download')&&!a.getAttribute('href').startsWith('#')&&unsaved()&&!window.confirm('Leave this page and discard unsaved changes?')){e.preventDefault();e.stopImmediatePropagation();}};
    document.addEventListener('keydown',keys,true);document.addEventListener('click',navigation,true);window.addEventListener('beforeunload',leave);
    AAAPlatform.onViewLeave(()=>{alive=false;observer.disconnect();document.removeEventListener('keydown',keys,true);document.removeEventListener('click',navigation,true);window.removeEventListener('beforeunload',leave);cleanups.forEach(f=>f());});
    function output(id,text) { const box=$(id);box.textContent=redact(text)||'(empty)';if(!box.previousElementSibling?.classList.contains('admin-copy')){const b=document.createElement('button');b.className='btn-secondary btn-small admin-copy';b.textContent='Copy displayed output';b.type='button';b.onclick=()=>OpsUI.copy(box.textContent);box.before(b);} }
    return {root,document:doc,$,request,json,run,watch,clean,dirty,close,error,notice,output,alive:()=>alive,cleanup:fn=>cleanups.push(fn)};
  }
  window.AdminUI={view,esc,redact};
})();
