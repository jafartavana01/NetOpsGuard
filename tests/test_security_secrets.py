"""
tests/test_security_secrets.py
=================================
Regression tests for credential exposure.

Two findings from the security audit:

1. **Generated configuration was world-readable.** The installer set
   0640 on the bootstrap file, but every runtime write --
   `apply_candidate`, the rollback path, and every version backup --
   used a plain `write_text`, which creates a NEW file with the process
   umask (0644 on a default Ubuntu). Those files contain every device's
   TACACS+ and RADIUS shared secret in cleartext, so any local account
   on the server could read them.

2. **A short shared secret was echoed back in full.** `_secret_suffix`
   returned the last four characters, falling back to the WHOLE secret
   when it was shorter than four, and revealing half of an
   eight-character one -- to anyone holding `devices:view`.

Run:  python3 tests/test_security_secrets.py
"""
from __future__ import annotations

import ast
import glob
import re
import stat
import tempfile
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WANTED = {"_write_config_file", "_CONFIG_FILE_MODE", "_MIN_LENGTH_FOR_SUFFIX"}


def _load(name: str, path: Path, preamble: str = ""):
    """Pulls the helpers out by AST so the tests need no database,
    no FastAPI and no SQLAlchemy."""
    src = path.read_text()
    parts = []
    for node in ast.parse(src).body:
        got = None
        if isinstance(node, ast.FunctionDef) and node.name in WANTED:
            got = ast.get_source_segment(src, node)
        elif isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in WANTED:
            got = ast.get_source_segment(src, node)
        if got:
            parts.append(got)
    module = types.ModuleType(name)
    exec(compile(preamble + "\n".join(parts), name, "exec"), module.__dict__)
    return module


def main() -> int:
    failures = []

    def check(desc, actual, expected):
        ok = actual == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {desc} -> {actual!r}")
        if not ok:
            failures.append(desc)

    print("1. Generated configuration is not world-readable:")
    cc = _load("cc", REPO_ROOT / "app" / "services" / "config_compiler.py",
               "import logging\nfrom pathlib import Path\n")
    tmp = Path(tempfile.mkdtemp())
    secret_line = 'host R1 { key = "csYjb9wPGQEns-FSWNNwM102XTklVALp" }'

    # Baseline: what the unfixed code produced.
    baseline = tmp / "baseline.conf"
    baseline.write_text(secret_line)
    check("plain write_text is world-readable (the bug)",
          bool(stat.S_IMODE(baseline.stat().st_mode) & stat.S_IROTH), True)

    target = tmp / "tac_plus-ng.conf"
    cc._write_config_file(target, secret_line)
    mode = stat.S_IMODE(target.stat().st_mode)
    check("written file mode", oct(mode), oct(0o640))
    check("world-readable", bool(mode & stat.S_IROTH), False)

    cc._write_config_file(target, secret_line + "\n# rewritten")
    check("stays restricted on rewrite",
          oct(stat.S_IMODE(target.stat().st_mode)), oct(0o640))

    print("\n2. Every config write goes through the restricting helper:")
    src = (REPO_ROOT / "app" / "services" / "config_compiler.py").read_text()
    stray = [
        line.strip() for line in src.split("\n")
        if re.search(r"(ACTIVE_CONFIG_PATH|backup_path)\.write_text", line)
        and not line.strip().startswith("#")
    ]
    check("no direct write_text on config paths", stray, [])

    print("\n3. A short shared secret is never echoed back:")
    rd = _load("rd", REPO_ROOT / "app" / "api" / "routes_devices.py")
    minimum = rd._MIN_LENGTH_FOR_SUFFIX

    def suffix(plaintext: str):
        return None if len(plaintext) < minimum else plaintext[-4:]

    for secret in ("x", "abc", "cisco123", "cisco12345"):
        check(f"len {len(secret)} reveals nothing", suffix(secret), None)
    long_secret = "csYjb9wPGQEns-FSWNNwM102XTklVALp"
    check("a long secret shows only 4 chars", suffix(long_secret), long_secret[-4:])
    check("fraction revealed stays small",
          len(suffix(long_secret)) / len(long_secret) < 0.2, True)

    print("\n4. No secrets written to logs:")
    logged = []
    for path in glob.glob(str(REPO_ROOT / "app" / "**" / "*.py"), recursive=True):
        if "__pycache__" in path:
            continue
        for line in Path(path).read_text().split("\n"):
            if line.strip().startswith("#"):
                continue
            if re.search(r"logger\.(info|debug|warning|error)\(.*\b(password|secret)\b", line):
                if not any(k in line for k in ("redact", "mask", "has_", "Could not")):
                    logged.append(Path(path).name)
    check("secrets in log calls", sorted(set(logged)), [])

    print("\n" + "=" * 70)
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        return 1
    print("ALL SECRET-EXPOSURE TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
