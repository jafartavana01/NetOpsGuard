---
layout: default
title: "NetOpsGuard: self-hosted TACACS+ AAA and network security operations"
description: "NetOpsGuard combines TACACS+ command authorization, AD/LDAP identity, RADIUS, network configuration backups, Cisco security audits, and SSH operations. Free for five devices."
permalink: /
---

# Network AAA and security operations, in one platform

NetOpsGuard (previously **NetworkAAA**) is an **open-source, self-hosted network management platform** for teams operating Cisco and other supported network infrastructure. Centrally manage **TACACS+ authentication, command authorization and accounting**, connect directory identities, inspect configuration changes, and review security findings through a web interface.

![NetOpsGuard web dashboard showing network operations and TACACS+ management](https://github.com/user-attachments/assets/60af06ac-6017-447e-bd37-69bb27d9c427)

**Get started at no cost:** The Community edition supports **up to five managed devices** with the currently available feature set. Larger device limits use signed licences.

[Install NetOpsGuard]({{ '/guides/getting-started/' | relative_url }}) · [Explore the source on GitHub](https://github.com/jafartavana01/NetOpsGuard)

## What NetOpsGuard helps you manage

| Area | What it does |
| --- | --- |
| **TACACS+ AAA** | Control administrative login and command authorization for managed devices; view accounting and access activity. |
| **Active Directory / LDAP** | Connect existing directory identities and authorized group mappings to network access policies. |
| **RADIUS** | Define network access policies and attributes supported by the installed daemon and NAS. |
| **Network configuration management (NCM)** | Archive device configurations over SSH, compare versions and baselines, inspect drift, and review change workflows. |
| **Cisco security auditing** | Review security findings, compliance-oriented views, and reports for supported Cisco IOS/IOS-XE devices. |
| **Network Operations** | Execute authorized SSH command jobs and reusable command templates across network devices. |

## Start with the workflow you need

- **[Install on Ubuntu]({{ '/guides/getting-started/' | relative_url }})** — deploy the self-hosted platform, check services, and log in securely.
- **[TACACS+ command authorization]({{ '/guides/tacacs-command-authorization/' | relative_url }})** — scope commands by identities and devices, and verify permit and deny outcomes.
- **[Active Directory and LDAPS]({{ '/guides/active-directory-ldap/' | relative_url }})** — connect directory groups to AAA policy safely.
- **[Network configuration backup]({{ '/guides/network-configuration-backup/' | relative_url }})** — collect and compare configuration archives.
- **[Cisco network security audits]({{ '/guides/cisco-security-auditing/' | relative_url }})** — organize device findings and review configuration exposure.
- **[TACACS+ versus RADIUS]({{ '/guides/tacacs-vs-radius/' | relative_url }})** — understand when each protocol fits device administration.
- **[Frequently asked questions]({{ '/faq/' | relative_url }})** — platform requirements, licensing, and operational limitations.

## Built for network administrators and infrastructure security teams

NetOpsGuard is designed for lab environments, operational teams, and organizations that want centrally managed network device access without building separate workflows for AAA policy, configuration history, and device checks.

The management plane runs on Ubuntu Server and uses PostgreSQL for application state. TACACS+ services are delivered by the installed **tac_plus-ng** daemon. Features involving directory membership, RADIUS capabilities, or device CLI output must be validated against the specific build and equipment in use.

> **Deployment note:** The policy simulator does not replace actual NAS authorization testing. A backup schedule displayed in the UI does not itself prove unattended backup execution. Test critical AAA and NCM workflows before depending on them in production.

## Try NetOpsGuard

Read the [quick installation guide]({{ '/guides/getting-started/' | relative_url }}) or go directly to [NetOpsGuard on GitHub](https://github.com/jafartavana01/NetOpsGuard) for the complete source, Apache-2.0 licence, and issue tracker.

## Licence requests and contact

The Community edition supports five devices for free. To request a licence for more devices or ask about licence migration, read the [NetOpsGuard licensing information]({{ '/licensing/' | relative_url }}) or contact the maintainer:

- **Email:** [tavanajafar2@gmail.com](mailto:tavanajafar2@gmail.com)
- **Telegram:** [@Powerinfossl](https://t.me/Powerinfossl)
- **WhatsApp ID:** `@jafartavana0`
- **Phone:** [+98 917 011 8221](tel:+989170118221) (`00989170118221`)
