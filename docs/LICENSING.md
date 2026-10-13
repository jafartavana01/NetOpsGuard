# Licensing

The Community edition supports up to five devices. Signed licences increase the device limit; the installed entitlement display is authoritative for the imported licence. Licensing does not turn planned functionality into supported functionality.

## Introductory annual licence prices

| Edition | Managed devices | Introductory annual licence |
| --- | ---: | ---: |
| Community | Up to 5 | **Free** |
| Starter | Up to 15 | **US$99/year** |
| Professional | Up to 50 | **US$299/year** |
| Business | Up to 100 | **US$599/year** |
| Enterprise | Up to 300 | **US$1,299/year** |
| Unlimited | No fixed device limit | **Contact for a quote** |

Prices are **proposed introductory rates in US dollars**, quoted by the maintainer and subject to confirmation before purchase. All listed editions include the currently available platform feature set; licences primarily adjust the permitted number of devices. These figures do not imply an automatic online checkout, a particular service-level agreement, or tested production compatibility with all device types. The active imported entitlement displayed by the platform remains authoritative.

See [Pricing and product comparison](pricing.md) for a comparison with ManageEngine's separate NCM product and the source of the published competitor prices.

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
