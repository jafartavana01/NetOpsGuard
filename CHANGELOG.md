# Changelog

## Unreleased — GUI-07 shell polish (in progress)

- Keyboard-accessible shared Apply Configuration dialog with focus trapping/restoration, Escape handling, background inerting, and failed candidate handling.
- Interrupted Apply connections now ask the operator to verify deployed configuration rather than incorrectly assume the Apply did not happen.
- Command palette restores focus and scrolling on dismissal, including SPA navigation.
- Narrow-screen global configuration action no longer overflows the topbar.
- Presentation and existing API integration only; no change to authorization, compiler, NCM or audit logic.

NCM backup scheduling, audit comparison semantics, LDAP certificate trust verification and role-deletion privilege fallback remain separate functional/security work. GUI-07 is not complete.


## Unreleased — System & Administration workspace

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
