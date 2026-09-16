"""
tests/test_security_rbac.py
==============================
Authorization-coverage regression tests.

Found during a security audit: 31 permissions existed in the catalogue
and were offered in the role editor, but five of them --
`config:apply`, `config:view`, `diagnostics:view`, `groups:view`,
`tacacs_users:view` -- were enforced at NO endpoint. An administrator
whose role granted only `security:view` could still apply
configuration and create TACACS+ users, because those endpoints
accepted any authenticated admin.

That is worse than a missing check, because the role editor told the
operator the permission mattered.

These tests are static: they read the route decorators and the
permission catalogue rather than starting the app, so they run without
a database and cannot be defeated by a fixture that happens to be a
superadmin.

Run:  python3 tests/test_security_rbac.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "app" / "api"

#: Endpoints that may legitimately be reached with no authentication.
PUBLIC = {("routes_auth.py", "POST", "/login"), ("routes_auth.py", "POST", "/logout")}

#: Reads any authenticated administrator may perform. Each is here
#: because it exposes nothing role-specific -- a fact to re-check when
#: adding to this set, not a place to silence a failure.
ANY_ADMIN_READS = {
    ("routes_auth.py", "GET", "/me"),              # who am I
    ("routes_system.py", "GET", "/status"),        # service up/down
    ("routes_radius.py", "GET", "/attributes"),    # static dictionary
    ("routes_radius.py", "GET", "/clients"),       # device list, no secrets
}


def _endpoints():
    for path in sorted(API_DIR.glob("*.py")):
        src = path.read_text()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)):
                    continue
                if dec.func.attr not in ("get", "post", "put", "delete", "patch"):
                    continue
                route = ""
                if dec.args and isinstance(dec.args[0], ast.Constant):
                    route = dec.args[0].value
                body = ast.get_source_segment(src, node) or ""
                yield {
                    "file": path.name,
                    "method": dec.func.attr.upper(),
                    "route": route,
                    "name": node.name,
                    "permissions": re.findall(r'require_permission\("([^"]+)"\)', body),
                    "superadmin": "get_current_superadmin" in body,
                    "any_admin": "get_current_admin" in body,
                }


def main() -> int:
    endpoints = list(_endpoints())
    failures = []

    print(f"Inspected {len(endpoints)} API endpoints.\n")

    print("1. Every endpoint is authenticated, except the login flow:")
    for ep in endpoints:
        key = (ep["file"], ep["method"], ep["route"])
        guarded = ep["permissions"] or ep["superadmin"] or ep["any_admin"]
        if guarded or key in PUBLIC:
            continue
        print(f"  FAIL  unauthenticated: {ep['file']} {ep['method']} {ep['route']}")
        failures.append(key)
    print("  PASS  no unexpected unauthenticated endpoints"
          if not failures else "")

    print("\n2. Every WRITE endpoint requires a permission or superadmin:")
    weak = []
    for ep in endpoints:
        if ep["method"] not in ("POST", "PUT", "DELETE", "PATCH"):
            continue
        key = (ep["file"], ep["method"], ep["route"])
        if key in PUBLIC:
            continue
        if not ep["permissions"] and not ep["superadmin"]:
            weak.append(key)
            print(f"  FAIL  any-admin write: {ep['file']} {ep['method']} {ep['route']}")
    if not weak:
        print("  PASS  every write is permission-gated or superadmin-only")
    failures.extend(weak)

    print("\n3. Reads are permission-gated unless explicitly allow-listed:")
    stray = []
    for ep in endpoints:
        if ep["method"] != "GET":
            continue
        key = (ep["file"], ep["method"], ep["route"])
        if ep["permissions"] or ep["superadmin"] or key in ANY_ADMIN_READS:
            continue
        stray.append(key)
        print(f"  FAIL  ungated read: {ep['file']} GET {ep['route']}")
    if not stray:
        print(f"  PASS  all reads gated, {len(ANY_ADMIN_READS)} allow-listed")
    failures.extend(stray)

    print("\n4. Catalogue permissions are actually enforced:")
    catalogue = set(re.findall(
        r'Permission\("([a-z_]+:[a-z_]+)"',
        (REPO_ROOT / "app" / "services" / "permissions.py").read_text(),
    ))
    enforced = {p for ep in endpoints for p in ep["permissions"]}
    # These are gated SUPERADMIN-ONLY, which is stricter than the
    # permission. Documented in permissions.py; relaxing them to
    # permission-based would weaken them.
    known_superadmin_only = {"admin_users:view", "admin_users:write", "platform_settings:write"}
    # Not yet implemented anywhere.
    known_unimplemented = {"security:remediate"}
    orphaned = catalogue - enforced - known_superadmin_only - known_unimplemented
    if orphaned:
        for perm in sorted(orphaned):
            print(f"  FAIL  '{perm}' is offered in the role editor but enforced nowhere")
        failures.extend(sorted(orphaned))
    else:
        print(f"  PASS  {len(enforced)} enforced, "
              f"{len(known_superadmin_only)} stricter-than-permission, "
              f"{len(known_unimplemented)} unimplemented and documented")

    print("\n" + "=" * 72)
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        return 1
    print("ALL RBAC COVERAGE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
