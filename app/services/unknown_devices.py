"""
app.services.unknown_devices
===============================
Finds devices that have contacted this platform but are not in the
inventory.

Where the data comes from
-------------------------
The three tac_plus-ng logs all record the client's address in their
`nas` field. Any address appearing there that does not match a device
in the inventory is a device someone pointed at this server without
adding it here.

This is derived from real traffic, not a scan: it shows what actually
tried to authenticate, which is a stronger signal than what happens to
answer a ping.

**An honest limit, stated because it changes what you should expect to
see.** tac_plus-ng only logs a client it can process. A device with no
matching `host` block may be dropped before anything is written, in
which case it will NOT appear here. This finds:

  * devices that were configured here, then removed from inventory
  * devices covered by a broad `host` block (a subnet rather than a
    /32) that were never added individually
  * devices whose requests were logged before their entry was deleted

It does not promise to find every device that has ever sent a packet.
A capture on TCP 49 and UDP 1812 would do that, and is a separate piece
of work with different privileges.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.device import NetworkDevice
from . import accounting_log


@dataclass
class UnknownDevice:
    ip_address: str
    first_seen: datetime | None
    last_seen: datetime | None
    attempts: int
    #: Usernames observed from this address. Useful for recognising
    #: whose device it is, and capped so one noisy source cannot make
    #: the response enormous.
    users: list = field(default_factory=list)
    #: Which logs it appeared in -- "authentication", "authorization",
    #: "accounting". Tells an operator how far the device got.
    seen_in: list = field(default_factory=list)


def _known_networks(db: Session) -> list:
    """Every inventory address as a network, so a device covered by a
    subnet entry is not reported as unknown."""
    networks = []
    for device in db.query(NetworkDevice).all():
        raw = (device.ip_address or "").strip()
        if not raw:
            continue
        try:
            networks.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            continue
    return networks


#: Dotted-quad addresses. Deliberately loose -- anything that looks
#: like an address is a candidate, and `_is_known` plus the octet check
#: below reject what is not usable.
_IPV4_IN_TEXT = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")


def _addresses_in(text: str) -> list:
    """Every plausible IPv4 address in a line of log text."""
    found = []
    for candidate in _IPV4_IN_TEXT.findall(text or ""):
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if candidate not in found:
            found.append(candidate)
    return found


def _is_known(address: str, networks: list) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        # Not an address at all -- a hostname, or a malformed field.
        # Treated as known so it is not offered for adoption: this
        # feature adds devices BY ADDRESS, and offering something that
        # cannot be used as one would be a dead end.
        return True
    return any(parsed in network for network in networks)


def find_unknown(db: Session, *, limit: int = 2000, max_users: int = 5) -> list:
    networks = _known_networks(db)
    found: dict = {}

    def note(address: str, when, user: str | None, source: str) -> None:
        address = (address or "").strip()
        if not address or _is_known(address, networks):
            return
        entry = found.setdefault(address, UnknownDevice(
            ip_address=address, first_seen=when, last_seen=when, attempts=0,
        ))
        entry.attempts += 1
        if when:
            if entry.first_seen is None or when < entry.first_seen:
                entry.first_seen = when
            if entry.last_seen is None or when > entry.last_seen:
                entry.last_seen = when
        if user and user not in entry.users and len(entry.users) < max_users:
            entry.users.append(user)
        if source not in entry.seen_in:
            entry.seen_in.append(source)

    for record in accounting_log.read_access_records(limit=limit):
        if record.parsed:
            note(record.nas, record.parsed_at, record.user, "authentication")

    for record in accounting_log.read_auth_records(limit=limit, include_logins=True):
        if record.parsed:
            note(record.nas, record.parsed_at, record.user, "authorization")

    for record in accounting_log.read_records(limit=limit):
        if record.parsed:
            note(record.nas, record.parsed_at, record.user, "accounting")

    # Raw sweep, over the SAME lines again.
    #
    # The structured readers above skip any line whose shape they do not
    # recognise -- and a rejected or unknown client is exactly the case
    # most likely to be logged in a different shape (an error string
    # rather than the usual field layout). Depending on the parser
    # therefore made this feature blind to the devices it most needed to
    # find: a real deployment showed switches connecting and being
    # ANSWERED by the daemon while nothing appeared here.
    #
    # So every line is also scanned for addresses, regardless of format.
    # An address that is not in the inventory is worth showing even when
    # the surrounding text means nothing to this parser.
    for source, lines in (
        ("authentication", accounting_log.read_access_lines(limit=limit)),
        ("authorization", accounting_log.read_auth_lines(limit=limit)),
        ("accounting", accounting_log.read_accounting_lines(limit=limit)),
    ):
        for raw in lines:
            when = accounting_log.timestamp_of(raw)
            for address in _addresses_in(raw):
                note(address, when, None, source)

    # Most recently active first: a device that contacted the platform
    # a minute ago is more likely to be the one being set up than one
    # last seen a week ago.
    return sorted(
        found.values(),
        key=lambda d: (d.last_seen is not None, d.last_seen or datetime.min),
        reverse=True,
    )
