# GUI-04 verification

Run from the repository root with the project's Python dependencies and Node Playwright installed. Browser tests start a loopback-only Jinja preview server and intercept API calls with synthetic inventory. They do not connect to PostgreSQL, a daemon, LDAP, or network devices. Do not deploy the preview server.

```bash
python tests/gui04/test_context.py
GUI_CHROMIUM=/absolute/path/to/chromium GUI04_EVIDENCE=/absolute/path/to/evidence node tests/gui04/browser.cjs
```

`GUI_CHROMIUM` may be omitted when Playwright's supported Chromium is installed. `GUI_CHART_JS` optionally points to a local Chart.js bundle for inherited preview routes. The default evidence directory is `docs/gui04/evidence/` and is ignored by Git. Port 8768 must be free. The browser runner executes production templates/scripts, tests read-only action visibility, errors/empty states, exact archive and diff content, bounded text rendering, modal focus, schedule scope preservation and repeated SPA navigation. It captures all 13 pages at widths 1366, 1440, 1920 and 2560, height 1000. Screenshots use completed animations.

Historical regression commands:

```bash
python tests/gui03/run_checks.py
node tests/gui03/browser.cjs
python tests/dependencies/test_deletion.py
node tests/dependencies/browser.cjs
python tests/dependencies/postgres_integration.py
```

Historical browsers share port 8767 and must run sequentially. The GUI-03 runner includes normal F03 and `--no-xfail`: the latter deliberately returns 1 for the existing 13 contract failures. No F03 assertions or classifications were changed. PostgreSQL scripts skip without a disposable `F03_POSTGRES_DSN`; skips are not integration verification.
