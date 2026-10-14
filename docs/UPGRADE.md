# Upgrade and recovery

NetOpsGuard can detect an existing installation and report certain schema differences, but **a safe upgrade is not guaranteed for every older database or application version**. Use a maintenance window, follow a tested backup/restore procedure, and verify the intended target release before proceeding.

## Before changing an existing installation

1. Record the currently deployed application version/commit and the AAA daemon build.
2. Back up the PostgreSQL database and verify that the dump is readable.
3. Securely back up `/etc/aaa-platform/` (including encryption and session material), generated AAA configuration, device configuration archives, and any operational files necessary for recovery.
4. Keep each database backup with the matching encryption material. Store backups off the NetOpsGuard server with appropriate access controls.
5. Rehearse the upgrade and rollback on an isolated restored copy, including critical permit/deny and NCM checks.
6. Confirm that the target release supports the database schema and your directory/NAS integration.

## Applying a newer release

The installer detects an existing installation and normally preserves the existing device, policy, and generated AAA state. **That does not make it a full database migration tool.** It can report missing columns and does not automatically resolve all schema drift. Some application startup paths perform scoped migrations, but these are not a comprehensive guarantee for arbitrary historical releases.

After the backup and rehearsal, follow the specific instructions supplied with the target release. Avoid `--force-config` on a populated installation unless you deliberately intend to replace the existing deployed AAA configuration with bootstrap configuration.

When the application and API change, deploy them together and refresh the browser. Recheck service health, administrator access, licence status, directory bindings, inventory, candidate diagnostics, and critical authorization policies. Confirm real-world permit and deny outcomes on a lab device before any broad deployment.

## If the upgrade does not work

Stop and diagnose rather than manually relaxing scope restrictions or ignoring schema errors. An application-only rollback may not work with a newer database schema. Restore a **matching** application version, database, configuration, and encryption material using the recovery procedure previously tested in your environment. A generated tac_plus-ng file or source ZIP by itself is not a complete platform backup.

For first checks and service logs, see [Troubleshooting](TROUBLESHOOTING.md). For installation details, see [Installation](INSTALL.md).

### NCM schedule execution state

The scheduled-backup update adds a separate execution-state table at application startup; it preserves existing schedules, encrypted Device Credentials, and backup history. Stop old application workers before starting the upgraded version so old and new schedulers cannot run together. The database account needs permission to create the new table. A failed initialization prevents startup rather than running without execution tracking.

Check each schedule's UTC time and status after upgrading. Historical attempts without detailed outcome records are not labelled successful. Review interrupted jobs before an explicit retry. Back up the database before upgrading; rolling back the application also restores the older scheduler's limitations and must not be mixed with new workers. The additive state table can remain in place when rolling back.
