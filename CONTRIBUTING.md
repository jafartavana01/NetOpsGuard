# Contributing to NetOpsGuard

Thanks for helping improve NetOpsGuard, a self-hosted network AAA and security operations platform.

## Before opening a pull request

- Read the [README](README.md), [configuration guide](docs/CONFIGURATION.md), [support policy](SUPPORT.md), and [code of conduct](CODE_OF_CONDUCT.md).
- Check [existing issues](https://github.com/jafartavana01/NetOpsGuard/issues) before proposing a duplicate change.
- For a larger behavioral change, open an issue first to agree on the expected user-facing result.
- Do not include production credentials, device configurations, encryption material, database dumps, customer information, or unredacted logs in commits or issues.

## Change principles

- Preserve restrictive authorization scope: unknown device, group, or source references must not silently become unrestricted.
- Keep TACACS+ command authorization separate from RADIUS protocol capabilities.
- Do not claim a feature is production-ready based solely on a simulator, mock database, or browser fixture.
- Avoid public documentation that describes secrets or internal security bypass techniques.
- Prefer small changes with a clear explanation of which workflows they affect.

## Validation

Run the checks relevant to your changes and report the actual outcomes. The [contributor testing guide](docs/TESTING.md) lists available contract, browser, and PostgreSQL tests. A skipped PostgreSQL or native-daemon integration test must be reported as **not run**, not as passed.

For UI or documentation changes, verify that navigation works, links resolve, text is accessible, and instructions match the current shipped behavior.

## Pull requests

Include a concise summary, motivation, user impact, actual test results, and any deployment or compatibility limitations. Where applicable, describe safe rollback and note which environments were **not** tested.

For security reports, do **not** open a public PR describing an exploit. Follow [SECURITY.md](SECURITY.md).

Contributions are reviewed on a best-effort basis; opening a PR does not imply acceptance.
