# Contributor testing

Install the project Python requirements in an isolated development environment. HTTP tests additionally use `httpx`. Node.js is needed for JavaScript contracts; browser tests use the Playwright Node package and an installed Chromium executable. Do not run fixture servers or synthetic MAVIS backends as production services.

```sh
python tests/f03/run.py --json tests/f03/results.json
python tests/f03/run.py --no-xfail
python tests/check_undefined_names.py
python tests/test_licensing.py
python tests/test_log_parsing.py
python tests/test_policy_block_authorization.py
python tests/test_security_command_pattern.py
python tests/test_security_rbac.py
python tests/test_security_secrets.py
python tests/test_security_ssh_hostkey.py
python tests/test_security_xss.py
python tests/test_public_metadata.py
python tests/gui01/test_contract.py
python tests/gui02/test_contract.py
```

The F03 runner treats unexpected successes as requiring review and does not disguise infrastructure errors as expected security failures. `--no-xfail` exposes outstanding contracts and may intentionally exit nonzero. Do not weaken assertions to obtain a green result.

## Real database tests

Set `F03_POSTGRES_DSN` privately to a dedicated disposable PostgreSQL database, never a production database. The test role needs permission to create/drop isolated test schemas. Without a DSN these suites explicitly skip; a skipped test is not a passed test.

```sh
python tests/f03/atomic_postgres_integration.py
python tests/f03/restoration_postgres_integration.py
python tests/f03/external_postgres_integration.py
python tests/f03/postgres_integration.py
```

Fast tests and mocked HTTP tests do not establish PostgreSQL commit, FK or isolation behavior. Native daemon tests likewise require an actual supported daemon/backend environment; do not infer native behavior from fixture interpreters.

## Browser tests

Set `GUI_PYTHON` to the Python interpreter with project dependencies, `GUI_CHROMIUM` to the installed Chromium executable and `GUI_CHART_JS` to a local copy of Chart.js 4.5.1's `chart.umd.min.js`. The browser fixtures serve actual templates with synthetic data on loopback. Scripts start their own fixture server; they do not log into a real deployment.

```sh
node tests/gui01/browser.cjs
node tests/gui02/browser.cjs
node tests/f03/atomic_browser.cjs
node tests/f03/restoration_browser.cjs
```

Browser evidence is generated under docs directories and should not be committed. Browser success is not an end-to-end database or AAA claim.

## System & Administration regression tests

```sh
python tests/gui06/test_permissions.py
node tests/gui06/browser.cjs
```

The GUI-06 browser script uses `python` from PATH, Playwright, and `GUI_CHROMIUM`. It serves actual templates on loopback port 8770 with synthetic API responses. It writes no evidence files by default; `GUI06_SCREENSHOT_DIR` optionally enables temporary screenshots outside the repository.

Coverage includes account/role mutations, missing permission catalogs, confirmation and discard behavior, network/TLS saves, restart failures, directory form-versus-saved checks, late responses, secret masking, license import/download, blocked candidate diagnostics, RADIUS settings/probes, SPA/back-forward navigation, keyboard focus, and 1366/1440/1920/2560px layouts. Permission tests use the real FastAPI routes and dependencies with synthetic identities; they do not exercise PostgreSQL.

GUI-06 verification: 172 browser checks and 8 authorization/CSRF tests passed. Existing browser regressions passed (471 checks across GUI-01–05, atomic policy, restoration, and dependency deletion). F03 remains 189 PASS / 13 XFAIL; `--no-xfail` exposes those same 13 failures. PostgreSQL suites explicitly skipped 57 tests because no disposable test DSN was supplied. Native AAA, directory, and device verification was not performed in this GUI phase.

Known deferred work remains: NCM backup-schedule execution and actual backup creation, audit-comparison resolution semantics, PostgreSQL verification, native AAA/device testing, and directory TLS trust enforcement. Passing GUI checks does not clear these issues.

## Interface consistency regression tests

```sh
node tests/gui07/browser.cjs
node tests/gui07/layout.cjs
```

These scripts use `python` from PATH, Playwright, `GUI_CHROMIUM`, and (for the layout check) `GUI_CHART_JS`. Run them sequentially: both serve actual templates on loopback port 8771 with synthetic API fixtures. They print results without creating evidence packages.

Coverage includes rapid and redirected navigation, refresh/back/forward, drawer cleanup, phone/tablet layouts, keyboard cancellation and sorting, notification accessibility, stale RADIUS scope values, missing option lists, denied and failed saves, blocked candidates, and interrupted Apply requests. An interrupted Apply reports an unknown outcome and requires a fresh review before retrying.

GUI-07 verification: 88 focused browser checks and 126 layout checks passed. The layout matrix covers 42 pages at 390, 768, and 1440px; focused dialog/table checks also cover 360, 1366, and 1920px. Existing GUI-01–06, atomic-policy, restoration, and deletion browser regressions passed all 643 checks. F03 remains 189 PASS / 13 XFAIL, with the same 13 failures exposed by `--no-xfail`. Existing authorization/CSRF checks and project regression scripts passed without changing their assertions.

PostgreSQL suites explicitly skipped 57 tests without a disposable test DSN. Real Cisco, tac_plus-ng/MAVIS, directory, and NAS verification were not performed. Known NCM scheduling, audit-comparison, LDAP certificate-verification, and role-deletion privilege-fallback defects remain open; these interface checks do not clear them for release.

## Compact interface and dashboard regression tests

```sh
python tests/gui071/test_activity.py
node tests/gui071/browser.cjs
```

The browser script requires Playwright, `GUI_CHROMIUM`, `GUI_CHART_JS`, and the existing Python test dependencies. It serves actual templates on loopback port 8772 with synthetic API responses and writes no evidence packages.

Coverage includes real-format authorization records, fractional timezone offsets, rolling-window boundaries, malformed and missing timestamps, command-versus-login filtering, and consistent API totals/buckets. Browser checks cover compact Device/Policy actions at 390/768/1440/1920px, automatic and manual directory checks, overlapping requests, timeouts, denied/expired sessions, network failures, and SPA polling cleanup.

GUI-07.1 verification: 14 activity tests and 47 browser checks passed. Existing GUI-01–07 and policy/restoration/dependency browser suites passed 857 checks; GUI-06 required an isolated rerun after a timing-sensitive first-run failure. F03 remains 189 PASS / 13 XFAIL; `--no-xfail` exposes the same 13 failures. The older manual-only dashboard expectation was updated to require one initial check and one cleaned-up 60-second interval. Security assertions were retained.

PostgreSQL suites skipped 57 tests without a disposable test DSN. Native Cisco, tac_plus-ng/MAVIS, and directory tests remain unverified. Browser cancellation does not prove an in-flight LDAP operation has stopped on the server. Known functional and security defects listed above remain open.
