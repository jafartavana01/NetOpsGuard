"""
app.models.security_protection
=================================
Temporary authentication lockouts and the security-event history.

Two tables, deliberately separate (spec section 8):

* `security_lockouts` -- CURRENT state. A row exists only while a
  lockout is active; the sweeper deletes it on expiry.
* `security_events` -- immutable history. Never deleted when a lockout
  expires, so "why was u2 locked out last Tuesday" is still answerable
  after the lockout is long gone.

Scope
-----
A lockout is keyed on (username, device, action). NOT on username
alone: locking u2 out of every device because they fumbled a password
on R1 would turn a typo into an outage, and is exactly what the spec
rules out.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SecurityLockout(Base):
    __tablename__ = "security_lockouts"
    __table_args__ = (
        # The uniqueness constraint IS the concurrency control: two
        # simultaneous requests cannot both create a lockout for the
        # same scope, because the second insert fails. See
        # services.security_protection for how that is used rather than
        # read-then-write, which races.
        UniqueConstraint("username", "device_name", "action", name="uq_lockout_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    #: Stored by NAME, not id. A TACACS+ user may come from Active
    #: Directory and have no row in this database at all, so a foreign
    #: key would silently exclude exactly the users most worth locking.
    username: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    device_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="authentication")

    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    #: Whether the deny rule for this lockout is present in the config
    #: the daemon is actually running. A lockout that has been recorded
    #: but not yet applied is NOT enforced, and the GUI says so rather
    #: than implying protection that is not in place yet.
    enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SecurityEvent(Base):
    """
    Append-only security history.

    Written for lockouts, expiries, manual unlocks and rate-limit
    rejections alike, so one timeline answers "what did the protection
    system do, and why".
    """

    __tablename__ = "security_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # lockout_created | lockout_expired | lockout_cleared |
    # rate_limited | enforcement_failed
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    username: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, default="authentication")
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    attempt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lockout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Who caused it. None means the platform itself (the detector or
    #: the expiry sweep), which is distinct from an administrator
    #: acting deliberately.
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class SecurityProtectionSettings(Base):
    """Singleton policy, following this project's existing settings
    pattern rather than a new configuration mechanism."""

    __tablename__ = "security_protection_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Defaults from the spec. Editable, because the right numbers for
    #: a lab and for a production core are not the same.
    max_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    lockout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    #: How often the detector reads the log and the sweeper expires
    #: lockouts. Also the WORST-CASE lag before a lockout takes effect,
    #: which is why it is surfaced in the GUI rather than buried.
    poll_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
