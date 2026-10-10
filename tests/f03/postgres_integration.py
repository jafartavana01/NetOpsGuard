"""OPT-IN real PostgreSQL FK contracts against fresh production-model DDL.

Requires an explicitly supplied disposable PostgreSQL database (F03_POSTGRES_DSN)
and project dependencies. Never calls init_db or the production engine. Creates
only a random private schema inside a transaction and rolls back all DDL/data.
This verifies fresh model-created constraints, NOT constraints in an installed DB.
"""
import importlib
import os
import sys
import unittest
import uuid
from pathlib import Path
from run import SecurityResult

DSN = os.environ.get('F03_POSTGRES_DSN')

@unittest.skipUnless(DSN, 'Requires PostgreSQL integration: set F03_POSTGRES_DSN to a disposable database')
class PostgreSQLScopeFKTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from sqlalchemy import create_engine
        from sqlalchemy.exc import IntegrityError
        from app.database import Base
        for module in ('ad_settings', 'group', 'device_group', 'device', 'user', 'command_set', 'policy',
                       'radius_policy', 'policy_condition_group', 'policy_condition'):
            importlib.import_module('app.models.' + module)
        cls.metadata = Base.metadata
        cls.engine = create_engine(DSN)
        if cls.engine.dialect.name != 'postgresql':
            cls.engine.dispose()
            raise RuntimeError('This suite requires PostgreSQL, not SQLite or a fake engine')
        cls.IntegrityError = IntegrityError
    @classmethod
    def tearDownClass(cls): cls.engine.dispose()
    def setUp(self):
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(self.transaction.rollback)
        # Schema name is generated locally and contains only fixed prefix + UUID hex.
        schema = 'f03_' + uuid.uuid4().hex
        self.connection.exec_driver_sql('CREATE SCHEMA ' + schema)
        self.connection.exec_driver_sql('SET LOCAL search_path TO ' + schema)
        names = ('ad_settings', 'tacacs_groups', 'device_groups', 'network_devices', 'tacacs_users',
                 'command_sets', 'policies', 'radius_policies', 'radius_policy_attributes',
                 'policy_condition_groups', 'policy_conditions')
        self.metadata.create_all(self.connection, tables=[self.metadata.tables[n] for n in names])
    def assert_deletion_protected(self, policy_table, target_table, field):
        from sqlalchemy import select
        target = self.metadata.tables[target_table]
        policy = self.metadata.tables[policy_table]
        target_id, policy_id = uuid.uuid4(), uuid.uuid4()
        values = dict(id=target_id, name='target')
        if target_table == 'network_devices': values['ip_address'] = '192.0.2.10/32'
        # Core inserts isolate FK enforcement from unrelated ORM licensing callbacks.
        self.connection.execute(target.insert().values(**values))
        self.connection.execute(policy.insert().values(id=policy_id, name='scoped', **{field: target_id}))
        savepoint = self.connection.begin_nested()
        blocked = False
        try:
            self.connection.execute(target.delete().where(target.c.id == target_id))
            self.connection.exec_driver_sql('SET CONSTRAINTS ALL IMMEDIATE')
        except self.IntegrityError as exc:
            savepoint.rollback()
            if getattr(exc.orig, 'sqlstate', None) != '23503': raise
            blocked = True
        else:
            savepoint.commit()
        stored = self.connection.execute(select(policy.c[field]).where(policy.c.id == policy_id)).scalar_one()
        self.assertTrue(blocked and stored == target_id,
                        f'Deletion was not blocked; persisted scope is {stored!r}')

for policy_table in ('policies', 'radius_policies'):
    for target, field in (('network_devices', 'condition_device_id'),
                          ('device_groups', 'condition_device_group_id'),
                          ('tacacs_groups', 'condition_group_id')):
        def make(policy_table=policy_table, target=target, field=field):
            @unittest.expectedFailure
            def test(self): self.assert_deletion_protected(policy_table, target, field)
            test.__doc__ = f'Requires PostgreSQL: {policy_table}.{field} must survive protected deletion.'
            return test
        setattr(PostgreSQLScopeFKTests, 'test_' + policy_table + '_' + target, make())

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQLScopeFKTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=SecurityResult).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
