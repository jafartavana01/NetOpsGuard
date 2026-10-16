"""Actual PostgreSQL coverage, explicitly skipped without a disposable DSN."""
import os
import unittest
import uuid
from sqlalchemy import create_engine
from test_comparison import PersistenceTests

@unittest.skipUnless(os.environ.get('F03_POSTGRES_DSN'), 'Requires disposable PostgreSQL F03_POSTGRES_DSN')
class PostgreSQLComparisonTests(PersistenceTests):
    def make_engine(self):
        engine=create_engine(os.environ['F03_POSTGRES_DSN'])
        if engine.dialect.name!='postgresql':raise RuntimeError('PostgreSQL required')
        schema='audit_compare_'+uuid.uuid4().hex
        with engine.begin() as con:con.exec_driver_sql('CREATE SCHEMA '+schema)
        def cleanup():
            with engine.begin() as con:con.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
            engine.dispose()
        self.addCleanup(cleanup)
        return engine.execution_options(schema_translate_map={None:schema})

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQLComparisonTests))
    raise SystemExit(not result.wasSuccessful())
