"""
tests/test_security_command_pattern.py
=========================================
Regression tests for TACACS+ configuration injection via command
patterns.

The vulnerability, found during a security audit and confirmed by
generating the output:

A command pattern is emitted between slash delimiters --
`if (cmd =~ /<pattern>/) { permit }`. The validator checked only that
the pattern COMPILED as a regular expression. `x/ } permit } ` compiles
fine and produces:

    if (cmd =~ /x/ } permit } /) { deny }

which closes the rule early and turns a deny into a permit-everything.
Anyone able to edit a command set could rewrite arbitrary authorization
rules -- a privilege escalation, not a formatting bug.

Run:  python3 tests/test_security_command_pattern.py
"""
from __future__ import annotations

import ast
import re
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_validator():
    """Extracts the validator from the schema without needing Pydantic."""
    src = (REPO_ROOT / "app" / "schemas" / "command_set.py").read_text()
    body = None
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == "validate_pattern":
            body = ast.get_source_segment(src, node)
            break
    if body is None:
        raise AssertionError("validate_pattern not found in app/schemas/command_set.py")
    body = body.replace('@field_validator("command_pattern")', "").replace("@classmethod", "")
    body = body.replace("def validate_pattern(cls, v: str) -> str:", "def validate_pattern(v):")
    module = types.ModuleType("v")
    exec(compile("import re\n" + body, "v", "exec"), module.__dict__)
    return module.validate_pattern


def _emit(pattern: str, action: str) -> str:
    """Mirrors config_compiler.py's emission, so a test failure shows
    the configuration that would actually have been generated."""
    return f"                if (cmd =~ /{pattern}/) {{ {action} }}"


INJECTION_PAYLOADS = [
    ("delimiter escape to permit-all", "x/ } permit } if cmd =~ /."),
    ("simple delimiter escape", "x/ } permit } "),
    ("brace escape", "show.*} permit {"),
    ("newline into config body", "x\npermit"),
    ("carriage return", "x\rpermit"),
    ("null byte", "x\x00"),
    ("quote injection", 'x" permit'),
    ("backslash escape attempt", "x\\/ }"),
    ("ReDoS: nested plus", "(a+)+$"),
    ("ReDoS: nested star", "(a*)*b"),
    ("empty pattern", "   "),
    # A trailing backslash escapes the closing delimiter.
    ("trailing backslash", "abc\\"),
]

LEGITIMATE_PATTERNS = [
    "^show .*",
    "configure terminal",
    "^show (ip|ipv6) route",
    "no shutdown",
    "reload.*",
    "^copy running-config startup-config$",
    "^show version",
    # The documented workaround for matching an interface path.
    "interface [A-Za-z]+[0-9]+.[0-9]+",
    # Backslash classes are ordinary regex and must keep working -- an
    # earlier version of the fix banned them and broke this.
    "^show(\\s|$)",
    "^copy\\s+running-config",
    "ip route [0-9.]+\\s+[0-9.]+",
]


def main() -> int:
    validate = _load_validator()
    failures = []

    print("1. Injection payloads must all be REJECTED:")
    for label, payload in INJECTION_PAYLOADS:
        try:
            validate(payload)
        except ValueError:
            print(f"  PASS  rejected: {label}")
            continue
        print(f"  FAIL  ACCEPTED: {label}")
        print(f"        would generate: {_emit(payload, 'deny')}")
        failures.append(label)

    print("\n2. Legitimate patterns must all be ACCEPTED:")
    for pattern in LEGITIMATE_PATTERNS:
        try:
            validate(pattern)
            print(f"  PASS  accepted: {pattern}")
        except ValueError as exc:
            print(f"  FAIL  wrongly rejected: {pattern} -> {exc}")
            failures.append(pattern)

    print("\n3. A rejected '/' must explain the working alternative:")
    try:
        validate("interface [A-Za-z]+[0-9/]+")
        print("  FAIL  '/' was accepted")
        failures.append("slash accepted")
    except ValueError as exc:
        helpful = "." in str(exc) and "GigabitEthernet" in str(exc)
        print(f"  {'PASS' if helpful else 'FAIL'}  message names a workaround")
        if not helpful:
            failures.append("unhelpful message")

    print("\n" + "=" * 70)
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("ALL COMMAND PATTERN SECURITY TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
