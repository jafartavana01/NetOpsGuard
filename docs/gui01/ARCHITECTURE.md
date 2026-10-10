# Frontend architecture inventory

## Request / render / navigation

`app/web/routes.py:dashboard_page` and module web routes call Jinja TemplateResponse with the current administrator and filtered navigation. TACACS+ pages use `routes_tacacs.py:_render`; platform, network operations, NCM, RADIUS and security route files have corresponding render helpers. They retain cookie authentication, module/license filtering and existing superadmin requirements.

`base.html` supplies CSS, app.js and GUI component helpers. `app_shell.html` supplies the persistent sidebar/header, global Apply modal, spa.js, gui-shell.js, status polling and pending-candidate polling. Feature templates populate `view_content` and `view_scripts`. `spa.js` fetches the same real HTML routes, updates #view-root/history/breadcrumb, cleans up the outgoing view and executes incoming view scripts.

The GUI navigation partial maps already-filtered server destinations into the new presentation groups. It cannot query or invent additional pages. Search consumes only those rendered DOM links. Menu visibility is not equivalent to all granular API permissions; the backend remains authoritative.

## Files / responsibilities

| File(s) | Responsibility |
|---|---|
| `app/modules/*_module.py`, `sidebar.py` | Existing destination ownership, server visibility and original grouping; unchanged |
| `app/web/routes*.py` | Existing authenticated HTML routes; unchanged |
| `templates/base.html` | Shared style/script dependency order |
| `templates/app_shell.html` | Persistent shell, global candidate presentation, view-script container |
| `templates/partials/sidebar.html` | Sidebar DOM, existing command-search markup, daemon status |
| `templates/partials/gui_navigation.html` | GUI grouping and future-destination fallback |
| `templates/partials/gui_components.html` | Opt-in safe Jinja component macros |
| `templates/partials/icons.html` | Existing SVG family; unchanged |
| `static/css/app.css` | Legacy compatibility/page styles; only old root token declarations removed |
| `static/css/gui-v2/*` | Canonical tokens and shared visual foundation |
| `static/js/app.js` | Existing authenticated fetch/CSRF, toast, cleanup, dirty-modal and generic feature helpers; unchanged |
| `static/js/spa.js` | Existing navigation; small mobile aria/Escape/focus adjustments |
| `static/js/gui-shell.js` | Collapse preference, navigation search/accordion, Ctrl+K search and help drawer |
| `static/js/gui-components.js` | Opt-in dialogs/drawers, badge helper and chart styling hook |
| `tests/gui01/*` | Synthetic preview, browser checks/screenshots and source/template contracts |

## Existing patterns retained

Cards: panel, status-card, dash-kpi and feature-specific panels. Tables: data-table, dynamic innerHTML rows with existing escaping, separate paging/filter code. Forms: native fields and icon wrappers, custom searchable selectors and toggles. Modals: modal-backdrop with feature-specific event/dirty-form logic; Security Findings also has its own drawer. Charts: repeated Chart.js 4.5.1 CDN loaders in Dashboard/Security Overview/report detail. No chart calculation or loader rewrite.

Machine-readable inventory lists all 55 templates, JavaScript files, inline-script templates, 851 style attributes and the feature-template migration backlog. Shared CSS compatibility intentionally takes precedence where safe; inline styles may still win and require explicit future migration.

## Test boundary

The preview server imports real navigation construction and renders real Jinja files, but supplies synthetic APIs and does not start FastAPI, authenticate a session, access the database or contact AAA services. Browser assertions verify presentation and interaction contracts, not live server RBAC or deployed policy enforcement.
