"""
tests/test_security_ssh_hostkey.py
=====================================
Regression tests for SSH host-key verification.

The vulnerability, found during the security audit: all three SSH code
paths used `paramiko.AutoAddPolicy`, which accepts whatever host key
the far end presents, silently, with no record. Anything on the network
path between this server and a switch could impersonate that switch and
capture:

  * the service account's SSH username and password, reused fleet-wide,
  * the TACACS+ shared secret, because provisioning pushes
    `tacacs-server host <ip> key <secret>` over that same session.

With that secret an attacker can forge or decrypt TACACS+ traffic for
the device.

Run:  python3 tests/test_security_ssh_hostkey.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.services import ssh_host_keys as hk  # noqa: E402

SSH_MODULES = [
    REPO_ROOT / "app" / "services" / "ssh_provision.py",
    REPO_ROOT / "app" / "services" / "network_ops_execution.py",
]


class FakeKey:
    def __init__(self, raw: bytes):
        self._raw = raw

    def asbytes(self) -> bytes:
        return self._raw


def main() -> int:
    failures = []

    def check(desc, actual, expected):
        ok = actual == expected
        print(f"  {'PASS' if ok else 'FAIL'}  {desc}")
        if not ok:
            failures.append(desc)

    real = FakeKey(b"the-real-switch-host-key")
    attacker = FakeKey(b"an-impersonating-host-key")
    real_fp = hk.fingerprint(real)

    print("1. Fingerprints are OpenSSH-style and distinguish keys:")
    check("SHA256: prefix", real_fp.startswith("SHA256:"), True)
    check("different keys differ", real_fp != hk.fingerprint(attacker), True)

    print("\n2. First connection learns the key:")
    learned = []
    policy = hk.PinnedHostKeyPolicy(expected=None, on_learn=learned.append, device_label="R1")
    policy.missing_host_key(None, "192.168.44.10", real)
    check("key recorded", learned, [real_fp])

    print("\n3. A later connection with the same key is accepted:")
    try:
        hk.PinnedHostKeyPolicy(expected=real_fp, device_label="R1").missing_host_key(
            None, "192.168.44.10", real)
        check("accepted", True, True)
    except Exception as exc:
        check(f"accepted (raised {exc})", False, True)

    print("\n4. A CHANGED key is refused -- the interception case:")
    try:
        hk.PinnedHostKeyPolicy(expected=real_fp, device_label="R1").missing_host_key(
            None, "192.168.44.10", attacker)
        check("refused", False, True)
    except hk.HostKeyChangedError as exc:
        check("refused with HostKeyChangedError", True, True)
        names_both = real_fp[:20] in str(exc) and hk.fingerprint(attacker)[:20] in str(exc)
        check("message names both fingerprints", names_both, True)

    print("\n5. A storage failure must not break the connection:")
    def explode(_):
        raise RuntimeError("database unavailable")
    try:
        hk.PinnedHostKeyPolicy(expected=None, on_learn=explode,
                               device_label="R2").missing_host_key(None, "10.0.0.1", real)
        check("connection proceeded", True, True)
    except Exception:
        check("connection proceeded", False, True)

    print("\n6. AutoAddPolicy must not reappear in any SSH path:")
    for module in SSH_MODULES:
        src = module.read_text()
        # Only count real usage, not a mention in a comment.
        uses = [
            line for line in src.split("\n")
            if "AutoAddPolicy" in line and not line.strip().startswith("#")
        ]
        check(f"{module.name} free of AutoAddPolicy", uses, [])

    print("\n7. Every SSH entry point accepts the pinning parameters:")
    for module in SSH_MODULES:
        src = module.read_text()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            segment = ast.get_source_segment(src, node) or ""
            if "PinnedHostKeyPolicy" not in segment:
                continue
            args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
            complete = all(p in args for p in ("expected_host_key", "on_host_key_learned"))
            check(f"{node.name}() takes pinning parameters", complete, True)

    print("\n" + "=" * 70)
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for item in failures:
            print("  - " + item)
        return 1
    print("ALL SSH HOST-KEY TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
