# GUI-05 capability inventory and implementation plan

Baseline: NetOpsGuard-GUI-04.zip. Inspected before production modification.

| Page | Feature | Backend support | Current GUI | Required improvement |
|---|---|---|---|---|
| Overview | Posture, severity, domains, risky devices, heatmap | Implemented: /api/security/dashboard, latest completed device audits | Charts/cards, limited population labels | Compact layout, precise populations, inventory coverage, observed activity, actionable links |
| Devices | Inventory + last completed audit | Implemented: /api/security/devices, all inventory including unaudited | Filters + bulk selection; missing score treated unaudited and lower risk called Healthy | Audit identity defines audited state; keep unknown score; sorting/paging; actual risk labels; critical/high counts from findings |
| Device detail | Audit findings, interfaces, domains, compliance | Implemented: /devices/{id}/audits and /audits/{id} | Latest result and history without run navigation | Saved-audit drawer, full history links, exact evidence tools, mapped status counts |
| Findings | Latest completed audit observations | Implemented: /findings; severity/device/domain/status | Filters and drawer, no clear-all or saved audit link | Visible active filters, clear, audit navigation, exact copy/wrap, no invented lifecycle |
| Findings | Open/resolved/accepted/suppressed workflows | Unsupported: actual statuses pass/fail/na/manual_review/warn | No persistence | Describe observations; do not add actions |
| Compliance | Framework/control aggregation and details | Implemented: /compliance and /compliance/{framework}/{control} | Framework panels/control drawer | Framework/status/search filters, mapped technical assessment language, related findings |
| Compliance | Unevaluated controls | Partially implemented: missing frameworks omitted; na means not applicable; control-detail na also when no results | May conflate absence and NA | Explicit not-evaluated empty state, preserve actual na meaning, no guessed count |
| History | All runs for a device; recent activity fleet-wide | Implemented: /devices/{id}/audits; /activity max100 (looks back200 runs) | Device history table, 15 activity rows | Reports/history workspace; saved audits including standalone upload via drawer |
| History | Added/resolved comparison | Partially implemented: /audits/{from}/compare/{to} lacks same-device/completed guards and folds absent checks into resolved | Not exposed | Do not enable unsafe lifecycle conclusions; document separate backend review |
| Reports | Numbered batch summaries | Implemented: /batches latest20; /batches/{number} | Web report/dashboard | Discovery filters, metadata, separate execution/risk, latest-device links labeled |
| Reports | PDF/CSV/download engine | Unsupported: no export endpoint | Web only | Preserve web report, no fake download |
| Scheduled audit | One global daily fleet job + shared SSH credential | Implemented: /schedule superadmin GET/PUT; /schedule/run-now; scheduled_audit.py | Form without robust network/single-flight state | Explicit fixed target, preserve blank password, validation/cancel, actual last result |
| Schedule | Named/multiple schedules, groups, next run | Unsupported | None | Do not invent fields or target selector |
| Schedule | Time zone | Implemented execution uses datetime.now(timezone.utc); schema/comments say server-local | Label server-local | Label UTC (actual behavior), document contradiction; no scheduler change |
| Audit failure | status/source/times | Implemented; error_message persisted but excluded from audit and batch response schemas | Generic error on requests | Show actual status, live request detail/last summary; state historical error unavailable |
| Related configuration | Device ID shared with NCM | Implemented: existing NCM routes/history and inventory | Existing NCM panel/backups | Context links, preserve authorization and explicit actions |
| Permissions | security:view, security:audit; schedule superadmin | Implemented existing dependencies | Some action buttons shown to all | Presentation-only permission projection using existing dependency; API unchanged |

## Implementation map

Web: app/web/routes_security.py (eight routes). API: app/api/routes_security.py. Schemas: app/schemas/security_audit.py. Models: AuditRun/AuditFinding/AuditDomainScore/AuditComplianceResult in app/models/audit_run.py; AuditBatch; AuditScheduleSettings. Persistence: app/services/security_audit_persistence.py. Scheduled collection: app/services/scheduled_audit.py. Engine: app/security_center/engine/orchestrator.py, finding.py, scoring.py, correlation.py; Cisco/device and interface checks/parser. Four mapping JSON files and loader under app/security_center/compliance. Templates: security_overview/devices/device_detail/findings/compliance/reports/report_detail/schedule.html. Existing styles app.css + GUI-01 tokens/components. Device inventory NetworkDevice is shared; vendor isn't included in SecurityDeviceOut.

Scoring uses persisted engine values. Status WARN earns half credit, MANUAL no credit with denominator retained, NA excluded; no formula changes. Risk values are Critical/Severe/High/Medium/Low/Minimal from the engine. Fail severity is critical/high/medium/low/info. Dashboard severity counts FAIL only. Device detail compliance currently displays non-failing percentage, conflating manual/NA with passing; replace this presentation with actual control status counts, not a new score.

## Design boundary

Reuse GUI tokens, OpsUI table tools and NetOpsUI drawers. Add one Security workspace partial, scoped stylesheet, small presentation helper and web permission context. Preserve existing eight templates and their supported actions/charts. No API, models, engine, mapping, scheduler or persistence changes. No lifecycle inference from missing/failed audits. No live directory/device verification in fixture screenshots. GUI-06 and Phase 2B stopped.
