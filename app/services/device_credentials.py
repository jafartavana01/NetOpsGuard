"""Owner of shared SSH credentials; retains existing encrypted storage in place.

Schedule/history columns remain schedule-owned. No secret copying or re-encryption
on upgrade. A compare-and-swap protects rotations across SQLite/PostgreSQL workers.
"""
import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from .. import security
from ..models.audit_schedule_settings import AuditScheduleSettings

SETTINGS_ID = uuid.UUID('672267c9-bc95-4e69-9805-1fb7d5f26337')
REQUIRED = 'Configure the SSH service account in System → Device Credentials (/platform/device-credentials).'


def get_settings(db):
    return db.query(AuditScheduleSettings).first()


def ensure_settings(db):
    settings = get_settings(db)
    if settings is None:
        try:
            with db.begin_nested():
                settings = AuditScheduleSettings(id=SETTINGS_ID)
                db.add(settings)
                db.flush()
        except IntegrityError:
            settings = get_settings(db)
            if settings is None:
                raise
    return settings


def configured(settings):
    return bool(settings and settings.ssh_username and settings.ssh_password_encrypted)


def revision(settings):
    # Opaque digest of randomized ciphertext, never a digest of the password.
    return hashlib.sha256(json.dumps([str(settings.id), settings.ssh_username,
                                      settings.ssh_password_encrypted]).encode()).hexdigest()


def public_status(settings):
    return dict(username=settings.ssh_username, configured=configured(settings),
                has_password=bool(settings.ssh_password_encrypted), revision=revision(settings))


def replace(db, *, username, password, expected_revision):
    settings = ensure_settings(db)
    if revision(settings) != expected_revision:
        raise HTTPException(409, 'Credentials changed. Reload the saved state before retrying.')
    encrypted = settings.ssh_password_encrypted
    if password:
        encrypted = security.encrypt_secret(password)
    if not encrypted:
        raise HTTPException(400, 'A password is required for the first configuration.')
    changed = db.query(AuditScheduleSettings).filter(
        AuditScheduleSettings.id == settings.id,
        AuditScheduleSettings.ssh_username == settings.ssh_username,
        AuditScheduleSettings.ssh_password_encrypted == settings.ssh_password_encrypted,
    ).update({'ssh_username': username, 'ssh_password_encrypted': encrypted}, synchronize_session=False)
    if changed != 1:
        db.rollback()
        raise HTTPException(409, 'Credentials changed. Reload the saved state before retrying.')
    db.commit()
    db.refresh(settings)
    return public_status(settings)


def resolve(db):
    settings = get_settings(db)
    if not configured(settings):
        raise HTTPException(400, REQUIRED)
    try:
        password = security.decrypt_secret(settings.ssh_password_encrypted)
    except ValueError:
        raise HTTPException(409, 'Saved SSH credentials cannot be decrypted. Replace them in System → Device Credentials.') from None
    return settings.ssh_username, password
