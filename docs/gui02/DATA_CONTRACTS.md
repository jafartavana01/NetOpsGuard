# Dashboard data contracts

A = existing direct data. B = presentation-only aggregation. C = future/unavailable.

| Widget | Class | Existing source | Meaning / constraint |
|---|---|---|---|
| Services, DB, build | A | GET /api/system/status; routes_system.system_status | Observed process state / DB probe; not end-to-end AAA health |
| Devices | B | GET /api/devices | Inventory length and enabled count; no online inference |
| AAA users / outcomes | A/B | GET /api/tacacs-accounting/health?hours=24&limit=2000 | Command decision tail; non-permit is not necessarily deny; totals not 24h-filtered |
| AAA chart | A | Same health API hourly_activity | Parsed timestamp buckets, last 24h, bounded sample |
| Sessions | A | GET /api/tacacs-accounting/sessions?active_only=true&limit=2000 | Accounting correlation, not live NAS proof |
| Authentication rate | B | GET /api/tacacs-accounting/access-events?kind=authentication&limit=10&since=... | Success / known outcomes; unknown shown separately; bounded ACCESS sample |
| Recent events | B | Above + kind=all authorization API | Merge timestamped samples; maximum 8; no invented session-start event |
| Security | A | GET /api/security/dashboard | Latest completed device audits; severity counts for FAIL checks; null score preserved |
| Backups | A | GET /api/ncm/overview | Success within 48h; no-job-history and latest-failure distinct |
| Recent snapshots | A | Same NCM overview | configurations_changed_recently counts stored snapshots, not actual differences |
| Drift | A | GET /api/ncm/drift | Archived running config vs baseline; coverage gaps separate |
| Candidate | A | GET /api/config/candidate | applicable, has_changes, diagnostics; no Apply mutation |
| Directory | A | GET /api/ad-settings/health, on demand | Strict-superadmin LDAP connection check; no enumeration required for dashboard refresh |
| Attention | B | Above available source observations | No new security decision engine; incomplete coverage disclosed |

Source implementations: app/api/routes_accounting.py (accounting_health, list_sessions, access-events helpers), routes_security.py (get_security_dashboard), routes_ncm.py (get_overview/get_drift), routes_config.py (candidate), routes_ad_settings.py (health_check); existing log/session and ad_directory services. Existing API and service code is unchanged.

## Future dashboard data contract (C)

- Explicit freshness, sample truncation and ingestion coverage for complete-window AAA metrics.
- Verified device reachability and active NAS sessions, distinct from enabled inventory and accounting correlation.
- Cached directory operational status with observation time, separate from identity authority and binding validity.
- True configuration-change events distinct from stored snapshots; precise last-success backup age/coverage.
- Audit age and SLA semantics before stale-audit alerts; explicit score bands if product-approved.
- Unified timestamped NCM/security activity only when event semantics exist.
- Protocol-specific RADIUS metrics; no TACACS-derived RADIUS claims.
- Explicit runtime identity-review alerts only after their backend semantics are implemented.
- RBAC-aware summary/capability API to reduce fan-out without weakening endpoint permissions.

None of these future contracts is implemented or fabricated in production GUI-02.
