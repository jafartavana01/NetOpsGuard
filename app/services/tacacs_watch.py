"""
app.services.tacacs_watch
============================
Observes TCP connection attempts to the TACACS+ port and records the
source addresses.

Why this exists
---------------
Discovering devices from the tac_plus-ng LOGS only finds clients the
daemon chose to log. A device with no matching `host` block may be
rejected before anything is written, so the devices most worth finding
-- the ones nobody has added yet -- are exactly the ones the log-based
search can miss.

Why not simpler approaches, having measured them
------------------------------------------------
* **Binding port 49** is impossible: tac_plus-ng owns it.
* **Polling `/proc/net/tcp`** needs no privileges at all, and was the
  first thing tried. A real TACACS+ authentication in the reported
  capture lasted 47 ms, so a one-second poll catches roughly 5% of
  them. A device retrying in a loop would eventually appear; a single
  login attempt would almost certainly be missed. Not good enough for a
  feature whose whole purpose is "show me what just tried".
* **Shelling out to tcpdump** works but means parsing another tool's
  text output and keeping a subprocess alive.

So: a raw socket reading IP headers directly. That needs `CAP_NET_RAW`,
which is a real privilege increase and is why this runs as its OWN
small process rather than inside the web application -- see the
`netopsguard-tacacs-watch` unit. The web service keeps no packet
capture ability; it only reads the file this writes.

Protocol note
-------------
**TACACS+ is TCP port 49, not UDP.** RADIUS is the UDP one (1812/1813).
This watches TCP, and optionally the RADIUS UDP ports as well.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

#: Where observations are published for the web application to read.
#: A plain file, written atomically, because the alternative -- giving
#: this privileged process a database connection -- would widen what a
#: fault in it could reach.
STATE_PATH = Path("/var/lib/aaa-platform/observed-clients.json")

TACACS_PORT = 49
RADIUS_PORTS = (1812, 1813)

#: Stop the file growing without bound on a busy network.
MAX_TRACKED = 500

#: Drop an observation nobody has acted on after this long, so a device
#: that was added, or was a one-off mistake, stops being offered
#: forever.
RETAIN_SECONDS = 7 * 24 * 3600


@dataclass
class Observation:
    ip: str
    port: int
    protocol: str            # "tacacs" | "radius"
    first_seen: float
    last_seen: float
    count: int = 1

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "first_seen": datetime.fromtimestamp(self.first_seen, timezone.utc).isoformat(),
            "last_seen": datetime.fromtimestamp(self.last_seen, timezone.utc).isoformat(),
            "count": self.count,
        }


def _parse_ipv4_packet(data: bytes):
    """
    Returns (source_ip, dest_port, protocol_name) for a packet we care
    about, or None.

    Parses only as far as needed: the IP header to get the source and
    protocol, then the first four bytes of the transport header for the
    destination port. No payload is read, and nothing is stored beyond
    an address -- this is a connection observer, not a traffic
    recorder, and reading TACACS+ payload would mean handling
    credentials.
    """
    if len(data) < 20:
        return None

    version_ihl = data[0]
    if (version_ihl >> 4) != 4:
        return None
    header_len = (version_ihl & 0x0F) * 4
    if len(data) < header_len + 4:
        return None

    protocol = data[9]
    source = socket.inet_ntoa(data[12:16])
    dest_port = struct.unpack("!H", data[header_len + 2:header_len + 4])[0]

    if protocol == socket.IPPROTO_TCP and dest_port == TACACS_PORT:
        # Only SYN packets: one record per connection ATTEMPT rather
        # than one per packet, which keeps a single login from looking
        # like a flood.
        if len(data) >= header_len + 14:
            flags = data[header_len + 13]
            syn, ack = flags & 0x02, flags & 0x10
            if not (syn and not ack):
                return None
        return source, dest_port, "tacacs"

    if protocol == socket.IPPROTO_UDP and dest_port in RADIUS_PORTS:
        return source, dest_port, "radius"

    return None


def _prune(seen: dict) -> dict:
    cutoff = time.time() - RETAIN_SECONDS
    kept = {k: v for k, v in seen.items() if v.last_seen >= cutoff}
    if len(kept) > MAX_TRACKED:
        newest = sorted(kept.values(), key=lambda o: o.last_seen, reverse=True)[:MAX_TRACKED]
        kept = {(o.ip, o.protocol): o for o in newest}
    return kept


def _publish(seen: dict) -> None:
    """Writes atomically: a reader must never see a half-written file."""
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "clients": [o.to_dict() for o in sorted(seen.values(), key=lambda o: o.last_seen, reverse=True)],
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2))
    try:
        temp.chmod(0o640)
    except OSError:
        pass
    temp.replace(STATE_PATH)


def read_observed() -> list:
    """Called by the web application. Returns [] on any problem -- a
    missing or malformed file must not break the devices page."""
    try:
        data = json.loads(STATE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    clients = data.get("clients")
    return clients if isinstance(clients, list) else []


def watch(*, publish_every: float = 5.0) -> int:
    """
    Main loop. Requires CAP_NET_RAW.

    Errors are fatal here on purpose: this runs as its own unit, so
    failing loudly gets a restart and a journal entry, whereas limping
    on silently would mean the feature quietly reports nothing while
    appearing to work.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 0)
    except PermissionError:
        print(
            "Raw socket denied. This needs CAP_NET_RAW -- run it as the "
            "netopsguard-tacacs-watch service, which is granted exactly that "
            "and nothing else.",
            file=sys.stderr,
        )
        return 1

    sock.settimeout(1.0)
    seen: dict = {}
    last_publish = 0.0
    print(f"Watching TCP {TACACS_PORT} and UDP {RADIUS_PORTS} for client connections.",
          file=sys.stderr)

    while True:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            data = None
        except OSError as exc:
            print(f"Capture error: {exc}", file=sys.stderr)
            return 1

        if data:
            parsed = _parse_ipv4_packet(data)
            if parsed:
                ip, port, protocol = parsed
                now = time.time()
                key = (ip, protocol)
                existing = seen.get(key)
                if existing:
                    existing.last_seen = now
                    existing.count += 1
                else:
                    seen[key] = Observation(ip=ip, port=port, protocol=protocol,
                                            first_seen=now, last_seen=now)

        now = time.time()
        if now - last_publish >= publish_every:
            seen = _prune(seen)
            try:
                _publish(seen)
            except OSError as exc:
                print(f"Could not write {STATE_PATH}: {exc}", file=sys.stderr)
            last_publish = now


if __name__ == "__main__":
    raise SystemExit(watch())
