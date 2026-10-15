"""Calendar-aware daily backups with UTC checkpoints and cross-process ownership.

Catch up the most recent due occurrence only. Failed/interrupted occurrences
are not automatically replayed; Run Now is an explicit retry. Locks survive
commits, and the OS/database releases them after process death.
"""
from __future__ import annotations
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..database import get_sessionmaker
from ..models.ncm import NcmBackupSchedule, NcmScheduleState, NcmBackupJob
from . import device_credentials, ncm_backup, ncm_lock

logger = logging.getLogger(__name__)
_POLL_INTERVAL_SECONDS = 30


from .schedule_time import utc, due_slot, next_slot


def should_run_now(daily_run_time, last_run_at, now):
    try:
        slot = due_slot(daily_run_time, now)
    except ValueError:
        return False
    return last_run_at is None or utc(last_run_at) < slot


def _split_ids(raw):
    return [uuid.UUID(item.strip()) for item in (raw or '').split(',') if item.strip()]


def next_due(schedule, state, now=None):
    if not schedule.enabled:
        return None
    now = utc(now or datetime.now(timezone.utc))
    try:
        slot = due_slot(schedule.daily_run_time, now, schedule.schedule_timezone)
    except ValueError:
        return None
    checkpoint = state.last_slot if state else schedule.last_run_at
    if (checkpoint and utc(checkpoint) >= slot) or (schedule.created_at and utc(schedule.created_at) > slot):
        slot = next_slot(schedule.daily_run_time, max(now, utc(checkpoint)) if checkpoint else now, schedule.schedule_timezone)
    return slot


def recover(db, state, now):
    """Called ONLY after obtaining the schedule lock: no live owner remains."""
    if state and state.status == 'running':
        job = db.get(NcmBackupJob, state.job_id) if state.job_id else None
        if job and job.status in ('completed', 'partial_success', 'failed', 'blocked'):
            state.status = job.status
            state.total, state.succeeded, state.failed = job.total_devices, job.succeeded, job.failed
            state.completed_at = job.completed_at or now
            if job.status == 'completed':
                state.succeeded_at = state.completed_at
            state.error = None if job.status == 'completed' else 'Review the previous backup job results.'
        else:
            state.status = 'failed'
            state.error = 'Previous execution was interrupted. Review its job before using Run Now.'
            state.completed_at = now
            if job:
                job.status = 'failed'
                job.completed_at = now
        db.commit()



def run_schedule(db, schedule_id, *, now=None, manual=False, actor=None):
    now = utc(now or datetime.now(timezone.utc))
    with ncm_lock.hold(db, 'schedule:' + str(schedule_id)):
        db.expire_all()
        schedule = db.get(NcmBackupSchedule, schedule_id)
        if not schedule:
            raise HTTPException(404, 'Schedule not found.')
        state = db.get(NcmScheduleState, schedule_id)
        recover(db, state, now)
        if not schedule.enabled:
            if manual:
                raise HTTPException(409, 'Enable the schedule before running it.')
            return state
        invalid_time = None
        try:
            slot = due_slot(schedule.daily_run_time, now, schedule.schedule_timezone)
        except ValueError as exc:
            invalid_time = str(exc)
            slot = now.replace(hour=0, minute=0, second=0, microsecond=0)
        checkpoint = state.last_slot if state else schedule.last_run_at
        if not manual and ((checkpoint and utc(checkpoint) >= slot) or
                           (not invalid_time and schedule.created_at and utc(schedule.created_at) > slot)):
            return state
        # Obtain the writer BEFORE claiming. A busy writer defers this occurrence
        # without recording a false failure or consuming its daily checkpoint.
        with ncm_lock.hold(db, 'backup-writer'):
            if state is None:
                state = NcmScheduleState(schedule_id=schedule.id)
                db.add(state)
            state.last_slot = slot
            state.status = 'running'
            state.attempted_at = now
            state.completed_at = None
            state.error = None
            state.total = state.succeeded = state.failed = 0
            job = NcmBackupJob(display_number=ncm_backup._next_job_number(db), source='scheduled',
                               status='running', started_by=actor or '(scheduled)',
                               schedule_id=schedule.id, schedule_name=schedule.name, total_devices=0)
            db.add(job)
            db.flush()
            state.job_id = job.id
            schedule.last_run_at = now
            db.commit()
            try:
                if invalid_time:
                    raise HTTPException(400, invalid_time)
                username, password = device_credentials.resolve(db)
                devices = ncm_backup.resolve_target_devices(db, _split_ids(schedule.device_ids), _split_ids(schedule.device_group_ids))
                if not devices:
                    raise HTTPException(400, 'No enabled inventory devices match the configured targets. Review devices and groups.')
                types = [x.strip() for x in (schedule.configuration_types or '').split(',') if x.strip()]
                if not types or any(x not in ('running', 'startup') for x in types):
                    raise HTTPException(400, 'Unsupported backup type. Select running and/or startup configuration.')
                job.total_devices = state.total = len(devices)
                db.commit()
                outcome = ncm_backup._run_backup(db, devices=devices, configuration_types=list(dict.fromkeys(types)),
                    ssh_username=username, ssh_password=password, source='scheduled', started_by=job.started_by, job=job)
                state.status = outcome.status
                state.total, state.succeeded, state.failed = outcome.total, outcome.succeeded, outcome.failed
                state.error = 'Some device backups failed; open the backup job for per-device results.' if outcome.failed else None
                if outcome.status == 'completed':
                    state.succeeded_at = job.completed_at or now
                db.commit()
                from .ncm_retention import prune
                try:
                    prune(db, schedule, now)
                except Exception:
                    db.rollback()
                    state.error = 'Backup result recorded, but retention cleanup failed. Review database availability and retention settings.'
            except HTTPException as exc:
                db.rollback()
                state.status = job.status = 'blocked'
                state.error = exc.detail
            except Exception:
                db.rollback()
                state.status = job.status = 'failed'
                state.error = 'Backup execution failed. Review inventory, credentials and database availability before retrying.'
                logger.warning('NCM schedule execution failed (schedule %s).', schedule_id)
            state.completed_at = datetime.now(timezone.utc)
            job.completed_at = state.completed_at
            db.commit()
            return state


def _poll_once(now=None):
    now = utc(now or datetime.now(timezone.utc))
    session_local = get_sessionmaker()
    with session_local() as db:
        ids = [row.id for row in db.query(NcmBackupSchedule).all()]
    for schedule_id in ids:
        try:
            with session_local() as db:
                run_schedule(db, schedule_id, now=now)
        except ncm_lock.Busy:
            continue
        except Exception:
            # No SQL parameters/tracebacks: exceptions may contain secret context.
            logger.warning('NCM schedule could not be evaluated (schedule %s); retrying next poll.', schedule_id)


async def scheduler_loop():
    while True:
        try:
            await asyncio.to_thread(_poll_once)
        except Exception:
            logger.warning('NCM scheduler poll failed; retrying next poll.')
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
