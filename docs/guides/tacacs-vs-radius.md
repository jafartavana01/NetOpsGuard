---
layout: default
title: "TACACS+ vs RADIUS for Network Device Administration"
description: "Compare TACACS+ and RADIUS for administrator authentication, command authorization, and accounting, and learn which NetOpsGuard capabilities apply."
permalink: /guides/tacacs-vs-radius/
---

# TACACS+ versus RADIUS for network access

**TACACS+** and **RADIUS** are both AAA protocols, but they serve different device and access-control workflows. For router and switch administrator logins, TACACS+ is often chosen when **command-level authorization** is required. RADIUS is commonly used for network access and device authentication, depending on the NAS and service.

## Capability comparison

| Question | TACACS+ | RADIUS |
| --- | --- | --- |
| Authenticate a user? | Yes | Yes |
| Provide authorization? | Yes, including supported command authorization | Yes, typically through attributes/services and NAS behavior |
| Account for activity? | Supported device/session/command events | Supported accounting events as emitted by NAS |
| Per-command network CLI authorization? | Supported by capable NAS/TACACS+ configurations | **Not equivalent to TACACS+ command authorization** |
| Common server transport | TCP 49 | UDP 1812/1813 |

Actual decisions depend on how each network device is configured to use its AAA server. The protocol does not automatically enforce your policies without matching NAS-side configuration.

## Choosing a protocol in NetOpsGuard

Use the **TACACS+** workspace for administrative command sets, per-device command policies, command accounting, and verification. Use **RADIUS** when the target device requires RADIUS and the selected tac_plus-ng daemon build provides the desired feature.

NetOpsGuard exposes RADIUS clients, policies, server settings, and attributes where supported. This release does **not** present RADIUS Change of Authorization (CoA) as a supported capability.

Start with [TACACS+ command authorization]({{ '/guides/tacacs-command-authorization/' | relative_url }}) or the [installation guide]({{ '/guides/getting-started/' | relative_url }}).
