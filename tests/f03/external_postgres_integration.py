"""Opt-in real PostgreSQL upgrade tests. Private schema, outer rollback only.

Use only an explicitly supplied disposable F03_POSTGRES_DSN. Tests exercise the
real migration inside a connection savepoint; no production engine/startup.
"""
import os
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace as NS

DSN=os.environ.get('F03_POSTGRES_DSN')

@unittest.skipUnless(DSN,'Requires disposable PostgreSQL: F03_POSTGRES_DSN is not configured')
class ExternalPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from sqlalchemy import create_engine
        from app.group_authority_migration import migrate
        cls.migrate=staticmethod(migrate);cls.engine=create_engine(DSN)
        if cls.engine.dialect.name!='postgresql':raise RuntimeError('Real PostgreSQL required')
    @classmethod
    def tearDownClass(cls):cls.engine.dispose()
    def setUp(self):
        self.c=self.engine.connect();self.addCleanup(self.c.close)
        self.tx=self.c.begin();self.addCleanup(self.tx.rollback)
        schema='f03_external_'+uuid.uuid4().hex
        self.c.exec_driver_sql('CREATE SCHEMA '+schema)
        self.c.exec_driver_sql('SET LOCAL search_path TO '+schema)
        self.c.exec_driver_sql('CREATE TABLE ad_settings(id UUID PRIMARY KEY)')
        self.c.exec_driver_sql('CREATE TABLE tacacs_groups(id UUID PRIMARY KEY, name TEXT, ad_group_name TEXT)')
        self.sid=uuid.uuid4();self.gid=uuid.uuid4()
        self.c.exec_driver_sql('INSERT INTO ad_settings VALUES (%s)',(self.sid,))
        self.c.exec_driver_sql('INSERT INTO tacacs_groups VALUES (%s,%s,%s)',(self.gid,'ops','AAA-ops'))
        @contextmanager
        def begin():
            with self.c.begin_nested():yield self.c
        self.adapter=NS(dialect=self.engine.dialect,begin=begin)
    def test_existing_legacy_restart_and_source_restrict(self):
        from sqlalchemy.exc import IntegrityError
        self.migrate(self.adapter);self.migrate(self.adapter)
        self.assertEqual(self.c.exec_driver_sql('SELECT authority,external_source_id FROM tacacs_groups').one(),('LEGACY',None))
        self.assertEqual(self.c.exec_driver_sql('SELECT count(*) FROM netopsguard_schema_migrations').scalar(),1)
        self.c.exec_driver_sql("UPDATE tacacs_groups SET authority='EXTERNAL',external_source_id=%s",(self.sid,))
        with self.assertRaises(IntegrityError):
            with self.c.begin_nested():self.c.exec_driver_sql('DELETE FROM ad_settings WHERE id=%s',(self.sid,))
        self.assertEqual(self.c.exec_driver_sql('SELECT external_source_id FROM tacacs_groups').scalar(),self.sid)
    def test_invalid_combination_rejected(self):
        from sqlalchemy.exc import IntegrityError
        self.migrate(self.adapter)
        with self.assertRaises(IntegrityError):
            with self.c.begin_nested():self.c.exec_driver_sql("UPDATE tacacs_groups SET authority='EXTERNAL'")
    def test_mid_upgrade_failure_rolls_back_and_can_retry(self):
        from sqlalchemy.exc import ProgrammingError
        self.c.exec_driver_sql('DROP TABLE ad_settings')
        with self.assertRaises(ProgrammingError):self.migrate(self.adapter)
        self.assertIsNone(self.c.exec_driver_sql("SELECT to_regclass('netopsguard_schema_migrations')").scalar())
        self.assertEqual(self.c.exec_driver_sql("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='tacacs_groups' AND column_name='authority'").scalar(),0)
        self.c.exec_driver_sql('CREATE TABLE ad_settings(id UUID PRIMARY KEY)')
        self.migrate(self.adapter)
        self.assertEqual(self.c.exec_driver_sql('SELECT authority FROM tacacs_groups').scalar(),'LEGACY')

if __name__=='__main__':unittest.main(verbosity=2)
