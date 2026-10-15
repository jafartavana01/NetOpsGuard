# Changelog

## Local-time scheduling and application version metadata

- System Settings offers an explicit IANA timezone preference. New backup schedules use it; existing backup and audit schedules remain Legacy UTC until deliberately converted. Schedule views include local and UTC execution times.
- Daily schedules use calendar-aware timezone conversion with documented DST rules. Security Center audits record durable claims and exclude overlapping scheduler/manual execution.
- Application version metadata is independent of tac_plus-ng and appears in the sidebar, Settings, and diagnostics. Release publication increments the four-part version and creates its matching tag atomically.


## Unreleased — Simpler deletion confirmation

- Deletion uses an explicit confirmation button without requiring typed text. Blocking references are grouped, and retained history no longer fills the dialog with repeated cards.
- Completed and failed Security Center audits no longer prevent inventory-device deletion. Audit evidence and device-name history are retained; active audits, policy references, and other configuration dependencies remain protected.


## Unreleased — Scheduled backup reliability

- NCM schedules record durable attempts and outcomes, catch up the latest missed UTC occurrence, and prevent concurrent execution across workers. A failed schedule no longer interrupts evaluation of unrelated schedules.
- Backup Schedules shows execution status, last attempt/success, device counts, and links to jobs and archives. Run Now uses saved targets and types with the existing schedule permission and CSRF protection.
- Missing credentials and empty targets are visible blocked results. Incomplete SSH configuration output is rejected instead of being archived as a successful backup.
- Schedule retention protects latest snapshots, baselines, and deployment recovery points. Existing credentials and scheduling settings are preserved.


## Unreleased — Centralized device credentials

- System → Device Credentials manages the shared SSH service account independently of audit schedules. Existing encrypted passwords and execution history are preserved without re-entry.
- Blank password replacement retains the saved secret; stale concurrent changes are rejected. Credential settings remain superadmin-only and protected against CSRF.
- Individual live security audits use the saved account by default; callers can still supply an explicit username/password pair with the existing audit permission.
- Audit scheduling no longer edits credentials. NCM and audit screens point to the central settings; NCM viewers receive configuration status only.
- Credential validation errors and SSH job failure messages avoid echoing supplied passwords. Saving settings is not an SSH connectivity test.

## Compact interface and dashboard corrections

- Compact table rows, controls, cards, and toolbars retain the existing visual identity and readable text. Device and Policy actions stay on one line inside scrollable tables.
- AAA hourly activity normalizes timezone offsets before grouping. Authorization totals and hourly activity now share the selected rolling time window; empty activity explains out-of-window and unknown timestamps.
- Directory health checks automatically on dashboard entry and every 60 seconds, retains manual checking, and shows the last attempt. Requests do not overlap in the dashboard and polling stops when leaving it.

## Interface consistency and usability

- Rapid navigation keeps the latest selected page, follows server redirects, and focuses the new heading for keyboard users.
- Dialog cancellation consistently protects unsaved edits; Escape on the discard prompt keeps the form open. Existing feature-specific save and permission checks remain authoritative.
- Interrupted configuration Apply requests explicitly report an unknown outcome and require a fresh review before retrying.
- Notifications stack without overlapping, expose accessible status messages, and allow dismissal. Failed sign-out requests remain visible instead of appearing to succeed.
- Improved small-screen forms, NCM overview panels, scrollable technical tables, filter-empty pagination, and keyboard sorting indicators.
- RADIUS policy editing waits for required scope options. Saved scope and attribute values absent from current lists are retained; failed saves remain in the editor with an error.

This update does not change AAA authorization, policy compilation, database models, licensing enforcement, or API contracts. The known backup-scheduling, audit-comparison, LDAP certificate-verification, and role-deletion fallback issues remain unresolved.

## System & Administration workspace

- Consistent administration navigation, searchable account/role tables, accessible dialogs, and unsaved-change protection.
- Clear separation between saved settings, management-service restart, AAA Configuration Apply, and observed runtime status.
- Improved directory connection testing, RADIUS listener/probe feedback, licensing, database/service diagnostics, and configuration-event inspection.
- Certificate/private-key and license imports use file selection without displaying the supplied file contents.
- Failed restart requests no longer report success; blocked configuration validation no longer reports that nothing is pending.
- Account editing is blocked when required role information cannot be loaded. Disabling accounts and changing assigned privileges require confirmation.

This update changes presentation and existing API integration, not authorization, identity authority, licensing enforcement, or database behavior. PostgreSQL and native AAA/device verification remain separate deployment gates.

## Current public release

This is a user-facing summary of the packaged source. It does not assign a new semantic version or claim a native installation certification.

### Changed

- Unified navigation, shared visual components and an operations dashboard across AAA, device security and NCM.
- Policy creation and update now persist metadata, condition-tree scope, relevant associations and history in one server-side transaction.
- The policy editor submits a complete request; incomplete legacy API requests are rejected.
- Configuration preview distinguishes blocked candidates, valid unchanged candidates and valid changes ready to apply.
- Policy restoration rejects missing references and snapshots that cannot preserve the intended restrictions.
- Explicit external-group binding validates the configured identity source and retains the group restriction in generated policy configuration.
- Public status responses omit raw database error text and installer-specific build paths/arguments.
- Public documentation and packaging exclude internal investigation reports and generated development evidence.

### Included capabilities

TACACS+ AAA, AD/LDAP integration, device inventory, condition-tree policies, command sets, accounting, sessions, RADIUS configuration, NCM, command jobs, Security Center, licensing and administrator controls are included according to installed daemon capabilities and the documented limitations.

### Compatibility

Deploy the policy editor and API together. Integrations creating or updating policies must provide explicit scope intent and the complete security-relevant state. Back up the database and encryption material before upgrade. See [upgrade guidance](docs/UPGRADE.md) and [configuration limitations](docs/CONFIGURATION.md).
