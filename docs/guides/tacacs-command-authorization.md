---
layout: default
title: "TACACS+ Command Authorization and Network Device AAA"
description: "Learn the NetOpsGuard TACACS+ workflow for centralized network administrator authentication, command authorization, policies, accounting, and permit/deny verification."
permalink: /guides/tacacs-command-authorization/
---

# TACACS+ command authorization for network devices

**TACACS+ (Terminal Access Controller Access-Control System Plus)** is commonly used to centralize administrative access to network infrastructure. A TACACS+ policy can distinguish between signing in to a network device and being authorized to execute a particular command.

NetOpsGuard places TACACS+ identity, device inventory, command sets, policy scope, and accounting information into a single management workflow. Its runtime AAA service uses **tac_plus-ng**.

## Authentication, authorization, and accounting

| Function | Question answered |
| --- | --- |
| Authentication | Who is attempting to log in? |
| Authorization | What operations is this authenticated administrator permitted to perform? |
| Accounting | Which activity did the NAS report to the AAA service? |

A network device must be configured to consult the TACACS+ server for the actions you intend to centralize. Capabilities and event reporting vary with Cisco IOS/IOS-XE versions and other NAS implementations.

## How to build a command policy

1. Add your network device, establish its management identity and shared secret, and test network reachability to the AAA server.
2. Define a local identity or connect an approved external group using Active Directory/LDAP.
3. Create **Command Sets** matching the operations that should be allowed or denied.
4. Create a **Policy** with an explicit identity/device scope and the intended command set and action.
5. Use **Policy Simulator** and **Effective Access** as aids to review intent, not as final enforcement evidence.
6. Open **Configuration**, inspect diagnostics and the candidate diff, then **Apply** the validated AAA configuration.
7. Test the policy on a lab NAS with both expected permitted and denied commands. Review **Accounting**, **Sessions**, and **Access Events**.

Avoid a broad or unrestricted policy when a device or group reference is missing. NetOpsGuard can block candidates with unresolved restrictive scopes rather than silently broadening access.

## Example policy design

Suppose network operations staff may run read-only troubleshooting commands on a group of routers but should not change routing configuration. Define the target router group, map the operators' identity group, and attach an appropriate read-only command set. Test the action using the actual NAS, including commands with parameters and alternate forms.

For sensitive changes, prefer narrow scopes and verify both successful and denied cases. Device CLI syntax, privilege levels, and AAA method lists still affect the outcome.

## Understanding accounting evidence

Accounting records depend on the device's configuration and supported events. In particular, some Cisco configurations do **not** report denied commands as ordinary command accounting records. Correlate access/authorization events and the NAS logs rather than assuming every denied attempt will appear in one accounting table.

Related articles: [AD/LDAP integration]({{ '/guides/active-directory-ldap/' | relative_url }}), [TACACS+ versus RADIUS]({{ '/guides/tacacs-vs-radius/' | relative_url }}), and the [configuration reference](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/CONFIGURATION.md).
