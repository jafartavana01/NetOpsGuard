"""Real PostgreSQL only; isolated schema, explicit skip without disposable DSN."""
import os
import unittest
import uuid
from sqlalchemy import create_engine, inspect
from test_retention import RetentionTests
from app.ncm_history_migration import migrate, TABLES

@unittest.skipUnless(os.environ.get('F03_POSTGRES_DSN'), 'Requires disposable PostgreSQL F03_POSTGRES_DSN')
class PostgreSQLRetentionTests(RetentionTests):
    def make_engine(self):
        url=os.environ['F03_POSTGRES_DSN'];admin=create_engine(url)
        if admin.dialect.name!='postgresql':raise RuntimeError('Actual PostgreSQL required')
        schema='retention_'+uuid.uuid4().hex
        with admin.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
        def cleanup():
            with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
            admin.dispose()
        self.addCleanup(cleanup)
        return create_engine(url,connect_args={'options':'-csearch_path='+schema})
    def test_legacy_cascades_migrated_without_losing_archives(self):
        self.archive();self.db.close()
        with self.engine.begin() as c:
            for table in TABLES:c.exec_driver_sql(f'ALTER TABLE {table} ADD CONSTRAINT legacy_device FOREIGN KEY (device_id) REFERENCES network_devices(id) ON DELETE CASCADE')
        migrate(self.engine);migrate(self.engine)
        with self.engine.begin() as c:
            c.exec_driver_sql('DELETE FROM network_devices')
            for table in TABLES:
                self.assertEqual(c.exec_driver_sql('SELECT count(*) FROM '+table).scalar(),1)
                self.assertFalse(any(f['referred_table']=='network_devices' for f in inspect(c).get_foreign_keys(table)))

if __name__=='__main__':
    names=[n for n in RetentionTests.__dict__ if n.startswith('test_')]+['test_legacy_cascades_migrated_without_losing_archives']
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PostgreSQLRetentionTests(n) for n in names)).wasSuccessful())
