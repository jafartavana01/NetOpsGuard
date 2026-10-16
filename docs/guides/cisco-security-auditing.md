---
layout: default
title: "Cisco IOS and IOS-XE Security Auditing"
description: "Use NetOpsGuard Security Center to review Cisco router and switch configuration findings, audit results, scores, and compliance-oriented reports."
permalink: /guides/cisco-security-auditing/
---

# Cisco IOS and IOS-XE security auditing

Network device security reviews are easier when configuration observations and remediation priorities are collected in one place. The **NetOpsGuard Security Center** provides security checks, findings, scores, report views, and compliance-oriented mapping for supported **Cisco IOS and IOS-XE** configurations.

## What an audit helps you answer

- Which examined configuration areas have findings that deserve review?
- Which devices or findings need follow-up?
- How do report results change after a configuration change and a new audit?
- Which checks relate to operational hardening and compliance-oriented control categories?

## Run and interpret an audit

1. Add the intended Cisco router or switch in **Devices** and confirm secure, authorized management access.
2. Open **Security Center → Devices**, select your target, and initiate the supported audit.
3. Review findings, scores, and relevant evidence in **Overview**, **Findings**, and **Audit Reports**.
4. Confirm the underlying device configuration and OS applicability before planning remediation.
5. Re-audit after changes to collect a new result and compare findings.

Scheduled audit options are available to authorized administrators, but test scheduling behavior and job outcomes before using scheduled results as your sole control evidence.

## Scope and limitations

An automated configuration audit is not a penetration test and does not establish complete compliance with a certification framework. Findings depend on the collected configuration, parser coverage, supported IOS/IOS-XE features, and the time of the audit. Validate high-impact remediation against device documentation and change-control procedures.

Continue to [TACACS+ command authorization]({{ '/guides/tacacs-command-authorization/' | relative_url }}) to restrict who may change network device configuration in the first place.

## Compare saved assessments

Open **Compare audit evidence** on a device's audit history or on **Audit Reports**. Select the previous and newer runs for the same inventory identity. Device names alone do not establish identity. Retained runs remain available through Audit Reports after device deletion.

- **New regression** requires a comparable previous pass followed by a confirmed failure.
- **First observed** identifies a confirmed failure without a previous evaluated pass or failure.
- **Confirmed resolved** requires an explicit newer pass for the same control, domain, interface/resource, and correlation identity in complete, comparable assessments.
- **Persistent** means both comparable observations failed.
- **Indeterminate** means evidence is missing, incomplete, ambiguous, not applicable, or incompatible. A disappeared check or interface is never proof of remediation.
- **Manual review** remains awaiting review; it does not close an earlier failure.

Expand a result to inspect previous and newer evidence separately. Score changes are unavailable when scores, control coverage, or assessment provenance cannot be compared. A zero score remains a real score; missing scores are not treated as zero.

New completed runs record their inventory identity, configuration hash, assessment definition and policy fingerprints, interface coverage, and result manifest in the same result transaction. Capture checks reject missing configuration headers/end markers, known capture errors, and failed interface assessments for comparison purposes. These checks establish necessary capture completeness, not independent device attestation: uploaded configurations are evaluated as supplied and must be attached to the correct inventory device. Snapshots, if supplied by an integration, must satisfy the same requirements. No snapshot collection workflow is added by this update.

Existing audit evidence is not rewritten or backfilled. Older runs without recorded provenance cannot establish confirmed resolution or meaningful score changes. Deleted historical devices lacking a retained stable identity, and unattached uploads, cannot be compared by guessing from hostnames. Run two new complete audits to establish a comparable baseline. Changes to engine definitions, assessment policy, or interface scope conservatively require a new baseline.

Upgrade installation creates an additive assessment table; it does not alter existing audit evidence or add a device-deletion dependency. Back up the database before upgrading. Older application versions ignore this table but do not provide these comparison guarantees; avoid using their comparison results as remediation evidence after rollback.

API clients retain `new_findings`, `resolved_findings`, and `persistent_findings`. New categories and paired observations are additive. `score_delta` can now be null, with `score_reason` explaining why. Clients must handle null rather than displaying zero. Invalid identities, reversed chronology, and identical-run comparisons return an explicit conflict; missing or malformed audit identifiers return not found.
