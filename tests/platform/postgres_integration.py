"""Explicit opt-in PostgreSQL timezone/claim tests; no SQLite substitution."""
import os
import unittest
import uuid
from sqlalchemy import create_engine
from test_execution import ExecutionTests

@unittest.skipUnless(os.environ.get('F03_POSTGRES_DSN'), 'Requires disposable PostgreSQL F03_POSTGRES_DSN')
class PostgreSQLTimezoneExecution(ExecutionTests):
    def make_engine(self):
        engine=create_engine(os.environ['F03_POSTGRES_DSN'])
        if engine.dialect.name!='postgresql':raise RuntimeError('Actual PostgreSQL required')
        schema='platform_timezone_'+uuid.uuid4().hex
        with engine.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
        def cleanup():
            with engine.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
            engine.dispose()
        self.addCleanup(cleanup)
        return engine.execution_options(schema_translate_map={None:schema})

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PostgreSQLTimezoneExecution))
    raise SystemExit(not r.wasSuccessful())
