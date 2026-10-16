"""Real SQLite upgrade with legacy cascading FKs, indexes, triggers and rollback."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import unittest
from sqlalchemy import create_engine, event, inspect
from app.ncm_history_migration import migrate, TABLES

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://')
        event.listen(self.engine,'connect',lambda c,r:c.execute('PRAGMA foreign_keys=ON'))
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as c:
            c.exec_driver_sql('CREATE TABLE network_devices (id TEXT PRIMARY KEY)')
            c.exec_driver_sql("INSERT INTO network_devices VALUES ('device-a')")
            for name in TABLES:
                c.exec_driver_sql(f'CREATE TABLE {name} (id TEXT PRIMARY KEY, device_id TEXT NOT NULL REFERENCES network_devices(id) ON DELETE CASCADE, content TEXT NOT NULL)')
                c.exec_driver_sql(f'CREATE INDEX ix_{name}_device ON {name}(device_id)')
                c.exec_driver_sql(f"INSERT INTO {name} VALUES ('row-a','device-a','original evidence')")
            c.exec_driver_sql('CREATE TABLE targets (id TEXT PRIMARY KEY, config_id TEXT REFERENCES ncm_configurations(id) ON DELETE SET NULL)')
            c.exec_driver_sql("INSERT INTO targets VALUES ('target-a','row-a')")
            c.exec_driver_sql('CREATE TABLE insert_log (id TEXT)')
            c.exec_driver_sql('CREATE TRIGGER track_config AFTER INSERT ON ncm_configurations BEGIN INSERT INTO insert_log VALUES (NEW.id); END')
    def test_upgrade_keeps_content_identity_and_inbound_links(self):
        migrate(self.engine)
        with self.engine.begin() as c:
            self.assertEqual(c.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)
            c.exec_driver_sql("DELETE FROM network_devices WHERE id='device-a'")
            for table in TABLES:
                self.assertEqual(c.exec_driver_sql('SELECT device_id,content FROM '+table).one(),('device-a','original evidence'))
            self.assertEqual(c.exec_driver_sql('SELECT config_id FROM targets').scalar(),'row-a')
            self.assertFalse(c.exec_driver_sql('PRAGMA foreign_key_check').all())
    def test_indexes_triggers_preserved(self):
        migrate(self.engine)
        with self.engine.begin() as c:
            for table in TABLES:self.assertEqual(inspect(c).get_indexes(table)[0]['name'],'ix_'+table+'_device')
            c.exec_driver_sql("INSERT INTO ncm_configurations VALUES ('new','device-a','new evidence')")
            self.assertEqual(c.exec_driver_sql('SELECT id FROM insert_log').scalar(),'new')
    def test_repeat_safe_no_copy_overwrite(self):
        migrate(self.engine);migrate(self.engine)
        with self.engine.connect() as c:
            self.assertFalse(any(n.endswith('_retained') for n in inspect(c).get_table_names()))
            self.assertEqual(c.exec_driver_sql('SELECT count(*) FROM ncm_configurations').scalar(),1)
    def test_failed_rebuild_rolls_back_and_restores_fk_mode(self):
        def fail(conn,cursor,statement,parameters,context,many):
            if 'RENAME TO' in statement:raise RuntimeError('injected')
        event.listen(self.engine,'before_cursor_execute',fail)
        with self.assertRaises(RuntimeError):migrate(self.engine)
        event.remove(self.engine,'before_cursor_execute',fail)
        with self.engine.connect() as c:
            self.assertEqual(c.exec_driver_sql('PRAGMA foreign_keys').scalar(),1)
            self.assertEqual(c.exec_driver_sql('SELECT content FROM ncm_configurations').scalar(),'original evidence')
            self.assertEqual(inspect(c).get_foreign_keys('ncm_configurations')[0]['referred_table'],'network_devices')

if __name__=='__main__':unittest.main()
