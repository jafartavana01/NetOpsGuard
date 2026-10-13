---
layout: default
title: "NetOpsGuard Licensing — Free Community and Device Limits"
description: "Get NetOpsGuard licensing information. Community is free for five devices; contact the maintainer via email, Telegram, WhatsApp or phone to request a larger licence."
permalink: /licensing/
---

# NetOpsGuard licensing and licence requests

NetOpsGuard is a self-hosted network AAA and security operations platform. The **Community edition is free for up to five managed devices** and includes the currently available platform features. Teams managing larger networks can request **signed licences** with increased device limits.

The project's source code is licensed separately under [Apache License 2.0](https://github.com/jafartavana01/NetOpsGuard/blob/main/LICENSE). A signed runtime licence determines the installation's device entitlement.

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
