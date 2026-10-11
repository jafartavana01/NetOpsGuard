# Dependency-aware deletion tests

Use the application's Python dependencies and Playwright/Chromium for browser checks.

```sh
python tests/dependencies/test_deletion.py
python tests/dependencies/postgres_integration.py
node tests/dependencies/browser.cjs
python tests/f03/run.py --json tests/f03/results.json
python tests/f03/run.py --no-xfail
python tests/gui03/run_checks.py
node tests/gui03/browser.cjs
```

`DEPENDENCY_EVIDENCE`, `GUI03_EVIDENCE`, `GUI_CHROMIUM`, `GUI_CHART_JS`, and
`GUI_PYTHON` optionally select output/dependency paths. Do not run the two browser
suites that use port 8767 concurrently. Browser fixtures use actual templates and
scripts with synthetic HTTP data; they never represent installed AAA behavior.

The deletion transaction suite uses real SQLite commits and foreign keys. Only
DDL portability is adapted: JSONB renders as JSON and unsupported deferred
uniqueness is omitted in the test schema. This does not certify the complete
application as a SQLite deployment or prove PostgreSQL semantics.

`postgres_integration.py` requires a **disposable** PostgreSQL `F03_POSTGRES_DSN`.
It creates/drops private schemas, uses the actual production model constraints,
executes real commits and runs the same transaction/race assertions. Without a
DSN every case is explicitly skipped. It does not substitute SQLite.

Ten original F03 object-deletion scenarios now use `legacy_contract_bridge.py`
and the real SQLite fixture because AST-only route doubles cannot execute the
new delegated transaction service. Original scenario names remain. Assertions
are stronger: HTTP 409 plus retained object, policy and exact reference. These
ten are now passing security contracts; remaining F03 expected failures are not
reclassified. No test-runner exception is counted as a security rejection.

The server serializes unsafe HTTP database transactions before the first read:
PostgreSQL transaction advisory lock at READ COMMITTED; SQLite BEGIN IMMEDIATE.
Reinspection and mutation share that transaction. Direct SQL or custom scripts
outside the guarded application are not covered by this application-level
protocol. Concurrent independent-reader PostgreSQL behavior and installed
upgrade/lock contention must be verified on the supported PostgreSQL deployment.

No tests apply daemon configuration, contact LDAP or provision real devices.
