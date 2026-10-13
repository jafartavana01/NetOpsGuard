---
layout: default
title: "NetOpsGuard Pricing and Licensing — Free, Starter and Enterprise"
description: "Compare NetOpsGuard annual licence prices: free for 5 devices, Starter $99/year for 15, Professional $299/year for 50, and Business $599/year for 100."
permalink: /licensing/
---

# NetOpsGuard licensing and licence requests

NetOpsGuard is a self-hosted network AAA and security operations platform. The **Community edition is free for up to five managed devices** and includes the currently available platform features. Teams managing larger networks can request **signed licences** with increased device limits.

The project's source code is licensed separately under [Apache License 2.0](https://github.com/jafartavana01/NetOpsGuard/blob/main/LICENSE). A signed runtime licence determines the installation's device entitlement.

## Introductory NetOpsGuard annual pricing

| Edition | Managed devices | Introductory annual licence |
| --- | ---: | ---: |
| Community | Up to 5 | **Free** |
| Starter | Up to 15 | **US$99/year** |
| Professional | Up to 50 | **US$299/year** |
| Business | Up to 100 | **US$599/year** |
| Enterprise | Up to 300 | **US$1,299/year** |
| Unlimited | No fixed device limit | **Contact for a quote** |

All editions include the currently available features. Prices are proposed introductory rates in **US dollars**, subject to confirmation when requesting a signed licence. Contact the maintainer for availability and terms. These prices do not include any promised SLA or paid implementation services.

**Interested in a comparison?** The [pricing comparison]({{ '/pricing/' | relative_url }}) includes ManageEngine Network Configuration Manager's published annual subscription rates and important differences in product scope and support.

## Contact the maintainer to request a licence

To ask about expanded device limits, licence issuance, or licence migration, use any of these contact methods:

- **Email:** [tavanajafar2@gmail.com](mailto:tavanajafar2@gmail.com)
- **Telegram:** [@Powerinfossl](https://t.me/Powerinfossl)
- **WhatsApp ID:** `@jafartavana0`
- **Phone:** [+98 917 011 8221](tel:+989170118221) (`00989170118221`)

When contacting the maintainer, mention **NetOpsGuard**, your requested device count, and whether you need a new licence or a migration. You can also describe your deployment environment without revealing sensitive infrastructure information.

## Generate a licence request

For a machine-bound licence, use the application's **Platform → License** page to generate a licence request. An alternative, on the NetOpsGuard server, is:

```bash
sudo python3 collect_fingerprint.py
```

Share the generated request through an agreed **private channel**. Do not publish licence requests, private keys, passwords, database credentials, or live network device configurations in public GitHub issues.

After obtaining a signed licence, import it through the **License** page and check that the displayed device limit and entitlement match your request.

## More information

- [Read the complete licensing guide](https://github.com/jafartavana01/NetOpsGuard/blob/main/docs/LICENSING.md)
- [NetOpsGuard source repository](https://github.com/jafartavana01/NetOpsGuard)
- [Installation instructions]({{ '/guides/getting-started/' | relative_url }})
- [Frequently asked questions]({{ '/faq/' | relative_url }})
