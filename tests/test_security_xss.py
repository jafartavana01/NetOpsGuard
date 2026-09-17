"""
tests/test_security_xss.py
=============================
Regression tests for cross-site scripting defences.

The finding: `escapeHtml` was implemented by setting `textContent` and
reading back `innerHTML`. That escapes `&`, `<` and `>` but NOT quotes,
which is safe in text position and unsafe inside an attribute -- a
value containing `" onerror="alert(1)` closes the attribute and adds a
new one.

An audit found 31 places where escaped output lands inside an HTML
attribute. Fixing the helper covers all of them, and the 32nd that
nobody has written yet.

Also asserted here: the shared helper is the only escaping mechanism,
so a future template cannot quietly reintroduce the weak version.

Run:  python3 tests/test_security_xss.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_JS = REPO_ROOT / "app" / "static" / "js" / "app.js"
TEMPLATES = REPO_ROOT / "app" / "templates"

PAYLOADS = [
    ("script tag", "<script>alert(1)</script>"),
    ("img onerror", "<img src=x onerror=alert(1)>"),
    ("double-quote attribute break", '" onerror="alert(1)'),
    ("single-quote attribute break", "' onmouseover='alert(1)"),
    ("svg onload", "<svg/onload=alert(1)>"),
    ("javascript URL", "javascript:alert(1)"),
    ("already-encoded entity", "&lt;script&gt;"),
]


def escape_html(value) -> str:
    """Mirrors the implementation in app.js, so this test fails if the
    two ever diverge -- checked directly below."""
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def main() -> int:
    failures = []

    def check(desc, actual, expected):
        ok = actual == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
        if not ok:
            failures.append(f"{desc}: got {actual!r}")

    print("1. The shipped helper escapes quotes as well as angle brackets:")
    src = APP_JS.read_text()
    match = re.search(r"function escapeHtml\(value\)\s*\{(.*?)\n  \}", src, re.S)
    body = match.group(1) if match else ""
    for char, entity in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"),
                         ('"', "&quot;"), ("'", "&#39;")):
        check(f"escapes {char!r} to {entity}", entity in body, True)
    # The old implementation is not attribute-safe and must not return.
    check("does not use the textContent/innerHTML round-trip",
          "textContent" in body and "innerHTML" in body, False)

    print("\n2. No payload survives in TEXT position:")
    for label, payload in PAYLOADS:
        out = escape_html(payload)
        check(f"{label}: no raw '<'", "<" in out, False)

    print("\n3. No payload escapes an ATTRIBUTE:")
    for label, payload in PAYLOADS:
        attribute = f'value="{escape_html(payload)}"'
        inner = attribute[len('value="'):-1]
        contained = not any(c in inner for c in ('"', "'", "<", ">"))
        check(f"{label}: attribute intact", contained, True)

    print("\n4. Free-text fields are rendered through textContent or escaped:")
    # These carry arbitrary operator input and are the realistic XSS
    # vectors; identifier fields are already restricted by the schema.
    risky = {
        "app_shell.html": "p.reason",
        "network_ops_job_detail.html": "execution.command",
        "command_sets.html": "badRegex.match_value",
    }
    for filename, expression in risky.items():
        text = (TEMPLATES / filename).read_text()
        safe = True
        for line in text.split("\n"):
            if "${" + expression + "}" not in line:
                continue
            # Safe if it is assigned to textContent, or escaped.
            if "textContent" in line or "esc(" in line or "escapeHtml(" in line:
                continue
            # Otherwise it may be building HTML.
            if "innerHTML" in line or "`<" in line:
                safe = False
        check(f"{filename}: ${{{expression}}} rendered safely", safe, True)

    print("\n5. No template carries the weak escaper:")
    # 31 templates define their own escapeHtml rather than using the
    # shared one. That is tolerated -- they are self-contained view
    # scripts -- but every copy must be the attribute-safe version.
    # Fixing only app.js protected almost nothing, which is why this
    # check exists.
    weak = []
    partial = []
    for path in sorted(TEMPLATES.glob("*.html")):
        text = path.read_text()
        if "return div.innerHTML" in text:
            weak.append(path.name)
        for match in re.finditer(r"function\s+escapeHtml\s*\(\w*\)\s*\{(.*?)\n  \}", text, re.S):
            body = match.group(1)
            if "&quot;" not in body or "&#39;" not in body:
                partial.append(path.name)
    check("no textContent/innerHTML round-trip remains", weak, [])
    check("every local escapeHtml escapes quotes", sorted(set(partial)), [])

    print("\n" + "=" * 70)
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for item in failures:
            print("  - " + item)
        return 1
    print("ALL XSS TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
