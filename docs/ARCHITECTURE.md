# Architecture

NetOpsGuard has a management plane and an AAA data plane.

The management plane is a FastAPI application served by Uvicorn, with Jinja templates and browser JavaScript. PostgreSQL stores inventory, identity objects, policies, job state and history. `app/main.py` registers modules; `app/api/` owns JSON routes, `app/web/` renders pages, and `app/services/` contains compilation, execution and integration services.

The data plane is upstream tac_plus-ng, installed as a separate systemd service. The application compiles database state into a candidate configuration. Scope validation rejects invalid restrictions before application. A valid changed candidate goes through configuration validation, backup, replacement and service control. Database policy state and the active daemon file are distinct until Apply completes.

`app/services/policy_scope.py` resolves scope. `app/services/config_compiler.py` renders TACACS+ and RADIUS configuration. Explicit external-group bindings connect identity groups to configured directory/MAVIS sources. Local identity rows and runtime directory membership are distinct; directory users need not be stored as local users.

`app/api/routes_policies.py` performs complete create/update transactions, including restrictions, associations, priority changes and history. The editor submits a single complete mutation request. `app/services/policy_versioning.py` and the version API manage history; unsupported or unresolved restoration state is rejected rather than silently broadened.

Background services execute network jobs, backups, audits and monitoring. Device access uses SSH credentials and host-key handling. Sensitive database values are encrypted with the installation's encryption key; this does not replace filesystem access controls or protected backups.

## Security boundaries

Signed administrator sessions and per-route authorization protect management operations. State-changing browser requests use CSRF checks. Superadmins bypass granular role checks; administrators without roles retain legacy broad access. Role-assigned administrators are checked against their permissions, while some routes require superadmin access explicitly.

Diagnostic logs and configuration views are privileged operator data, not public telemetry. Treat exported configs, audit evidence and service logs as potentially sensitive. Normal status responses provide selected build metadata; raw installer metadata remains on the server for compilation and troubleshooting.

## Installed layout

- `/opt/aaa-platform/app`: application source.
- `/opt/aaa-platform/generated`: generated AAA configuration.
- `/opt/aaa-platform/backups`: configuration backups.
- `/etc/aaa-platform`: database credentials, encryption/session keys and settings.
- `/var/log/aaa-platform`: service and AAA logs.
- `aaa-platform.service` and `tac-plus-ng.service`: management and data-plane services.

These are supported installation paths, not developer-machine paths. See the installer source for ownership and generated systemd units. See [configuration](CONFIGURATION.md), [installation](INSTALL.md) and [testing](TESTING.md) for operational details.
