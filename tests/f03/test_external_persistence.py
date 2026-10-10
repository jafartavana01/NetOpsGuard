"""Real Pydantic/SQLAlchemy handler checks on disposable SQLite.

SQLite here verifies API persistence/check constraints only, NOT PostgreSQL FK
or transactional DDL behavior. PG has a separate opt-in suite.
"""
import importlib.util
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

DEPS = bool(importlib.util.find_spec('sqlalchemy') and importlib.util.find_spec('fastapi'))

@unittest.skipUnless(DEPS, 'Install project requirements for real model/API tests')
class ExternalPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from app.api import routes_tacacs_groups as api
        from app.schemas.group import TacacsGroupCreate, TacacsGroupUpdate
        from app.schemas.ad_settings import AdSettingsUpdate
        from app.database import Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        cls.api,cls.Create,cls.Update,cls.AD=api,TacacsGroupCreate,TacacsGroupUpdate,AdSettingsUpdate
        cls.engine=create_engine('sqlite:///:memory:')
        cls.metadata=Base.metadata
        cls.tables=[Base.metadata.tables[n] for n in ('ad_settings','tacacs_groups','tacacs_users','install_events')]
        cls.Session=Session
    @classmethod
    def tearDownClass(cls): cls.engine.dispose()
    def setUp(self):
        self.metadata.create_all(self.engine,tables=self.tables)
        self.db=self.Session(self.engine,autoflush=False)
        self.addCleanup(self.db.close)
        self.backend=self.api.AdSettings(enabled=True,host='ad.example.test',port=636,use_tls=True,
            bind_dn='CN=reader,DC=example,DC=test',bind_password_encrypted='fixture',
            search_base='DC=example,DC=test',group_prefix='AAA-',use_memberof=True)
        self.db.add(self.backend);self.db.commit()
        self.admin=NS(username='reviewer')
    def tearDown(self):
        self.db.close();self.metadata.drop_all(self.engine,tables=self.tables)
    def payload(self,**kw):
        return self.Create(**(dict(name='ops',authority='EXTERNAL',ad_group_name='AAA-ops',external_source_id=self.backend.id)|kw))
    def test_real_create_and_audit(self):
        r=self.api.create_group(self.payload(),self.db,self.admin)
        self.assertEqual(r.authority,'EXTERNAL');self.assertEqual(r.binding_status,'valid')
        self.assertEqual(self.db.query(self.api.TacacsUser).count(),0)
        event=self.db.query(self.api.InstallEvent).one()
        self.assertEqual(event.event_type,'group_authority_create');self.assertIn('reviewer',event.detail)
        self.assertNotIn('fixture',event.detail)
    def test_default_no_inference_from_ad_metadata(self):
        r=self.api.create_group(self.Create(name='ops',ad_group_name='AAA-ops'),self.db,self.admin)
        self.assertEqual(r.authority,'LEGACY');self.assertEqual(r.binding_status,'unclassified')
    def test_client_cannot_declare_valid(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError): self.payload(binding_status='valid')
    def test_unknown_authorities_and_incomplete_fields_rejected(self):
        from pydantic import ValidationError
        for kw in ({'authority':'LOCAL'},{'authority':'HYBRID'},{'external_source_id':None},
                   {'ad_group_name':None},{'authority':'LEGACY'}):
            with self.subTest(kw=kw),self.assertRaises(ValidationError): self.payload(**kw)
    def test_binding_calculated_server_side(self):
        from fastapi import HTTPException
        self.backend.enabled=False;self.db.commit()
        with self.assertRaises(HTTPException) as caught:self.api.create_group(self.payload(),self.db,self.admin)
        self.assertEqual(caught.exception.status_code,422)
        self.assertEqual(caught.exception.detail[0]['code'],'scope.external_backend_disabled')
        self.assertEqual(self.db.query(self.api.TacacsGroup).count(),0)
    def test_old_client_cannot_accidentally_downgrade(self):
        from fastapi import HTTPException
        r=self.api.create_group(self.payload(),self.db,self.admin)
        with self.assertRaises(HTTPException) as caught:
            self.api.update_group(r.id,self.Update(name='ops'),self.db,self.admin)
        self.assertEqual(caught.exception.status_code,409)
        self.assertEqual(self.db.query(self.api.TacacsGroup).one().authority,'EXTERNAL')
    def test_deliberate_binding_update_audited(self):
        r=self.api.create_group(self.payload(),self.db,self.admin)
        payload=self.Update(**self.payload().model_dump())
        with patch.object(self.api,'_referencing_policy_names',return_value={}):
            out=self.api.update_group(r.id,payload,self.db,self.admin)
        self.assertEqual(out.binding_status,'valid')
        self.assertEqual(self.db.query(self.api.InstallEvent).filter_by(event_type='group_authority_update').count(),1)
    def test_source_response_contains_no_secrets(self):
        out=self.api.external_sources(self.db,self.admin)[0]
        self.assertEqual(out['id'],str(self.backend.id))
        self.assertNotIn('bind_password_encrypted',out);self.assertNotIn('bind_dn',out)
    def test_prefix_api_rejects_regex(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):self.AD(group_prefix='AAA.*')
        self.assertEqual(self.AD(group_prefix='AAA-').group_prefix,'AAA-')
    def test_real_model_check_constraint(self):
        from sqlalchemy.exc import IntegrityError
        self.db.add(self.api.TacacsGroup(name='bad',authority='EXTERNAL'))
        with self.assertRaises(IntegrityError):self.db.commit()
        self.db.rollback()
    def test_model_fk_is_restrict_metadata_only(self):
        field=self.api.TacacsGroup.__table__.c.external_source_id
        fk=next(iter(field.foreign_keys))
        self.assertEqual(fk.target_fullname,'ad_settings.id');self.assertEqual(fk.ondelete,'RESTRICT')

@unittest.skipUnless(DEPS, 'Install project requirements for migration control-flow tests')
class MigrationControlFlowTests(unittest.TestCase):
    """Transaction recording double: not a claim of PG transactional DDL success."""
    def setUp(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
        from app.group_authority_migration import migrate
        self.migrate=migrate
    def engine(self,already=False,fail=False):
        class Connection:
            def __init__(self):self.statements=[];self.committed=False;self.rolled_back=False
            def __enter__(self):return self
            def __exit__(self,t,v,tb):self.committed=t is None;self.rolled_back=t is not None
            def execute(self,sql,params=None):
                sql=str(sql);self.statements.append(sql)
                if fail and 'ADD CONSTRAINT' in sql:raise RuntimeError('injected DDL failure')
                return NS(scalar=lambda: already if 'SELECT 1 FROM netopsguard_schema_migrations' in sql else False)
        c=Connection();return NS(dialect=NS(name='postgresql'),begin=lambda:c),c
    def test_legacy_default_only_and_version_last(self):
        engine,c=self.engine();self.migrate(engine)
        self.assertTrue(c.committed);self.assertIn("DEFAULT 'LEGACY'",' '.join(c.statements))
        self.assertTrue(c.statements[-1].startswith('INSERT INTO netopsguard_schema_migrations'))
        self.assertFalse(any(s.startswith('UPDATE ') for s in c.statements))
    def test_restart_no_duplicate_mutation(self):
        engine,c=self.engine(already=True);self.migrate(engine)
        self.assertTrue(c.committed);self.assertFalse(any('ALTER TABLE' in s for s in c.statements))
    def test_failure_rolls_back_not_marked_complete(self):
        engine,c=self.engine(fail=True)
        with self.assertRaises(RuntimeError):self.migrate(engine)
        self.assertTrue(c.rolled_back);self.assertFalse(c.committed)
        self.assertFalse(any(s.startswith('INSERT INTO netopsguard_schema_migrations') for s in c.statements))
    def test_non_pg_not_silently_accepted(self):
        engine,c=self.engine();engine.dialect.name='sqlite'
        with self.assertRaises(RuntimeError):self.migrate(engine)
        self.assertEqual(c.statements,[])
