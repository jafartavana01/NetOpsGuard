# AAA workspace regression checks

GUI-03 is a presentation-only update to the current published functionality. Python APIs, database models, compiler, external identity validation, atomic policy saves and restoration remain unchanged.

## Run

Use the project's Python dependencies and Node with Playwright installed. Set `GUI_CHROMIUM` to an installed Chromium executable and `GUI_CHART_JS` to a local copy of the existing pinned Chart.js 4.5.1 bundle for GUI-01/02 tests. These are test dependencies, not new runtime dependencies.

```sh
node tests/gui03/test_workspace.cjs
python tests/gui03/test_accounting.py
node tests/gui03/browser.cjs
python tests/gui03/run_checks.py
```

`GUI03_EVIDENCE` optionally selects a directory outside the source tree. Default: `docs/gui03/evidence` (ignored). Browser fixtures bind loopback port 8767, render actual Jinja templates and intercept API requests with synthetic data. Do not deploy the fixture server.

The runner invokes the existing F03 suite (both modes), nine existing script checks, metadata tests, GUI-01/02 contracts, four PostgreSQL integration entry points, atomic/history browser tests and GUI-01/02 browser tests. An exit code of 1 is expected only from `--no-xfail`; inspect the report to verify the remaining known failures, not new failures. GUI-03 originally had 23 expected failures; dependency-aware deletion subsequently fixed ten deletion cases (189 PASS / 13 XFAIL). See `docs/dependencies/TESTING.md` for their real-database test adapter.

PostgreSQL tests require the explicitly configured disposable `F03_POSTGRES_DSN` and otherwise skip. Skips are not database verification. GUI-03 tests make no native daemon, live LDAP, live device provisioning or installed-service claims.

## Presentation contracts

- Only parsed `permit` and `deny` tokens receive authorization success/denial badges. Other tokens remain Unknown.
- Authentication vocabulary is separate; authentication success does not imply command permission.
- Accounting raw tokens, exact case-insensitive result filtering, timestamp behavior and CSV fields remain unchanged.
- Legacy device and device-group summaries retain AND. Tree parentheses retain AND/OR/NOT structure. Mixed dimensions are not projected into misleading independent scopes.
- Missing roots, unsupported leaves and unresolved references never render as unrestricted.
- Summary text describes stored intent, not backend validation or deployed authorization.
- Condition-tree save remains one authoritative POST/PUT. The pre-existing atomic browser test asserts no second tree write.
- Directory counts remain external observations, not counts inferred from local users. Binding identifiers are in Details.
- Tables filter and page only loaded rows; this does not expand backend log tails or query scope.
- Device workflow navigation performs no configuration writes. Existing safety confirmations remain in place.
- Simulator/effective-access output remains advisory because the backend does not expose authoritative support/validity certification.
- Both analysis pages read existing candidate diagnostics separately. A valid candidate is not proof of evaluator parity; blocked candidates show their diagnostic codes. Permission/network failure yields unavailable context, never validation success.

## Inventory

All pages are served by `app/web/routes_tacacs.py`, extend `app_shell.html`, reuse GUI-01 tokens/dialogs and retain their existing inline view scripts. Shared additions: `aaa-workspace.js` and `gui-v2/aaa.css`, loaded by `base.html`.

| View / template | Existing APIs | GUI-03 additions |
| --- | --- | --- |
| Accounting / `accounting.html` | `/api/tacacs-accounting`, `/export`, device groups | Outcome icons, compact filters, raw evidence drawer, loaded-row paging |
| Policies / `policies.html` | `/api/policies`, `/{id}/condition-tree`, history, reference inventories | WHO/WHERE/ACCESS/DEFAULT, exact scope detail, wide sectioned editor |
| Users / `users.html` | `/api/tacacs-users`, groups, AD search, logs | Source details, stored-group caveats, direct policy references, filtering |
| Groups / `groups.html` | `/api/tacacs-groups`, external sources, AD group members | Authority/source/membership/binding columns, detailed binding drawer |
| Devices / `devices.html` | devices, monitoring, network scan, AAA template/provisioning, grants | Inventory / Monitoring / Scan & provision / Access grants workflow navigation |
| Device groups / `device_groups.html` | `/api/device-groups`, members, devices | Filtered inventory, wider member view and member search |
| Sessions / `sessions.html` | `/api/tacacs-accounting/sessions` | Context help, observed-state labels, wide evidence timeline |
| Access events / `access_events.html` | `/api/tacacs-accounting/access-events` | Consistent outcomes, evidence drawer; original filters/pagination/export retained |
| Command sets / `command_sets.html` | `/api/command-sets`, categories, policies | Description/rule visibility, rule/reference drawer, wider editor |
| Categories / `command_categories.html` | `/api/command-categories` | Filtering and explicit create/delete-only capability |
| Effective access / `effective_access.html` | `/api/effective-access/*`, user/device inventory | Name suggestions, explicit non-authoritative result wording |
| Simulator / `policy_simulator.html` | `/api/policy-simulator/evaluate`, user/device inventory | Name suggestions, advisory result/trace labels |
