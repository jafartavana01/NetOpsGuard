# Configuration guide

## Management access

Use the administrator account chosen at installation. Configure HTTPS in Platform Settings and restrict management connectivity. An account without a granular role retains broad legacy administrator permissions; assign a role to restrict it. Keep at least one recoverable superadmin account.

## Dashboard observations

AAA activity and authorization totals describe timestamped command authorization records in the last 24 hours of the bounded log sample (up to 2,000 log lines). UTC hourly buckets include partial first and last hours; labels use your browser timezone. Records outside that window or with unknown timestamps are excluded, not assigned invented times. Non-permit includes any non-empty result other than permit and is not necessarily an explicit deny. Login/authentication events remain separate.

For superadmins with Directory access, the dashboard checks saved directory settings on entry and every 60 seconds while the view remains open. **Check directory** remains available between requests. The check is a read-only LDAP bind and base-object lookup; it does not verify MAVIS authorization or certificate trust. The last attempt is displayed, errors remain Unknown/failed, and navigation stops polling. Each open dashboard has its own polling cycle.

## Navigation and editing

On narrow screens, open the navigation menu from the top bar; Escape closes it and returns focus to the menu button. Wide result tables scroll independently so addresses, commands, and scope values remain readable. Table filters marked “loaded rows” search the current loaded results, not additional server records.

When a dialog has unsaved edits, cancellation offers a choice to keep editing or discard. Escape on the discard prompt keeps the editor open. Error notifications stay visible until dismissed. A failed sign-out request does not confirm that the session has ended; retry after connectivity is restored.

RADIUS policy editing requires the group, device, device-group, and attribute lists to load. If these requests fail or access is denied, refresh after resolving the error. A saved value missing from a current list is shown explicitly and retained; it is not changed to “Any.” Review stale references before saving, then review Configuration and Apply separately. A successful save is not confirmation of deployment. If the connection is lost during Apply, the result is unknown: refresh Configuration and inspect service status before retrying.

## System & Administration workspace

Use the contextual navigation to switch between Network & TLS, Administrators, Roles & permissions, AD / LDAP, Modules, License, RADIUS settings, Diagnostics, and AAA health. Existing account permissions and module availability still apply.

- **Network & TLS:** Save web settings, then explicitly restart management to activate them. Changing the address, port, or HTTPS mode can interrupt access. TACACS+ port changes require AAA Configuration Apply separately. Certificate replacement writes the selected certificate/key to disk; management restart activates it. Private-key contents are not displayed.
- **Administrators and roles:** Search loaded rows, review the role, and confirm access changes. A blank password when editing preserves the existing password. Deleting a role currently leaves its assigned accounts with full standard-admin access; reassign those accounts first if this privilege expansion is not intended.
- **AD / LDAP:** Test Connection checks the current form values. Run health check tests saved settings. The displayed successful-check time applies only to the current page visit. Neither test proves native MAVIS authentication or authorization. Save settings, review the AAA candidate, Apply, and verify real permitted and denied logins.
- **Modules:** The switches show saved configuration. Changes affect mounted pages/APIs after an explicit management restart; saving does not restart services.
- **License:** Inspect actual usage and edition limits, select a license file for import, or generate a request. The request includes hashed machine identifiers and any contact/reference entered; review it before sharing.
- **RADIUS settings:** Saved listener settings and the illustrative preview are distinct from observed listeners. Save, then review and Apply AAA configuration. A probe response, including Access-Reject, proves reachability rather than successful user authorization.
- **Diagnostics:** Refresh service/database status or validate the candidate without applying it. Blocked, changed, unchanged, and inconclusive validation results are distinct. Configuration events are not a complete administrative audit trail. Known credential patterns are masked in displayed/copied output; this is not comprehensive backend log sanitization.

Discard restores saved form values. Loading failures prevent settings from overwriting the server with defaults. A lost connection during a mutation does not prove failure or success: refresh saved state before retrying.

**Directory TLS limitation:** The current platform LDAP test/browser client uses `CERT_NONE`; its successful LDAPS/StartTLS check does not validate server-certificate trust. This GUI update preserves backend behavior. Do not use that result as evidence of certificate verification; remediation and native MAVIS trust verification require separate review.

## Inventory and identity

Add devices with unique addresses and their own TACACS+/RADIUS secrets. Device groups may exist empty, but a policy referencing an empty group cannot be deployed. Store SSH credentials only through the supported settings/API and review first-use host-key trust.

Configure the actual directory controller, TLS trust and bind account before importing groups. Explicit EXTERNAL group authority requires a valid source binding and runtime membership mapping. A populated display name alone does not prove the binding. Local membership enumeration is not a directory membership test. Legacy ambiguous groups may require explicit review; LOCAL/HYBRID source-isolation modes are not implemented as selectable authority states. External RADIUS authority and external negative-membership cases remain unsupported where validation rejects them.

## Policy save and apply

Choose identity/device scope, command sets, action and priority. Saving persists the complete policy state; applying updates the daemon configuration separately. For API integrations, POST/PUT policy requests require `scope_mode` (`unrestricted`, `legacy` or `tree`) and all security-relevant fields. `legacy` requires every dimension explicitly, using null for intentional Any; `tree` requires the full condition tree and no conflicting legacy restriction. `unrestricted` explicitly declares a catch-all. A failed validation does not authorize a partial save.

The Configuration page distinguishes:

- Valid changed candidate: review the diff and apply.
- Valid unchanged candidate: no application is needed.
- Invalid candidate: read policy diagnostics and repair the scope; the deployed configuration is unchanged.

A missing or unsupported restriction must not be replaced with Any to dismiss a diagnostic. Intentional unrestricted policies remain supported. Test both expected permits and denials on a lab NAS after changes.

## History and backup

Policy snapshots that cannot reconstruct their scope are not restorable. Full condition-tree history restoration is not supported by every older snapshot. Preserve a database backup in addition to generated configuration backups. Restoring a raw privileged configuration is a different workflow from regenerating configuration from database policy state.

## Current limitations

- Legacy editor conversion of simultaneous device and device-group restrictions does not preserve every conjunction. Review the complete Boolean expression in the advanced editor before saving and verify the generated result.
- Historical null fields may not reveal whether a restriction was intentionally absent or was lost. Review older policies explicitly.
- Dependency-aware inventory deletion is not complete. Review dependent policies before deleting objects or changing membership, then inspect the candidate and diagnostics.
- Simulator/effective-access output is advisory; unsupported, negated or malformed conditions are not authoritative native-daemon evidence.
- RADIUS does not provide TACACS+-style per-command authorization. Protocol/service-type behavior depends on the installed supported daemon; verify on the target NAS.
- Authentication-time directory failure and native command authorization should be tested in the deployment's actual directory/NAS environment.

These limitations are not removed by successful GUI tests or by atomic policy persistence.

## Shared network device SSH credentials

A superadmin configures **System → Device Credentials**. This account is used for manual and scheduled NCM backups, NCM deployment/rollback and their backup checks, scheduled and bulk Security Center audits, and individual live audits by default. Network discovery and general command jobs retain their explicit per-request credentials. This account is separate from TACACS+ and RADIUS shared secrets and from the AD bind account.

Existing installations keep their encrypted account in place; no password re-entry or secret migration is required. Enter a username and a password for the first setup. On later saves, leave the replacement password blank to retain the saved password. The browser never receives the stored password or its encrypted value. If another administrator changes the account first, reload the saved state and review your intended change before retrying. Credential-specific modification time and editor are not available in the existing storage.

Saving validates the settings but does not test SSH connectivity or device privileges. Review the next backup/audit result against an authorized device. Existing SSH host-key behavior is unchanged. A running job may finish with the credentials it loaded before a rotation; subsequent runs load the saved account.

**Scheduled Audits** controls the schedule and displays execution history and credential status. It no longer accepts username/password updates. NCM overview and backup schedules show credential status; only superadmins can open the credential editor. Operators who cannot edit settings should ask a superadmin to configure the account.

For API clients, `GET /api/device-credentials` returns non-secret settings and a revision token. Superadmins use `PUT /api/device-credentials` with `username`, `password` (null/blank preserves it), and the latest `revision`, with the existing CSRF header. Stale revisions return 409. Remove credential fields from `PUT /api/security/schedule`; these fields now return 422 instead of changing the shared account. Individual `/api/security/devices/{id}/audit/live` requests may omit both credentials to use the shared account or supply both explicitly. Audit permission and CSRF requirements remain unchanged.

Restart all application workers when upgrading; do not run old scheduling writers alongside the new credential editor. Downgrading restores the old credential-editing interface and loses the new stale-update protection. Schedule reliability, audit-comparison correctness, directory certificate verification, and role-deletion fallback are separate unresolved issues.

### Scheduled NCM backups

NCM → Backup Schedules preserves existing times as **Legacy UTC**, independent of the browser or server timezone. New schedules can use an explicit IANA timezone. Review the saved timezone after upgrading; see Application timezone and daily schedules below.

Enabled schedules are checked approximately every 30 seconds while the application is running. After downtime, only the most recent due occurrence is considered; the scheduler does not replay every missed day. Newly created schedules start with the next occurrence. An attempted occurrence, including a blocked or interrupted attempt, is not automatically retried. Review the recorded outcome and use **Run Now** to retry explicitly. Moving the daily time later can create another due occurrence that day; editing a running schedule is refused until it finishes.

The schedule list shows the nominal next due time, last attempt, last successful execution, device counts, and a link to the backup job and archived configurations. Next due is not a guaranteed start time: another backup may hold the worker lock. Use **Refresh status** to read the latest persisted result. Missing Device Credentials, empty target selections, and invalid saved settings are reported as failures or blocked attempts, never successful backups. A lost browser connection does not cancel server-side work; refresh and inspect the job before retrying.

Backup jobs are serialized across application workers; devices within a job still use bounded concurrency. Manual backups and baseline changes return a busy response during a conflicting operation. PostgreSQL uses database advisory locks. SQLite supports workers on one host sharing the same database path and its adjacent `.ncm-locks` directory; do not place SQLite on a network filesystem or delete lock files while workers are running. The service account must be able to create this directory.

Retention removes only old snapshots created by the schedule. The latest snapshot for each device/configuration type, designated baselines, and deployment rollback/verification snapshots remain protected. Job history remains available, but a target may no longer link to an expired snapshot. Unchanged configuration still records a successful attempt and links to the existing archive rather than creating duplicate content.

Configuration retrieval must finish with the supported device prompt. A timeout or incomplete response is a failed retrieval; it cannot replace a valid archived configuration. Supported device verification remains necessary before relying on the backups for recovery.

### Deleting inventory items

Select Delete, review the selected names and any blocking references, then use **Confirm deletion**. No typed confirmation is required. Cancel is initially focused, and closing the dialog does not submit a deletion.

Completed/failed Security Center audit history is retained when its inventory device is removed. Active audits still block deletion until they finish. Policies, backup schedules, and other live configuration references must be resolved explicitly; removing a device never silently removes its policy restriction. Deleting dependent policies remains a separate, clearly listed destructive choice. Running AAA configuration changes only after a separate successful Apply.


## Application timezone and daily schedules

Under **System → Settings**, search for an IANA timezone such as `Asia/Tehran` or `Europe/London`, then save it. The browser timezone is a suggestion only. The initial application preference is UTC; the Ubuntu host timezone is never an implicit scheduling input. Changing this preference requires no service restart and does not change saved schedules.

New backup schedules use the application preference. Every schedule retains its own timezone. Old NCM and Security Center schedules display **Legacy UTC** and keep their original UTC execution time. To convert one, edit its timezone and daily wall-clock time explicitly, then save. Saving other fields does not convert it. API clients that omit `schedule_timezone` preserve the current setting on updates; omitted or null timezone on creation retains legacy UTC compatibility.

The scheduler calculates each local calendar occurrence with IANA timezone rules, then records its UTC instant. At a fall-back transition, a repeated time runs **once, at the first occurrence**. At a spring-forward transition, a nonexistent local time is **skipped for that date**. This also handles non-hour transitions and skipped calendar dates. NCM catches up only the latest valid missed occurrence; timezone-aware audits use the same rule. Legacy audits keep their existing same-UTC-day behavior. Execution timestamps and checkpoints remain UTC.

Schedule pages show the saved timezone and local next/previous instants, with UTC equivalents for troubleshooting. These are nominal due times, not guaranteed start times. Busy workers can defer execution. A blocked, failed or interrupted attempt consumes that occurrence: inspect the result before an explicit Run Now. Audit edits and Run Now cannot overlap its active daily scheduler. Moving a schedule's time can deliberately create another due occurrence; review the next due time after saving.

Timezone preferences are saved independently in `/etc/aaa-platform/config/timezone.json`; include this directory in configuration backups. Use the same IANA timezone data on all workers and restart application workers after timezone-data upgrades.
