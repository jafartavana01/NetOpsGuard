# Licensing

The Community edition supports up to five devices. Signed licences increase the device limit; the installed entitlement display is authoritative for the imported licence. Licensing does not turn planned functionality into supported functionality.

Import licences through the platform's License page. For a machine-bound licence, generate a licence request from that page or run `sudo python3 collect_fingerprint.py` on the target host and provide the resulting request to the issuer through an agreed private channel. Do not send database credentials or encryption keys.

Licences contain a signed payload and an Ed25519 signature. The application ships the issuer's public verification key; the issuer's private signing key must remain outside the repository and release package. Synthetic development signing material in automated tests is not trusted by the production verifier.

A database backup does not replace a valid licence or a matching machine identity. Review licence status after moving an installation or changing hardware. Contact the maintainer for licence issuance and migration questions.

The source-code licence is [Apache License 2.0](../LICENSE). It is separate from signed runtime entitlements.
