# Policy-scope regression tests

This suite retains security contracts for scope resolution, compilation, restoration, complete policy mutation and simulator behavior. Some contracts intentionally remain expected failures; do not remove or invert them to hide incomplete work.

See [contributor testing](../../docs/TESTING.md) for dependencies, commands and the separation between fast, HTTP, PostgreSQL and native-daemon verification. Use `run.py` as the authoritative fast runner. Automated fixture cases are synthetic and are not deployment examples.
