---
layout: default
title: "NetOpsGuard Frequently Asked Questions"
description: "Answers about NetOpsGuard licensing, TACACS+, RADIUS, Active Directory, supported Ubuntu versions, Cisco devices, NCM backup scheduling, and secure deployment."
permalink: /faq/
---

# Frequently asked questions

## Is NetOpsGuard free and open source?

The source is provided under the **Apache License 2.0**. The **Community** edition supports up to **five devices**, with the currently available platform features; higher device limits use signed licences. See [licensing](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/LICENSING.md).

## How can I request a licence for more than five devices?

You can request a signed licence by emailing [tavanajafar2@gmail.com](mailto:tavanajafar2@gmail.com) or contacting the maintainer via [Telegram @Powerinfossl](https://t.me/Powerinfossl). The [licensing information page]({{ '/licensing/' | relative_url }}) lists the WhatsApp ID, phone contact and request process.

## Can NetOpsGuard authorize individual Cisco commands?

Yes, through its **TACACS+ command sets and policies** on compatible network devices. Define the identity and device scope, apply the resulting AAA configuration, and verify actual allow/deny results on your NAS. [Read the command authorization guide]({{ '/guides/tacacs-command-authorization/' | relative_url }}).

## Does it connect to Microsoft Active Directory?

NetOpsGuard supports **Active Directory/LDAP integration** and external group mappings. Configure the actual directory source and certificate trust, then test real group membership and daemon behavior before production access-policy changes. [Read the AD/LDAP guide]({{ '/guides/active-directory-ldap/' | relative_url }}).

## Is RADIUS the same as TACACS+?

No. RADIUS supports AAA use cases, but it does **not** provide TACACS+-style per-command CLI authorization. Feature availability also depends on the daemon build and network device. [Compare TACACS+ and RADIUS]({{ '/guides/tacacs-vs-radius/' | relative_url }}).

## Which server operating systems can host NetOpsGuard?

The installer targets **Ubuntu Server 22.04, 24.04, and 26.04 LTS**. Other platforms are not automatically supported. See [installation requirements]({{ '/guides/getting-started/' | relative_url }}).

## Can it back up network device configurations?

Yes, it includes SSH-based configuration backup, versioned archives, comparisons, baselines and drift views. A backup is useful only once you have verified that the correct device configuration was successfully collected. [Read the NCM guide]({{ '/guides/network-configuration-backup/' | relative_url }}).

## Are scheduled configuration backups fully verified?

Not universally. A schedule can be configured, but administrators must confirm that their scheduled jobs execute and produce the expected archive snapshots in their actual deployment. Do not treat browser UI tests as proof of end-to-end scheduling.

## Does NetOpsGuard replace existing network-device AAA configuration?

No. Network devices must still be configured to contact the correct AAA server and use the desired method lists/services. NetOpsGuard manages the centralized server side, not every vendor's on-device AAA behavior.

## Can I safely upgrade an existing populated installation?

Back up the database and matching encryption/configuration material first, and test the target version on an isolated copy. There is no guarantee of complete automatic migration for every historical schema. See [upgrade and recovery](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/UPGRADE.md).

## Where should I report issues or security vulnerabilities?

Use the [issue tracker](https://github.com/jafartavana01/NetOpsGuard/issues) for ordinary problems, with sanitized logs and reproduction steps. Follow the [private security reporting policy](https://github.com/jafartavana01/NetOpsGuard/blob/main/SECURITY.md) for suspected vulnerabilities.

## Was NetOpsGuard previously called NetworkAAA?

Yes. **NetworkAAA** was the former project name. **NetOpsGuard** is the current repository and product name. Earlier community articles may still refer to NetworkAAA or link to an older repository; use the [current NetOpsGuard project](https://github.com/jafartavana01/NetOpsGuard) for up-to-date documentation.
