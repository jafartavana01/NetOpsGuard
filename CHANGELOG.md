# Changelog

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
