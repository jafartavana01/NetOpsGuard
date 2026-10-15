"""Daily wall-clock occurrences. NULL zone is explicitly legacy UTC.

Fall-back: first occurrence only. Spring-forward: skip nonexistent local dates.
Never depend on the host timezone or add 24h to a timezone-aware occurrence.
"""
from datetime import datetime, timedelta, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


def validate_zone(value):
    if value is None:
        return None
    if not isinstance(value, str) or value not in available_timezones():
        raise ValueError("Choose a valid IANA timezone.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("Timezone data is unavailable. Install timezone data before saving.") from None
    return value


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def occurrence(day, clock, zone=None):
    if not isinstance(clock, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", clock):
        raise ValueError("Invalid daily time; use HH:MM.")
    validate_zone(zone)
    hour, minute = map(int, clock.split(":"))
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(zone or "UTC"), fold=0)
    instant = local.astimezone(timezone.utc)
    if instant.astimezone(local.tzinfo).replace(tzinfo=None) != local.replace(tzinfo=None):
        return None
    return instant


def due_slot(clock, now, zone=None):
    validate_zone(zone)
    now = utc(now)
    day = now.astimezone(ZoneInfo(zone or "UTC")).date()
    for offset in range(8):
        slot = occurrence(day - timedelta(days=offset), clock, zone)
        if slot is not None and slot <= now:
            return slot
    raise ValueError("No valid daily occurrence found.")


def next_slot(clock, after, zone=None):
    validate_zone(zone)
    after = utc(after)
    day = after.astimezone(ZoneInfo(zone or "UTC")).date()
    for offset in range(8):
        slot = occurrence(day + timedelta(days=offset), clock, zone)
        if slot is not None and slot > after:
            return slot
    raise ValueError("No valid daily occurrence found.")
