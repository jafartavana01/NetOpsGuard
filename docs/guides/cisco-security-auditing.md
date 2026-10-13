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
