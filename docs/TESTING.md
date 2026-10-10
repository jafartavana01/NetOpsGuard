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
