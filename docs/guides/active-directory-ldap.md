---
layout: default
title: "Active Directory and LDAPS for TACACS+ AAA"
description: "Integrate NetOpsGuard with Microsoft Active Directory or LDAP using directory group bindings, TLS trust, and scoped TACACS+ command authorization."
permalink: /guides/active-directory-ldap/
---

# Integrate Active Directory and LDAP with network AAA

Using **Active Directory (AD) or LDAP** for network device administration helps operators manage identities centrally rather than creating unrelated usernames on every router or switch. NetOpsGuard supports directory-backed identity integration through its configured **MAVIS/LDAP** integration and external group policy binding.

## Prepare the directory integration

Before importing groups, gather the correct directory endpoint, service account permissions, directory search settings, and the certificate trust necessary for a secure connection. Use **LDAPS**, commonly on TCP **636**, when appropriate for your directory environment.

Verify that the NetOpsGuard server can reach the directory controller and validate its certificate. An LDAP server address and a group display name alone are not evidence that the identity source is usable.

## Map a directory group to authorization

1. Configure directory connectivity under **Platform → Active Directory**.
2. Test the connection and directory authentication against the intended controller.
3. Import or bind the relevant external group to its specific identity source.
4. Define the intended devices or device groups, command sets, and policy conditions.
5. Inspect the generated candidate configuration for binding diagnostics before Apply.
6. Test with a real directory user who is a member of the group **and** a user who is not a member, using the target network device.

Directory membership may be resolved at authentication time and does not necessarily appear as local user rows. Do not treat locally enumerated user/group records as proof of native daemon membership decisions.

## Key security considerations

- Validate server certificates and restrict directory bind credentials to the permissions required.
- Avoid treating an unknown group or failed directory lookup as permission to match all users.
- Test nested groups or special group names against the actual directory/daemon behavior when these apply.
- Review legacy identity bindings during upgrades; not every proposed authority mode is implemented in the public release.

For product-specific limitations, read the [configuration guide](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/CONFIGURATION.md). Continue with [command authorization]({{ '/guides/tacacs-command-authorization/' | relative_url }}).
