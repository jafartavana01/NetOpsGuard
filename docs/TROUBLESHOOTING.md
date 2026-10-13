# Troubleshooting NetOpsGuard

This guide covers first checks for installation, management access, AAA behavior, and network configuration backups. Run commands on the installed Ubuntu server unless otherwise noted. Never share unsanitized logs or configurations in public issues.

## Check service health

```bash
sudo systemctl status aaa-platform.service --no-pager
sudo systemctl status tac-plus-ng.service --no-pager
sudo ss -lntup
```

The default management endpoint is HTTPS on TCP 8420, and TACACS+ listens on TCP 49. Check the actual configured ports before assuming the defaults apply. The separate service names above are the installed service names; they do not necessarily use the public product name.

If a service has failed, inspect its startup messages:

```bash
sudo journalctl -u aaa-platform.service -n 60 --no-pager
sudo journalctl -u tac-plus-ng.service -n 60 --no-pager
```

Some application output is redirected to files instead of the systemd journal. Inspect relevant files under `/var/log/aaa-platform/` while protecting any credentials and configuration content.

## Cannot reach the management GUI

1. Check whether the management service is active and listening on TCP 8420 (or your configured port).
2. Verify routing and the host firewall between the browser and the server.
3. Use `https://<server-ip>:8420` for a normal fresh installation.
4. A self-signed certificate can cause a browser trust warning; replace it with a trusted certificate for regular use. Do not ignore unexpected identity or certificate errors.
5. If HTTPS was explicitly enabled but certificate files are missing, restore the configured certificate and key before restarting.

If HTTPS settings or the bind address have changed, reconnect using the newly configured address and port.

## Device authentication or command authorization fails

1. Verify the NAS/device can reach the AAA server on TCP 49.
2. Verify that the NAS identity and shared secret match the device inventory.
3. Verify that the user or directory group can be resolved and that the intended device/command scope is present.
4. Go to **TACACS+ → Configuration** and check the candidate diagnostics. Saved policies do not change the running daemon until an Apply succeeds.
5. Test a known allowed command and a known denied command from a controlled lab device.
6. Compare the outcome with **Accounting**, **Sessions**, **Access Events**, and **Diagnostics**. Be aware that some devices do not send accounting for denied commands; use the available authorization/access event evidence as appropriate.

A simulation result is advisory and does not prove native daemon enforcement.

## AD/LDAP authentication problems

Verify that the directory server is reachable, the expected bind/search configuration is correct, and the relevant directory TLS trust is configured. Group display names alone do not prove an external membership mapping is valid. Recheck the imported identity source and group binding, then validate on the actual directory/NAS combination.

## RADIUS behavior differs from TACACS+

RADIUS availability depends on the selected daemon build and network device. Check the configured RADIUS listener, client secret, transport, and authentication method. RADIUS has **no TACACS+-style per-command authorization**, and this release does not expose Change of Authorization (CoA) as a supported capability.

## NCM backup problems

For manual backups, confirm the selected device is reachable using SSH, its configured credentials and host key are correct, and the CLI returns the expected configuration output. Inspect the backup job outcome and configuration archive before treating it as successful.

For scheduled backups, do not assume a saved schedule means the backup actually ran. Check the enabled schedule, server-local time, target devices, recorded run/result data, job records, and resulting archive entries. Execute a controlled end-to-end schedule test and verify the created snapshot. **Unattended backup scheduling has not been established as production-verified by repository UI tests alone.**

## Upgrade or database issues

Before changing a populated installation, make recoverable copies of the database, encryption material, and application configuration. Review [Upgrade & recovery](UPGRADE.md). The installer can detect some database schema drift; it is not a guaranteed migration framework for every historical release.

## Reporting a problem

Open a [GitHub issue](https://github.com/jafartavana01/NetOpsGuard/issues) containing the affected commit or release, Ubuntu version, relevant device/platform details, what you expected, what happened, and **sanitized** error messages. For vulnerabilities, use [private security reporting](../SECURITY.md).
