"""Expire only this schedule's old snapshots; preserve latest and recovery pins."""
from datetime import timedelta
from ..models.ncm import NcmConfiguration, NcmBackupJob, NcmBackupJobTarget, NcmBaseline, NcmDeployment


def prune(db, schedule, now):
    if not 1 <= schedule.retention_days <= 3650:
        raise ValueError('Invalid retention')
    protected = {r[0] for r in db.query(NcmBaseline.configuration_id).all()}
    for pre, post in db.query(NcmDeployment.pre_configuration_id, NcmDeployment.post_configuration_id).all():
        protected.update((pre, post))
    # Latest per device/type remains a usable drift/deduplication reference.
    latest = set()
    for row in db.query(NcmConfiguration.id, NcmConfiguration.device_id, NcmConfiguration.configuration_type).order_by(NcmConfiguration.version_number.desc()).all():
        key = (row.device_id, row.configuration_type)
        if key not in latest:
            protected.add(row.id)
            latest.add(key)
    old = db.query(NcmConfiguration.id).join(NcmBackupJob, NcmConfiguration.job_id == NcmBackupJob.id).filter(
        NcmBackupJob.schedule_id == schedule.id,
        NcmConfiguration.created_at < now - timedelta(days=schedule.retention_days),
    ).all()
    for row in old:
        if row.id not in protected:
            db.query(NcmBackupJobTarget).filter(NcmBackupJobTarget.configuration_id == row.id).update(
                {'configuration_id': None}, synchronize_session=False)
            db.query(NcmConfiguration).filter(NcmConfiguration.id == row.id).delete(synchronize_session=False)
    db.commit()
