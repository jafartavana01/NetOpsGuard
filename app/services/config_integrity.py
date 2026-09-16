"""
app.services.config_integrity
================================
Detects out-of-band edits to the generated tac_plus-ng configuration.

The platform is the only thing that should write
`/opt/aaa-platform/generated/tac_plus-ng.conf`. A hand edit is not
merely untidy: it silently diverges the running AAA policy from what
the GUI, the audit trail and every operator believes is in force, and
the next Apply overwrites it without warning. Either half of that is
bad; together they are how an unexplained authorization outage happens.

How it works
------------
Every Apply records the SHA-256 of exactly what was written, along
with who applied it and when. A background check re-hashes the file on
a schedule and compares.

On a mismatch the platform does NOT silently re-apply. It records the
event, raises an alert the GUI surfaces, and -- if configured to --
stops the daemon.

Why stopping is opt-in and OFF by default
-----------------------------------------
Stopping tac_plus-ng because a file changed means every device loses
AAA. On a network whose switches fall back to local accounts that is a
containable inconvenience; on one that fails closed it is an outage
caused by the safety mechanism rather than by the threat.

That trade-off belongs to the operator, not to this module, so the
default is to alert loudly and keep serving. An administrator who
would rather fail closed can turn it on, and the setting says plainly
what it will do.

What this is and is not
-----------------------
This detects and reports tampering. It does not PREVENT it: anything
running as root can edit the file, stop the checker, or rewrite the
stored hash. That is the same self-hosted reality documented for
licensing, and the honest claim is "you will know", not "it cannot
happen".
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from ..models.config_integrity import ConfigIntegrityState

#: Statuses reported to the GUI.
STATUS_OK = "ok"
STATUS_MODIFIED = "modified"
STATUS_MISSING = "missing"
STATUS_UNKNOWN = "unknown"      # nothing applied yet -- not a fault


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


@dataclass
class IntegrityReport:
    status: str
    detail: str
    expected_hash: str | None = None
    actual_hash: str | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    checked_at: datetime | None = None
    #: True only on the transition into a modified state, so a caller
    #: can act once rather than on every poll.
    newly_detected: bool = False


def _get_or_create(db: Session) -> ConfigIntegrityState:
    row = db.query(ConfigIntegrityState).first()
    if row is None:
        row = ConfigIntegrityState()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def record_applied(db: Session, *, config_path: Path, content: str, applied_by: str | None) -> None:
    """
    Called immediately after the platform writes and applies a config.

    Hashes the CONTENT the platform intended to write rather than
    re-reading the file. Re-reading would hash whatever is on disk at
    that instant, which is precisely the thing being guarded -- a race
    or an interposed write would be baked in as the trusted baseline.
    """
    row = _get_or_create(db)
    row.expected_hash = hash_text(content)
    row.config_path = str(config_path)
    row.applied_by = applied_by
    row.applied_at = datetime.now(timezone.utc)
    row.last_status = STATUS_OK
    row.last_checked_at = row.applied_at
    row.alert_active = False
    row.alert_detail = None
    db.commit()


def check(db: Session, *, config_path: Path | None = None) -> IntegrityReport:
    """Re-hashes the file and compares against the recorded baseline."""
    row = _get_or_create(db)
    now = datetime.now(timezone.utc)

    if not row.expected_hash:
        row.last_status = STATUS_UNKNOWN
        row.last_checked_at = now
        db.commit()
        return IntegrityReport(
            status=STATUS_UNKNOWN, checked_at=now,
            detail="No configuration has been applied from this platform yet, so there is "
                   "nothing to compare against.",
        )

    path = config_path or Path(row.config_path or "")
    actual = hash_file(path) if str(path) else None

    if actual is None:
        was_ok = row.last_status != STATUS_MISSING
        row.last_status = STATUS_MISSING
        row.last_checked_at = now
        row.alert_active = True
        row.alert_detail = f"The configuration file is missing or unreadable: {path}"
        db.commit()
        return IntegrityReport(
            status=STATUS_MISSING, detail=row.alert_detail,
            expected_hash=row.expected_hash, applied_at=row.applied_at,
            applied_by=row.applied_by, checked_at=now, newly_detected=was_ok,
        )

    if actual == row.expected_hash:
        row.last_status = STATUS_OK
        row.last_checked_at = now
        row.alert_active = False
        row.alert_detail = None
        db.commit()
        return IntegrityReport(
            status=STATUS_OK,
            detail="The configuration file matches what this platform last applied.",
            expected_hash=row.expected_hash, actual_hash=actual,
            applied_at=row.applied_at, applied_by=row.applied_by, checked_at=now,
        )

    was_ok = row.last_status != STATUS_MODIFIED
    applied = row.applied_at.isoformat() if row.applied_at else "an earlier time"
    detail = (
        f"The tac_plus-ng configuration has been changed outside this platform. "
        f"It no longer matches what was applied at {applied}"
        + (f" by {row.applied_by}." if row.applied_by else ".")
        + " Re-apply from the platform to restore the known configuration, or investigate "
          "who edited the file."
    )
    row.last_status = STATUS_MODIFIED
    row.last_checked_at = now
    row.alert_active = True
    row.alert_detail = detail
    if was_ok:
        row.detected_at = now
    db.commit()

    return IntegrityReport(
        status=STATUS_MODIFIED, detail=detail,
        expected_hash=row.expected_hash, actual_hash=actual,
        applied_at=row.applied_at, applied_by=row.applied_by,
        checked_at=now, newly_detected=was_ok,
    )
