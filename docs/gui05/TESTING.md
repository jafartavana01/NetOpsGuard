# GUI-05 verification

Run from the extracted repository root. The GUI-05 preview renders the real Jinja templates and production JavaScript, but supplies synthetic HTTP responses. It is not a production server or native AAA/database integration test.

Use the project's Python dependencies, Node with Playwright, a compatible Chromium executable and the Chart.js 4.5.1 UMD bundle already used by the application. These browser dependencies are development-only and are not included in the snapshot.

```bash
export GUI_CHROMIUM=/absolute/path/to/headless_shell
export GUI_CHART_JS=/absolute/path/to/chart.umd.min.js
export GUI05_EVIDENCE=/absolute/path/to/gui05-evidence
python tests/gui05/test_context.py
node tests/gui05/browser.cjs
```

The browser suite starts and stops its loopback fixture server on port 8769. It verifies supported page behavior, stored scores and actual status distinctions, escaping and exact evidence copying, keyboard drawers, presentation permissions, schedule payloads, error states, repeated SPA navigation, and eight views at 1366/1440/1920/2560 pixels. JSON results include assertions, HTTP requests and screenshot names. No real devices, directory, database or daemon are contacted.

Existing regressions (unchanged scripts):

```bash
export GUI03_EVIDENCE=/absolute/path/to/existing-regressions
python tests/gui03/run_checks.py
python tests/gui04/test_context.py
python tests/dependencies/test_deletion.py
node tests/gui03/browser.cjs
node tests/gui04/browser.cjs
node tests/dependencies/browser.cjs
python tests/dependencies/postgres_integration.py
```

Keep GUI_CHART_JS set for the existing browser scripts too. GUI-03 and dependency browser checks share port 8767 and must run sequentially. Set GUI04_EVIDENCE and DEPENDENCY_EVIDENCE to route their artifacts outside the source tree. Some older scripts write evidence under docs; exclude generated evidence from release packages.

The regression runner includes both F03 modes:

```bash
python tests/f03/run.py --json /absolute/path/to/f03-results.json
python tests/f03/run.py --no-xfail
```

The inherited contract currently has 189 passing cases and 13 expected failures. The no-xfail invocation intentionally exits 1 with those same 13 failures. GUI-05 does not remove or weaken them. PostgreSQL tests require a disposable F03_POSTGRES_DSN and explicitly skip without it. Never point destructive integration tests at a production database. Native tac_plus-ng/MAVIS, real SSH collection and scheduler execution require separate integration verification.
