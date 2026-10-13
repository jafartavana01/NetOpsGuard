---
layout: default
title: "Install NetOpsGuard on Ubuntu Server"
description: "Install the open-source NetOpsGuard TACACS+ AAA platform on Ubuntu, access its secure web management interface, and configure your first network device."
permalink: /guides/getting-started/
---

# Install NetOpsGuard on Ubuntu Server

NetOpsGuard combines network AAA, configuration history, Cisco security auditing, and network operations in a self-hosted management interface. Use a dedicated Ubuntu Server VM for your first deployment and validate AAA behavior with a lab device before production rollout.

## Prerequisites

- Ubuntu Server **22.04, 24.04, or 26.04 LTS** with sudo access
- At least **1 GB RAM and 5 GB free disk space** as installation recommendations; allow more headroom for active deployments and growing archives
- Network access during installation to retrieve packages and the tac_plus-ng source
- Connectivity between network devices and the AAA server

## Install

Run these commands on your Ubuntu host:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/jafartavana01/NetOpsGuard.git
cd NetOpsGuard
sudo bash bootstrap.sh
```

The installer checks the environment, provisions PostgreSQL, builds/installs the AAA daemon, installs the management application, configures system services, and prompts for an initial administrator account.

## Open the management UI

Browse to `https://<server-ip>:8420`. A fresh install uses a self-signed HTTPS certificate, so your browser may report that it is not signed by a trusted CA. Replace it with an appropriate trusted certificate and restrict management access to your administrator networks.

Verify the installed services if the page is unavailable:

```bash
sudo systemctl status aaa-platform.service --no-pager
sudo systemctl status tac-plus-ng.service --no-pager
```

Network paths include TCP **49** for TACACS+, TCP **8420** for the default web interface, and optional RADIUS UDP **1812/1813**. SSH device operations commonly require outbound TCP **22**, and LDAPS commonly uses TCP **636**. Only permit the paths actually required.

## Configure your first device

1. Add a lab device under **TACACS+ → Devices** with its correct IP address and shared secret.
2. Create or connect a user/group identity.
3. Create a command set and a policy scoped to the intended device and identity.
4. Review the candidate and diagnostics under **TACACS+ → Configuration** before applying.
5. Test one allowed and one denied operation on your lab device. Review accounting and access events for evidence.

**Important:** Saving a policy does not change the running daemon; the separate **Apply** step deploys it. For detailed installer options, see the [installation reference on GitHub](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/INSTALL.md).

Continue with [TACACS+ command authorization]({{ '/guides/tacacs-command-authorization/' | relative_url }}) or [Active Directory integration]({{ '/guides/active-directory-ldap/' | relative_url }}).
