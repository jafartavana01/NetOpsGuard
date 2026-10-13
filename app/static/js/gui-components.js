/* GUI-01 opt-in components. Feature editors remain on their existing handlers. */
(function () {
  const escape = window.AAAPlatform.escapeHtml;
  let current = null;
  const focusables = 'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]';
  function openDialog({ title, body, footer, tabs, drawer = false, beforeClose = () => true }) {
    if (current) return null; // No implicit replacement/discard of an open editor.
    const returnFocus = document.activeElement;
    const backdrop = document.createElement('div');
    backdrop.className = 'gui-dialog-backdrop' + (drawer ? ' gui-drawer-backdrop' : '');
    const panel = document.createElement('section');
    panel.className = 'gui-dialog' + (drawer ? ' gui-drawer' : '');
    panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-labelledby', 'gui-dialog-title'); panel.tabIndex = -1;
    const header = document.createElement('header'); header.className = 'gui-dialog-header';
    const heading = document.createElement('h2'); heading.id = 'gui-dialog-title'; heading.textContent = title;
    const closeButton = document.createElement('button'); closeButton.className = 'shell-icon-button'; closeButton.type = 'button';
    closeButton.textContent = '×'; closeButton.setAttribute('aria-label', 'Close ' + title);
    header.append(heading, closeButton); panel.append(header);
    // Content is a DOM node or text, never an untrusted HTML string.
    if (tabs) { const nav = document.createElement('nav'); nav.className = 'gui-dialog-tabs'; nav.setAttribute('aria-label','Editor sections'); nav.append(tabs); panel.append(nav); }
    const content = document.createElement('div'); content.className = 'gui-dialog-body'; content.append(body); panel.append(content);
    if (footer) { const actions = document.createElement('footer'); actions.className = 'gui-dialog-footer'; actions.append(footer); panel.append(actions); }
    backdrop.append(panel); document.body.append(backdrop);
    const shell = document.querySelector('.app-shell'); const wasInert = shell?.inert;
    if (shell) shell.inert = true;
    const previousOverflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
    let closing = false;
    async function close() {
      if (closing || panel.getAttribute('aria-busy') === 'true') return false;
      closing = true;
      try { if (await beforeClose() === false) return false;
        backdrop.remove(); if (shell) shell.inert = wasInert; document.body.style.overflow = previousOverflow;
        current = null; if (returnFocus?.isConnected) returnFocus.focus(); return true;
      } finally { closing = false; }
    }
    closeButton.addEventListener('click', close);
    backdrop.addEventListener('click', e => { if (e.target === backdrop) close(); });
    current = { panel, close };
    (panel.querySelector('[autofocus]') || closeButton).focus();
    return current;
  }
  document.addEventListener('keydown', e => {
    if (!current) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); current.close(); }
    if (e.key === 'Tab') {
      const items = [...current.panel.querySelectorAll(focusables)].filter(el => el.getClientRects().length);
      const first = items[0] || current.panel; const last = items.at(-1) || first;
      if (e.shiftKey && (document.activeElement === first || !current.panel.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (document.activeElement === last || !current.panel.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
    }
  }, true);
  function chartOptions() {
    const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return { color:css('--text-secondary'), borderColor:css('--border-subtle'),
      font:{family:css('--font-ui'),size:12}, animation:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? false : {duration:200},
      palette:{success:css('--success'),info:css('--info'),warning:css('--warning'),danger:css('--danger')} };
  }
  window.NetOpsUI = { openDialog, openDrawer: options => openDialog({...options,drawer:true}), chartOptions,
    badge: (label, tone = 'neutral') => '<span class="badge badge-' + (['success','info','warning','danger','neutral'].includes(tone) ? tone : 'neutral') + '">' + escape(label) + '</span>' };
})();
