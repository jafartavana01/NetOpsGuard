"""
app.services.ssh_host_keys
=============================
SSH host-key pinning for device connections.

The problem this fixes
----------------------
Every SSH path used `paramiko.AutoAddPolicy`, which accepts whatever
host key the far end presents, silently, with no record. Anything on
the network path between this server and a switch could impersonate
that switch. What it would capture is not trivial:

  * the service account's SSH username and password, which is used
    across the fleet, and
  * the TACACS+ shared secret, because provisioning pushes
    `tacacs-server host <ip> key <secret>` over that very session.

With that secret an attacker can forge or decrypt TACACS+ traffic for
the device. This was the highest-severity finding of the audit.

Why trust-on-first-use rather than strict checking
--------------------------------------------------
Strict verification against a populated `known_hosts` is stronger, and
it would break every existing installation on the first connection,
because no keys have ever been recorded. An upgrade that stops all
device management is not a security improvement anyone will keep.

So: the first connection to a device RECORDS its key fingerprint, and
every later connection VERIFIES against it. A changed key is refused
and reported. That is the signal that matters -- an attacker
intercepting an established device is caught, which is the realistic
threat on a management network.

The honest limit: a device compromised or impersonated at the very
first connection is trusted from then on. That window is stated in the
GUI rather than glossed over, and an administrator can clear a pin to
force re-learning after legitimate hardware replacement.
"""
from __future__ import annotations

import base64
import hashlib
import logging

logger = logging.getLogger(__name__)


class HostKeyChangedError(Exception):
    """Raised when a device presents a different key from the pinned
    one. Deliberately its own type so callers can report it as a
    security event rather than as a generic connection failure."""


def fingerprint(key) -> str:
    """
    OpenSSH-style SHA256 fingerprint, e.g. `SHA256:abc123...`.

    Matches what `ssh-keyscan` and `ssh` itself display, so an
    administrator can compare the value shown here against the device
    console without converting anything.
    """
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class PinnedHostKeyPolicy:
    """
    A paramiko missing-host-key policy that pins on first use.

    `expected` is the fingerprint already recorded for this device, or
    None if it has never been contacted. `on_learn` is called with the
    new fingerprint when there was nothing to compare against, so the
    caller can persist it -- this module does no database work itself,
    which keeps it usable from the SSH worker threads that must not
    hold a session.
    """

    def __init__(self, *, expected: str | None, on_learn=None, device_label: str = ""):
        self.expected = (expected or "").strip() or None
        self.on_learn = on_learn
        self.device_label = device_label or "device"
        self.observed: str | None = None

    def missing_host_key(self, client, hostname, key) -> None:
        observed = fingerprint(key)
        self.observed = observed

        if self.expected is None:
            logger.info(
                "Learned SSH host key for %s (%s): %s",
                self.device_label, hostname, observed,
            )
            if self.on_learn:
                try:
                    self.on_learn(observed)
                except Exception:
                    # Failing to RECORD the key must not fail the
                    # connection: the alternative is that a database
                    # hiccup blocks device management entirely. The
                    # device simply stays unpinned and is learned next
                    # time.
                    logger.exception("Could not record the SSH host key for %s", self.device_label)
            return

        if observed == self.expected:
            return

        # Refuse. This is the case the whole mechanism exists for, so
        # the message names both fingerprints -- an administrator
        # comparing them against the device console is exactly how a
        # legitimate key change gets distinguished from an attack.
        raise HostKeyChangedError(
            f"The SSH host key for {self.device_label} ({hostname}) has CHANGED. "
            f"Expected {self.expected}, got {observed}. "
            f"This is what an interception attempt looks like. If the device was "
            f"legitimately replaced or rebuilt, clear its pinned key on the device page "
            f"and connect again."
        )
