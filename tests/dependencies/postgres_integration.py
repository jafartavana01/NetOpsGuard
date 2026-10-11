"""Opt-in real PostgreSQL model/transaction/concurrency tests in a private schema.

No outer rollback hides real commits. Never runs against SQLite as a substitute.
"""
import os
import unittest
import uuid
from sqlalchemy import create_engine
from test_deletion import DeletionTests


@unittest.skipUnless(os.environ.get('F03_POSTGRES_DSN'), 'Real PostgreSQL unavailable: set disposable F03_POSTGRES_DSN')
class PostgreSQLDeletionTests(DeletionTests):
    def make_engine(self):
        engine=create_engine(os.environ['F03_POSTGRES_DSN'])
        if engine.dialect.name!='postgresql':
            raise RuntimeError('A disposable PostgreSQL DSN is required')
        schema='dependency_'+uuid.uuid4().hex
        with engine.begin() as con:con.exec_driver_sql('CREATE SCHEMA '+schema)
        def drop():
            with engine.begin() as con:con.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
            engine.dispose()
        self.addCleanup(drop)
        return engine.execution_options(schema_translate_map={None:schema})

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQLDeletionTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
