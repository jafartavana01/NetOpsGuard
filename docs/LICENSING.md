# Licensing

The Community edition supports up to five devices. Signed licences increase the device limit; the installed entitlement display is authoritative for the imported licence. Licensing does not turn planned functionality into supported functionality.

## Requesting a licence

Contact the NetOpsGuard maintainer to request a signed licence for a higher device limit, ask about licence availability, or discuss migration to another server:

- **Email:** [tavanajafar2@gmail.com](mailto:tavanajafar2@gmail.com)
- **Telegram:** [@Powerinfossl](https://t.me/Powerinfossl)
- **WhatsApp ID:** `@jafartavana0`
- **Phone:** [+98 917 011 8221](tel:+989170118221) (`00989170118221`)

Tell us the number of devices you need to manage and, if applicable, which existing installation you want to migrate. For a machine-bound licence, generate the licence request file first and share it only through an agreed private contact channel. **Never send passwords, database credentials, private keys, or unredacted device configurations.**

See the [public licensing information page](licensing.md) for a short overview of the process.

## Installing a signed licence

Import licences through the platform's License page. For a machine-bound licence, generate a licence request from that page or run `sudo python3 collect_fingerprint.py` on the target host and provide the resulting request to the issuer through an agreed private channel. Do not send database credentials or encryption keys.

Licences contain a signed payload and an Ed25519 signature. The application ships the issuer's public verification key; the issuer's private signing key must remain outside the repository and release package. Synthetic development signing material in automated tests is not trusted by the production verifier.

A database backup does not replace a valid licence or a matching machine identity. Review licence status after moving an installation or changing hardware. Contact the maintainer for licence issuance and migration questions.

The source-code licence is [Apache License 2.0](../LICENSE). It is separate from signed runtime entitlements.
