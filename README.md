# NetOpsGuard

**Self-hosted network access control, configuration management, and security operations — in one web interface.**

NetOpsGuard helps network teams control who can access their infrastructure, which commands they can run, and what changes on their devices. It brings **TACACS+ AAA**, **Active Directory/LDAP integration**, **device inventory**, **Security Center**, **network configuration management (NCM)**, and **SSH command operations** into a unified platform.

**Free Community edition: up to 5 devices, with the currently available feature set.** Introductory paid licences start at **US$99/year for 15 devices**. Larger device limits are available through signed licences. [View all pricing](docs/pricing.md) and [licensing details](docs/LICENSING.md).

> **Previously known as NetworkAAA.** NetOpsGuard is the current project name and repository. Please link to this repository when referencing the platform.

![NetOpsGuard web interface](https://github.com/user-attachments/assets/60af06ac-6017-447e-bd37-69bb27d9c427)

[**Installation**](#quick-start) · [**Features**](#what-you-can-do) · [**First configuration**](#your-first-configuration) · [**Documentation**](#documentation) · [**Security**](SECURITY.md) · [**Issues**](https://github.com/jafartavana01/NetOpsGuard/issues)

## What you can do

| Area | Capabilities |
| --- | --- |
| **TACACS+ AAA** | Centralized administrator authentication, device and command authorization, command sets, policy scopes, accounting, sessions, and access events. |
| **Identity & access** | Local users/groups, Active Directory/LDAP integration, external group bindings, administrator roles, and policy simulation. |
| **Device inventory** | Manage devices and device groups, discover devices on a network range, and review device-related information. |
| **Configuration deployment** | Preview and validate an AAA candidate, examine the diff, and apply changes to the AAA service with backup and recovery safeguards. |
| **RADIUS** | Configure clients, policies, attributes, authentication, and accounting where supported by the installed daemon and NAS. |
| **Security Center** | Cisco IOS/IOS-XE security audits, findings, scores, compliance-oriented views, reports, and audit scheduling. |
| **Network Configuration Management** | SSH configuration backup and archive, version history, comparison, baseline/drift views, change control, jobs, and backup schedule management. |
| **Network Operations** | Run SSH command jobs across devices, reuse command templates, and review execution results. |
| **Platform administration** | Web dashboard, configurable HTTPS, module management, administrator accounts/roles, licence management, and diagnostics. |

**Protocol boundary:** RADIUS does not offer TACACS+-style per-command authorization. Available RADIUS and directory behaviors depend on the selected tac_plus-ng build and target network devices.

<details>
<summary>View the NetOpsGuard capabilities infographic</summary>

![NetOpsGuard capabilities overview](https://github.com/user-attachments/assets/c1abe186-dd4e-4519-8585-98b2f2eb2e1f)

</details>

## Quick start

### Requirements

- **OS:** Ubuntu Server 22.04, 24.04, or 26.04 LTS
- **Access:** A user with sudo privileges
- **Resources:** At least 1 GB RAM and 5 GB free disk space recommended; allocate more for production workloads, logs, and configuration archives
- **Network:** Outbound access during initial installation to obtain packages and the AAA daemon source
- **Python:** Python 3.10+ (the bootstrap can install Python 3 if missing)

Start on a fresh Ubuntu server:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/jafartavana01/NetOpsGuard.git
cd NetOpsGuard
sudo bash bootstrap.sh
```

The installer provisions the platform, PostgreSQL, the AAA service, and an initial administrator account. It also generates a self-signed HTTPS certificate for initial access.

When installation completes, open:

```text
https://<server-ip>:8420
```

Sign in using the administrator credentials created during installation. **Do not expose the management interface directly to the public Internet.** Restrict access to trusted administrator networks and replace the self-signed certificate with one issued by your trusted CA.

For detailed installation, firewall, service, and removal instructions, see the [installation guide](docs/INSTALL.md).

### Network connectivity

| Connection | Default port | Direction / purpose |
| --- | --- | --- |
| Web management | TCP **8420** | Administrator browser → NetOpsGuard |
| TACACS+ | TCP **49** | Network device → AAA server |
| RADIUS, when enabled | UDP **1812 / 1813** | Network device → authentication / accounting listener |
| SSH | TCP **22** | NetOpsGuard → managed devices for supported operations |
| LDAPS, when configured | TCP **636** | NetOpsGuard → directory server |

The management port and certain service settings are configurable. Open only the ports needed for your deployment; directory and device ports depend on your environment. Database access is intended to remain local or otherwise appropriately restricted.

## Your first configuration

1. **Secure access.** Replace or trust the HTTPS certificate, restrict management network access, and review administrator roles under **Platform**.
2. **Add devices.** In **TACACS+ → Devices**, create inventory records or use network discovery. Configure each device's AAA shared secret as needed.
3. **Connect identities.** Create local users/groups or configure **Platform → Active Directory** with the appropriate directory and certificate trust settings.
4. **Build authorization.** Create **Command Sets** and **Policies**, select the intended users/groups and devices, and review the effective restrictions.
5. **Preview before applying.** Open **TACACS+ → Configuration**, inspect validation messages and the candidate diff, and apply only when it matches your intent.
6. **Test with a lab device.** Confirm both permitted and denied commands, then inspect **Accounting**, **Sessions**, and **Access Events**.
7. **Explore other modules.** Try Security Center audits, NCM configuration archives/diffs, and Network Operations command jobs on authorized devices.

**Important:** Saving a policy is not the same as applying it to the AAA daemon. The policy simulator is a planning aid; verify real decisions against the target NAS.

## Operations and limitations

- Test directory integration, device-specific authentication behavior, and authorization on the actual NAS and identity infrastructure before broad deployment.
- Policy scopes with unresolved or invalid references can block an AAA configuration apply rather than silently becoming unrestricted.
- NCM backups, comparisons, and schedule management are available; **verify that scheduled backups actually run and retain their archives in your environment before relying on unattended backup schedules**.
- Back up the PostgreSQL database **and** the associated configuration/encryption material. A generated AAA configuration backup alone is not a full platform backup.
- Upgrading an existing populated deployment is not a guaranteed one-command schema migration. Read the [upgrade and recovery guide](docs/UPGRADE.md) before attempting an upgrade.
- Some directory authority modes, historical policy restoration scenarios, and advanced RADIUS capabilities have limitations. See the [configuration guide](docs/CONFIGURATION.md).

## Documentation

| Guide | What it covers |
| --- | --- |
| [Install](docs/INSTALL.md) | Supported hosts, installation, initial access, network ports, services, and uninstall |
| [Configuration](docs/CONFIGURATION.md) | Identity, policies, validation, application, and operational limitations |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Connectivity, service checks, AAA problems, and backup verification |
| [Upgrade & recovery](docs/UPGRADE.md) | Pre-upgrade backups, compatibility checks, and recovery planning |
| [Licensing](docs/LICENSING.md) | Free five-device Community edition and signed licence limits |
| [Architecture](docs/ARCHITECTURE.md) | High-level platform layout and security boundaries |
| [Changelog](CHANGELOG.md) | User-visible changes in the current published source |
| [Security reporting](SECURITY.md) | Private vulnerability reporting and deployment responsibilities |
| [Contributor testing](docs/TESTING.md) | Optional test instructions for contributors |
| [FAQ](docs/faq.md) | Frequently asked questions about features, licensing and deployments |
| [Support](SUPPORT.md) | How to request help and report bugs |
| [Contributing](CONTRIBUTING.md) | Contribution guidelines and validation expectations |

## Licensing

NetOpsGuard's source code is available under the [Apache License 2.0](LICENSE). Runtime editions use device-count entitlements: **Community is free for up to five devices**, and signed licences allow larger fleets. Read [docs/LICENSING.md](docs/LICENSING.md) for details.

### Introductory licence pricing (USD)

| Edition | Managed devices | Introductory annual licence |
| --- | ---: | ---: |
| Community | Up to 5 | **Free** |
| Starter | Up to 15 | **US$99/year** |
| Professional | Up to 50 | **US$299/year** |
| Business | Up to 100 | **US$599/year** |
| Enterprise | Up to 300 | **US$1,299/year** |
| Unlimited | No fixed device limit | **Contact for a quote** |

Prices are proposed introductory annual rates, subject to confirmation with the maintainer; they are not an automated checkout or a guarantee of support or SLA. Available product features are not differentiated by these device-count editions. [Full pricing and comparison](docs/pricing.md).

### NCM price comparison

ManageEngine's separate Network Configuration Manager Professional edition lists **US$958/year for 50 devices**, compared with NetOpsGuard **US$299/year for up to 50 devices**. NetOpsGuard also includes its available TACACS+ AAA, RADIUS, AD/LDAP, NCM, Security Center, and Network Operations modules. This is a price and product-scope comparison, **not a claim of equivalent NCM functionality or support**. [Official ManageEngine NCM prices](https://store.manageengine.com/network-configuration-manager/index.html) (checked 13 October 2026). [Detailed comparison](docs/pricing.md).

### Request a NetOpsGuard licence

For more than five managed devices, licence pricing, or licence migration questions, contact the project maintainer through one of these channels:

- **Email:** [tavanajafar2@gmail.com](mailto:tavanajafar2@gmail.com)
- **Telegram:** [@Powerinfossl](https://t.me/Powerinfossl)
- **WhatsApp ID:** `@jafartavana0`
- **Phone:** [+98 917 011 8221](tel:+989170118221) (`00989170118221`)

Include the requested device limit and a short description of your deployment. For machine-bound licences, send the generated licence request **privately**; never publish it or any passwords, keys, or production configuration in GitHub issues.

## Support, feedback, and security

Use [GitHub Issues](https://github.com/jafartavana01/NetOpsGuard/issues) for bug reports, questions, and feature suggestions. Include the affected version or commit, relevant sanitized logs, and steps to reproduce; **never post secrets, private keys, device configurations, or customer information**.

For potential vulnerabilities, follow the private disclosure instructions in [SECURITY.md](SECURITY.md) instead of opening a public exploit report.

**Project status:** NetOpsGuard is actively developed. The presence of a feature in the UI does not guarantee compatibility with every device, daemon build, or production environment; validate your critical AAA, NCM, and recovery workflows before production use.
