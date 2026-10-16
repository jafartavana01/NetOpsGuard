# Device deletion and retained history

Run from the repository root with the project dependencies installed:

```sh
python tests/device_retention/test_retention.py
python tests/device_retention/test_migration.py
python tests/device_retention/postgres_integration.py
node tests/device_retention/browser.cjs
```

The retention suite exercises real SQLite transactions, policy compilation, rollback, permission/CSRF enforcement, archive reads/diffs, and missing-target deployment rejection. Migration tests start with actual cascading foreign keys and verify retained rows, indexes, triggers, repeatability, and rollback.

PostgreSQL tests require a disposable `F03_POSTGRES_DSN` and otherwise explicitly skip. They create and remove an isolated schema; SQLite results do not establish PostgreSQL transaction behavior.

Browser tests use the existing GUI preview and controlled API responses. Set `GUI_CHROMIUM` to the installed browser executable and `GUI_CHART_JS` as required by that preview. They cover confirmation, permissions, stale/network errors, cancellation, and responsive layouts. They do not contact real network devices or apply daemon configuration.
