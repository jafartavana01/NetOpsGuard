# Configuration guide

## Management access

Use the administrator account chosen at installation. Configure HTTPS in Platform Settings and restrict management connectivity. An account without a granular role retains broad legacy administrator permissions; assign a role to restrict it. Keep at least one recoverable superadmin account.

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
