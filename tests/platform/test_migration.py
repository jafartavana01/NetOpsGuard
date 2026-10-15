import unittest
from sqlalchemy import create_engine,text,inspect
from app.scheduling_migration import migrate
class MigrationTests(unittest.TestCase):
    def test_sqlite_upgrade_repeat_preserves_legacy_and_history(self):
        e=create_engine('sqlite://')
        with e.begin() as c:
            for table in ['ncm_backup_schedules','audit_schedule_settings']:
                c.execute(text(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, daily_run_time VARCHAR(5), history TEXT)'))
                c.execute(text(f"INSERT INTO {table} VALUES (1,'02:00','keep')"))
        migrate(e);migrate(e)
        with e.begin() as c:
            for table in ['ncm_backup_schedules','audit_schedule_settings']:
                row=c.execute(text(f'SELECT daily_run_time,history,schedule_timezone FROM {table}')).one()
                self.assertEqual(tuple(row),('02:00','keep',None))
            c.execute(text("UPDATE ncm_backup_schedules SET schedule_timezone='Asia/Tehran'"))
        migrate(e)
        with e.connect() as c:self.assertEqual(c.execute(text('SELECT schedule_timezone FROM ncm_backup_schedules')).scalar(),'Asia/Tehran')
        e.dispose()
    def test_empty_schema_is_safe(self):
        e=create_engine('sqlite://');migrate(e);e.dispose()
