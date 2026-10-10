# Upgrade and recovery

Use a maintenance window and a recoverable backup. This guide does not promise compatibility with every historical schema or a one-command rollback.

1. Record the installed application snapshot and tac_plus-ng build commit.
2. Back up PostgreSQL using the installation's database administrator procedure. Protect the backup as sensitive.
3. Back up `/etc/aaa-platform`, generated configuration, configuration backups and device configuration archives. Keep encryption keys paired with database backups; do not publish either.
4. Rehearse the upgrade on an isolated copy of the installation. Check schema initialization/migration messages and source-binding classifications.
5. Run the new snapshot's supported installer from the complete source directory. Review the existing-installation prompts and any upstream build choice. Do not uninstall to perform an upgrade.
6. Deploy editor and API together. Refresh browser assets and update API clients to the complete policy mutation contract.
7. Check management login, services, inventory, policies and candidate diagnostics. Verify AAA permit/deny behavior with a lab device before applying changes broadly.

Startup creates missing tables, applies the tracked external-group authority migration and runs the legacy additive-column helper. This is not a comprehensive migration framework for every historical schema. A migration failure must be investigated; do not manually erase restrictions or mark migrations successful.

For rollback, restore a matching application version, database backup and encryption/configuration material using your tested recovery procedure. Older code may not understand newer schema or policy intent. Restoring only an old application ZIP is not a complete database rollback.
