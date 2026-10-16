---
layout: default
title: "Network Configuration Backup, Diff and Baseline Management"
description: "Explore NetOpsGuard NCM for SSH device configuration backups, archived versions, baseline comparison, drift views, and change control."
permalink: /guides/network-configuration-backup/
---

# Network configuration backup and change tracking

**Network Configuration Management (NCM)** helps administrators understand which configuration was collected from a device, how one version differs from another, and what needs review before making a change. NetOpsGuard includes configuration archives, diff and comparison views, baselines, change workflows, and backup job tracking.

## A practical NCM workflow

1. Add an authorized network device to inventory and configure the necessary SSH access.
2. Verify connectivity and host-key trust, then run a **manual configuration backup**.
3. Open the **Configuration Archive** and confirm the stored snapshot contains the intended running configuration.
4. Compare two archived versions in **Configuration Diff**, or select snapshots across devices for **Configuration Compare**.
5. Set a known-good version as a **baseline**, and inspect the baseline-versus-archive changes with drift views.
6. Use **Change Control** to review proposed configuration operations where supported by the device workflow.

## What diffs and baselines can tell you

A text or normalized-configuration diff highlights recorded changes between collected snapshots. It cannot, by itself, prove that a device currently matches the latest archive. Likewise, a baseline comparison is not a live compliance attestation unless the device has been checked at the relevant time.

Keep relevant configuration backups and application/database backups separate and protected. A complete platform restore also requires matching configuration and encryption material.

## Automated backup schedules: important verification

NetOpsGuard exposes NCM backup schedules and a schedule service, but the availability of a schedule page is not proof that unattended jobs run correctly in every installation. **Before relying on automatic backups**, create a noncritical test schedule, wait for its execution, and confirm the job record **and** a valid archived configuration for the target device. Investigate missing or partial output.

For job troubleshooting and schedule checks, consult [Troubleshooting](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/TROUBLESHOOTING.md).

## Supported equipment

Collection behavior depends on the device OS, SSH authentication, CLI output, and supported platform driver. Test representative device families and firmware versions before rolling out a backup policy broadly.

## Removing an inventory device

Select **Delete** on the Devices page and review the confirmation. If policies depend directly on a selected device, or deleting the selection would empty a device group used by an enabled policy, the confirmation lists the affected policies. Confirming removes those complete policies and the devices together. Removing policies requires policy-edit permission. Review the warning about later policy matches before confirming; AAA configuration is not applied automatically.

NCM configuration archives, baselines, saved changes, completed jobs, and security audit history are retained. Archived versions remain readable and comparable using the original device identity. Saved changes cannot be deployed to a removed device. Adding another device with the same name does not transfer the old device's history.

Backup schedules remain saved. Removed devices are not contacted, and a run with no remaining targets reports a blocked result. Edit the schedule when replacement targets are needed. Active jobs and other live configuration dependencies can still require attention before deletion.

Back up the database before upgrading and restart the upgraded application before deleting inventory. Startup removes the cascading inventory links from NCM history tables while preserving their data. If that upgrade cannot complete, device deletion remains blocked. Rolling back application code does not restore those database constraints; restoring an older database can restore the old deletion behavior.
