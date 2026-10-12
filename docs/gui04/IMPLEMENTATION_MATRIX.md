# GUI-04 implementation inventory

Baseline: NetOpsGuard-Dependency-Aware-Deletion.zip. Existing engines and API contracts remain authoritative.

| Page / feature | Existing backend support | State | GUI change / boundary |
|---|---|---|---|
| NCM Overview | GET /api/ncm/overview, /devices, /drift, /deployments; POST /backup | Implemented | Precise enabled-device KPI labels, archive timestamps distinct from backup attempts; attention links; running count; coverage filters |
| Archive | GET /configurations (max 1000, no offset), /devices/{id}/history, /configurations/{id}, /download | Implemented | Device explorer includes never archived devices; per-device history avoids global cap; bounded viewer, exact copy, wrap and expand; diff links (job-to-version link on Jobs) |
| Compare | POST /compare, /diff; ncm_compare.py category normalization and majority score | Implemented | Keep scoring; reject devices with no running snapshot; accessible selection; explain textual comparison limits |
| Diff | POST /diff/detailed provides aligned rows, changes/categories; ncm_diff_detail.py | Implemented | Preserve engine rows; exact preset IDs; search/change navigation; bounded pages; raw unified copy |
| Baselines/drift | GET /drift, /baselines; PUT/DELETE /devices/{id}/baseline; ncm_drift.py | Implemented | Exact baseline-to-latest links, archive-only status, no fabricated detection timestamps or live compliance |
| Jobs | GET /jobs (limited), /jobs/{id}; NcmBackupJob/Target | Implemented | Label loaded-job metrics; filter/page, completion timestamps and snapshot links; poll actual running jobs |
| Schedules | GET/POST /schedules, PUT/DELETE /schedules/{id}; ncm_scheduler.py | Implemented | Daily server-local schedule only; searchable targets, explicit missing targets, validation and unsaved confirmation |
| Change control | GET/POST /candidates; submit/review/deploy; GET /deployments and rollback | Implemented | Preserve confirmations/permissions/states; distinguish execution from verified intent; version links and failures |
| SSH command jobs + details | routes_network_ops.py, network_ops_jobs.html, network_ops_job_detail.html | Implemented | Shared workspace navigation, table tools and layout; retain polling/execution |
| Command templates | network_ops_templates.html, existing templates API | Implemented | Shared design and navigation; retain CRUD |
| Checks/audits bookmarked legacy pages | routes_network_ops_checks.py, routes_network_ops_audits.py | Implemented, hidden in menu | Apply shared layout only; keep canonical Security Center navigation, no duplicate menu |
| Discovery/monitoring | Existing Device Inventory controls and monitoring/scan APIs | Implemented | Link to existing Devices page, do not create duplicate pages |
| Scheduled next run, schedule last result | No authoritative next-run/result fields in schedule response | Unsupported directly | Display daily server-local time and recorded last run; no guessed timestamps |
| Cancel backup job; automatic remediation | No supported endpoint | Unsupported | No buttons added |
| Persisted drift detection time, operational equivalence | Not supplied/proven | Unsupported | Explicitly distinguish archive comparison from live device verification |

## Source map

NCM web routes: app/web/routes_ncm.py. API and permissions: app/api/routes_ncm.py. Models: NcmConfiguration, NcmBackupJob, NcmBackupJobTarget, NcmBackupSchedule, NcmBaseline, NcmCandidate, NcmDeployment in app/models/ncm.py. Payloads/responses: app/schemas/ncm.py. Services: ncm_backup, ncm_archive, ncm_drivers, ncm_compare, ncm_diff_detail, ncm_drift, ncm_scheduler, ncm_deploy. SSH credential/host-key paths remain unchanged. Network Operations: app/web/routes_network_ops.py, app/api/routes_network_ops*.py, app/modules/network_ops_module.py. Shared shell: app_shell.html, GUI-01 tokens/components/gui.js; GUI-03 and dependency deletion remain intact.

## Narrow presentation backend addition

GET /api/auth/me exposes only username and is_superadmin; it does not provide granular permissions. Existing NCM templates have no per-action permission context. To avoid a new API and preserve RBAC, the two web renderers supply a presentation-only permission list using the existing require_permission implementation. API checks remain unchanged and authoritative. No data/engine/model changes were made.

## Implementation sequence and verification

Overview → Archive → Compare → Diff → Drift → Jobs → Schedules → Change control → Network Operations integration. Reuse one scoped stylesheet, table tools and selection helpers. Execute focused actual-template browser cases as each section is completed, then all historical regression scripts and browser suites. Screenshots use synthetic fixture data only. PostgreSQL remains a separately reported integration gate.
