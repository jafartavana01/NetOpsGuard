# Security reporting

Please report suspected vulnerabilities privately. Use GitHub's **Report a vulnerability** control on this repository's Security tab when private reporting is enabled:

https://github.com/jafartavana01/NetOpsGuard/security/advisories/new

If that control is unavailable, contact the repository maintainer through their GitHub profile to request a private reporting channel. If no private contact method is listed, open an issue containing only a request for a private contact channel, without vulnerability details. Do not publish exploit instructions, secrets or affected customer information in a public issue.

Include the affected release/commit, component, impact, prerequisites and a minimal sanitized reproduction in the private report. Use placeholders for credentials and infrastructure identifiers. Never send production passwords, private keys, database dumps or unredacted configurations.

There is no published response-time SLA. Do not assume that a report has been received until the maintainer acknowledges it. The maintainer should enable private vulnerability reporting before publication.

## Deployment responsibilities

Restrict management access, enable HTTPS, protect backups and encryption keys, assign least-privilege administrator roles and test authorization outcomes before deploying new policy. Do not expose fixture servers or test MAVIS backends from the tests directory. Review the release's configuration limitations before upgrade.
