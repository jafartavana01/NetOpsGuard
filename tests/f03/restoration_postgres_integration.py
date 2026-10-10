"""Opt-in production-model/handler restore transactions on disposable PostgreSQL.

No installed schema claim. Private schema in an outer transaction is rolled back.
Never uses application credentials or calls init_db. Requires F03_POSTGRES_DSN.
"""
import importlib
import os
import pkgutil
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

DSN = os.environ.get('F03_POSTGRES_DSN')

@unittest.skipUnless(DSN, 'POSTGRESQL RESTORATION VERIFICATION NOT EXECUTED: supply disposable F03_POSTGRES_DSN')
class PostgreSQLRestorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        import app.models
        for mod in pkgutil.iter_modules(app.models.__path__): importlib.import_module('app.models.' + mod.name)
        from app.database import Base
        from app.api import routes_policy_versions as api
        from app.models.device import NetworkDevice
        from app.models.policy import Policy
        from app.models.policy_version import PolicyVersion
        cls.engine = create_engine(DSN)
        if cls.engine.dialect.name != 'postgresql': raise RuntimeError('PostgreSQL is required')
        cls.Base, cls.Session, cls.api = Base, Session, api
        cls.Device, cls.Policy, cls.Version = NetworkDevice, Policy, PolicyVersion
    @classmethod
    def tearDownClass(cls): cls.engine.dispose()
    def setUp(self):
        self.connection = self.engine.connect(); self.addCleanup(self.connection.close)
        self.outer = self.connection.begin(); self.addCleanup(self.outer.rollback)
        schema = 'restore_' + uuid.uuid4().hex
        self.connection.exec_driver_sql('CREATE SCHEMA ' + schema)
        self.connection.exec_driver_sql('SET LOCAL search_path TO ' + schema)
        self.Base.metadata.create_all(self.connection)
        self.db = self.Session(self.connection, join_transaction_mode='create_savepoint')
        self.addCleanup(self.db.close)
        self.did, self.pid = uuid.uuid4(), uuid.uuid4()
        self.db.execute(self.Device.__table__.insert().values(id=self.did, name='router', ip_address='192.0.2.10', enabled=True))
        self.policy = self.Policy(id=self.pid, name='scoped', priority=1, condition_device_id=self.did, default_action='deny')
        self.db.add(self.policy); self.db.commit()
        self.admin = SimpleNamespace(username='reviewer')
    def version(self, name):
        import json
        snapshot = dict(name='scoped', description=None, enabled=True, priority=1,
            condition_device_name=name, condition_device_group_name=None, condition_group_name=None,
            command_set_names=[], default_action='deny', default_priv_lvl=1)
        v = self.Version(policy_id=self.pid, version_number=1, snapshot=json.dumps(snapshot))
        self.db.add(v); self.db.commit(); return v
    def restore(self, v): return self.api.restore_policy_version(str(self.pid), str(v.id), self.db, self.admin)
    def test_existing_device_and_version_persistence(self):
        v = self.version('router'); old = v.snapshot
        self.restore(v); self.db.expire_all()
        self.assertEqual(self.db.get(self.Policy, self.pid).condition_device_id, self.did)
        self.assertEqual(self.db.query(self.Version).count(), 2)
        self.assertEqual(self.db.get(self.Version, v.id).snapshot, old)
    def test_missing_device_rejection_no_write(self):
        from fastapi import HTTPException
        v = self.version('retired'); old = v.snapshot
        with self.assertRaises(HTTPException) as caught: self.restore(v)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(self.db.dirty)
        self.db.expire_all()
        self.assertEqual(self.db.get(self.Policy, self.pid).condition_device_id, self.did)
        self.assertEqual(self.db.query(self.Version).count(), 1)
        self.assertEqual(self.db.get(self.Version, v.id).snapshot, old)
    def test_explicit_unrestricted_restores(self):
        self.restore(self.version(None)); self.db.expire_all()
        self.assertIsNone(self.db.get(self.Policy, self.pid).condition_device_id)
        self.assertEqual(self.db.query(self.Version).count(), 2)
    def test_failed_version_write_rolls_back_on_session_close(self):
        v = self.version(None)
        with patch.object(self.api.policy_versioning, 'record_version', side_effect=RuntimeError('injected version failure')):
            with self.assertRaises(RuntimeError): self.restore(v)
        self.db.close()  # production get_db finalizer closes the failed request session
        with self.Session(self.connection, join_transaction_mode='create_savepoint') as fresh:
            self.assertEqual(fresh.get(self.Policy, self.pid).condition_device_id, self.did)
            self.assertEqual(fresh.query(self.Version).count(), 1)

if __name__ == '__main__': unittest.main(verbosity=2)
