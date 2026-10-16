# Audit comparison regressions

Run from the repository root with application dependencies installed:

```sh
python tests/security_comparison/test_comparison.py
python tests/security_comparison/postgres_integration.py
GUI_CHROMIUM=/path/to/chromium node tests/security_comparison/browser.cjs
```

The backend suite exercises classification, evidence integrity, real SQLite persistence,
retained-history foreign keys, and API permissions/CSRF. SQLite adapts the existing
PostgreSQL JSONB DDL to JSON; it is not proof of PostgreSQL behavior. Set
`F03_POSTGRES_DSN` to a disposable PostgreSQL database to run the independent integration
suite, which creates and drops isolated schemas. Otherwise those tests explicitly skip.

Live and scheduled audit tests mock SSH transport while using the actual audit engine,
persistence, and API. Browser tests render real templates and JavaScript with controlled
HTTP responses, including failed requests and SPA navigation. None of these tests
claims verification against a physical Cisco device.
