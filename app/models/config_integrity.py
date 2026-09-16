"""
app.models.config_integrity
==============================
Baseline hash of the last configuration this platform applied, plus the
current alert state.

One row. `expected_hash` is written only by `record_applied`, which
hashes the content the platform intended to write rather than whatever
happens to be on disk at that moment.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConfigIntegrityState(Base):
    __tablename__ = "config_integrity_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    expected_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alert_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    alert_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- operator settings ------------------------------------------
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)

    #: Whether to STOP tac_plus-ng when tampering is detected.
    #:
    #: Defaults to False, and that default is a judgement rather than an
    #: oversight: stopping the daemon means every device loses AAA. On a
    #: network that fails closed, the safety mechanism would cause a
    #: worse outage than the thing it detected. Alerting loudly while
    #: continuing to serve is the safer default; an operator who would
    #: rather fail closed can say so.
    stop_service_on_tamper: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
