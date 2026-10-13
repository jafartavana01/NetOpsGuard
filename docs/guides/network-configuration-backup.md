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
