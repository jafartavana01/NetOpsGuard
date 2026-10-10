# NetOpsGuard

NetOpsGuard is a self-hosted network operations and security platform for managing network infrastructure from one web interface.

It combines TACACS+ AAA, device security auditing, configuration management, network command jobs, accounting, sessions, and Active Directory/LDAP integration.

## Main capabilities

- TACACS+ authentication, authorization, accounting, and command authorization
- Local users and Active Directory/LDAP identity integration through MAVIS
- Scoped policies, command sets, condition trees, and policy simulation
- Configuration preview, validation, diff, backup, apply, and rollback workflow
- Device inventory and device groups
- SSH command jobs and reusable command templates
- Security Center audits, findings, scoring, and compliance references
- NCM configuration backups, history, baseline comparison, and diffs
- Session and permit/deny accounting views
- RADIUS authentication and accounting where supported by the installed daemon

RADIUS does not provide TACACS+-style per-command authorization.

## Requirements

- Ubuntu Server 22.04, 24.04, or 26.04 LTS
- Root or sudo access
- Internet access during installation
- At least 5 GB free disk space recommended
- At least 1 GB RAM recommended

The installer provisions PostgreSQL, installs the Python dependencies, builds tac_plus-ng from the configured source, creates the system services, and asks you to create the first administrator account.

## Installation

Clone or copy the complete repository to the server:

```bash
git clone https://github.com/jafartavana01/NetOpsGuard.git
cd NetOpsGuard
sudo bash bootstrap.sh
```

You can also run the installer directly:

```bash
sudo python3 setup.py
```

After installation, open:

```text
https://<server-address>:8420
```

The installer creates a self-signed certificate. Replace it with a certificate issued by your internal or public CA before production use, and restrict management access to trusted networks.

## First steps

1. Sign in with the administrator account created during installation.
2. Configure HTTPS and trusted administrator source networks.
3. Add network devices and device groups.
4. Configure local users or the AD/LDAP integration.
5. Create command sets and scoped policies.
6. Review the generated candidate configuration and diagnostics.
7. Apply only a valid candidate, then test expected permit and deny results on a lab device.

## Security behavior

NetOpsGuard is designed to fail closed when a restrictive policy scope cannot be resolved.

- Missing or invalid policy references block candidate application.
- Empty referenced groups are not deployable under the current policy contract.
- Invalid policies are not silently omitted from a candidate.
- Explicitly unrestricted policies remain supported.
- Policy metadata, scope, associations, priority changes, and history are saved through one server-side mutation operation.
- Restoration rejects snapshots that cannot safely reconstruct their restrictions.
- State-changing browser requests use CSRF protection.
- Sensitive device and directory values are encrypted at rest using the installation encryption key.

Administrators without an assigned granular role retain legacy broad administrator access. Assign an appropriate role when restricted administrative access is required.

## Important limitations

- TACACS+ and RADIUS behavior depends on the installed tac_plus-ng build and the target NAS/device.
- RADIUS command-level authorization is not supported.
- Directory membership and native daemon behavior should be tested in the target AD/MAVIS environment.
- Dependency-aware deletion protection and some historical policy migration cases require administrator review.
- The policy simulator is advisory and does not replace native AAA testing.
- PostgreSQL-specific transaction/security verification was not executed in the available release-validation environment.

## Documentation

- [Installation guide](docs/INSTALL.md)
- [Configuration guide](docs/CONFIGURATION.md)
- [Upgrade and recovery](docs/UPGRADE.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md)
- [Licensing](docs/LICENSING.md)
- [Changelog](CHANGELOG.md)
- [Security reporting](SECURITY.md)

## Licensing

The source is distributed under the [Apache License 2.0](LICENSE). The Community edition supports up to five devices. Larger limits use signed licence entitlements.

## Security reports

Do not publish credentials, private keys, generated AAA configuration, database dumps, or exploit details in public issues. Follow [SECURITY.md](SECURITY.md) for private vulnerability reporting.

## Project status

NetOpsGuard is actively developed. Some planned capabilities remain outside the current release, including additional identity-authority modes, advanced RADIUS authorization behavior, and broader lifecycle protections. Review the documentation and test the release in a lab before production deployment.
