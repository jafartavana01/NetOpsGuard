"""Real PostgreSQL atomic-policy gates. Requires disposable F03_POSTGRES_DSN.

Production model DDL and actual handlers; disposable private schema dropped afterwards.
No substitute database is accepted. Real commits (not outer savepoints), rollback,
deferred constraints and independent-reader visibility are exercised.
"""
import json,unittest,uuid
from unittest.mock import patch
from restoration_postgres_integration import PostgreSQLRestorationTests,DSN
from test_atomic_policy import payload

@unittest.skipUnless(DSN, 'POSTGRESQL ATOMIC POLICY VERIFICATION NOT EXECUTED: disposable F03_POSTGRES_DSN required')
class AtomicPolicyPostgreSQLTests(PostgreSQLRestorationTests):
    # Do not inherit unrelated restoration test cases into this suite.
    test_existing_device_and_version_persistence=None
    test_missing_device_rejection_no_write=None
    test_explicit_unrestricted_restores=None
    test_failed_version_write_rolls_back_on_session_close=None
    def setUp(self):
        from types import SimpleNamespace
        self.schema = 'atomic_' + uuid.uuid4().hex
        with self.engine.begin() as conn:
            conn.exec_driver_sql('CREATE SCHEMA ' + self.schema)
        self.addCleanup(self.drop_schema)
        self.scoped_engine = self.engine.execution_options(schema_translate_map={None:self.schema})
        self.Base.metadata.create_all(self.scoped_engine)
        self.db = self.Session(self.scoped_engine, autoflush=False)
        self.addCleanup(self.db.close)
        self.did, self.pid = uuid.uuid4(), uuid.uuid4()
        self.db.execute(self.Device.__table__.insert().values(id=self.did, name='router', ip_address='192.0.2.10', enabled=True))
        self.policy = self.Policy(id=self.pid, name='scoped', priority=1, condition_device_id=self.did, default_action='deny')
        self.db.add(self.policy); self.db.commit()
        self.admin = SimpleNamespace(username='reviewer')
        from app.api import routes_policies, routes_policy_conditions
        from app.schemas.policy import PolicyCreate,PolicyUpdate
        self.mutation=routes_policies;self.trees=routes_policy_conditions
        self.Create,self.Update=PolicyCreate,PolicyUpdate
    def drop_schema(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA ' + self.schema + ' CASCADE')
    def tree(self):
        return dict(logical_operator='AND',conditions=[dict(object_type='device',operator='equal',referenced_object_id=str(self.did))],child_groups=[])
    def request(self,creating=False,**kw):
        return (self.Create if creating else self.Update)(**payload(name='created' if creating else 'scoped',scope_mode='tree',condition_tree=self.tree(),**kw))
    def invoke(self,creating=False,request=None):
        p=request or self.request(creating)
        return self.mutation.create_policy(p,self.db,self.admin) if creating else self.mutation.update_policy(str(self.pid),p,self.db,self.admin)
    def state(self, db=None):
        # Core reads fresh stored values, independent of ORM identity cache.
        tables=('policies','policy_condition_groups','policy_conditions','policy_command_sets','policy_versions')
        return {n:sorted([dict(x) for x in (db or self.db).execute(self.Base.metadata.tables[n].select()).mappings()],key=lambda x:str(x['id'])) for n in tables}
    def test_create_complete_tree_and_history_single_commit(self):
        result=self.invoke(True)
        from app.models.policy_condition_group import PolicyConditionGroup
        from app.models.policy_version import PolicyVersion
        pid=uuid.UUID(result.id)
        self.assertEqual(self.db.query(PolicyConditionGroup).filter_by(policy_id=pid).count(),1)
        self.assertEqual(self.db.query(PolicyVersion).filter_by(policy_id=pid).count(),1)
        self.assertTrue(result.has_condition_tree)
    def test_edit_tree_legacy_and_unrestricted_transitions(self):
        self.invoke();self.assertTrue(self.mutation.policy_to_out(self.db,self.db.get(self.Policy,self.pid)).has_condition_tree)
        self.invoke(request=self.Update(**payload(scope_mode='legacy',condition_device_id=str(self.did),condition_group_id=None,condition_device_group_id=None)))
        p=self.db.get(self.Policy,self.pid);self.assertEqual(p.condition_device_id,self.did)
        self.assertFalse(self.mutation.policy_to_out(self.db,p).has_condition_tree)
        self.invoke(request=self.Update(**payload()))
        self.assertIsNone(self.db.get(self.Policy,self.pid).condition_device_id)
    def test_create_and_edit_faults_roll_back_every_component(self):
        # Includes priority shifts affecting other policies and history writes.
        self.invoke()  # failures must preserve an existing tree and history, too
        targets=((self.mutation,'_replace_command_sets'),(self.trees,'_build_tree'),
                 (self.mutation.policy_versioning,'record_version'),(self.mutation,'policy_to_out'))
        for creating in (True,False):
            for obj,name in targets:
                before=self.state()
                original=getattr(obj,name)
                def fail_after(*a,**kw):
                    original(*a,**kw)
                    raise RuntimeError('injected after '+name)
                with self.subTest(create=creating,stage=name),patch.object(obj,name,side_effect=fail_after):
                    with self.assertRaises(RuntimeError):self.invoke(creating)
                self.assertEqual(self.state(),before)
    def test_missing_reference_preserves_existing_tree(self):
        from fastapi import HTTPException
        self.invoke();before=self.state()
        bad=self.tree();bad['conditions'][0]['referenced_object_id']=str(uuid.uuid4())
        with self.assertRaises(HTTPException):self.invoke(request=self.Update(**payload(scope_mode='tree',condition_tree=bad)))
        self.assertEqual(self.state(),before)
    def test_missing_command_set_preserves_state(self):
        from fastapi import HTTPException
        before=self.state()
        with self.assertRaises(HTTPException):self.invoke(request=self.Update(**payload(command_set_ids=[str(uuid.uuid4())])))
        self.assertEqual(self.state(),before)
    def test_deferred_commit_failure_rolls_back(self):
        from fastapi import HTTPException
        before=self.state()
        # Real DEFERRABLE INITIALLY DEFERRED priority uniqueness fails at commit.
        with patch.object(self.mutation, '_make_room_for_priority', return_value=None):
            with self.assertRaises(HTTPException):self.invoke(True)
        self.assertEqual(self.state(),before)
    def test_ordered_associations_and_manual_settings_commit_together(self):
        from app.models.command_set import CommandSet
        from app.models.policy_command_set import PolicyCommandSet
        sets=[CommandSet(name='first'),CommandSet(name='second')]
        self.db.add_all(sets);self.db.commit()
        ids=[str(x.id) for x in sets]
        req=self.Update(**payload(scope_mode='tree',condition_tree=self.tree(),
            requires_manual_approval=True,manual_default_command_set_id=ids[0],command_set_ids=ids[::-1]))
        self.invoke(request=req)
        stored=self.db.get(self.Policy,self.pid)
        self.assertTrue(stored.requires_manual_approval)
        self.assertEqual(str(stored.manual_default_command_set_id),ids[0])
        self.assertEqual([str(j.command_set_id) for j in self.db.query(PolicyCommandSet).filter_by(policy_id=self.pid).order_by(PolicyCommandSet.order).all()],ids[::-1])
        before=self.state()
        with patch.object(self.mutation.policy_versioning,'record_version',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):self.invoke(request=self.Update(**payload()))
        self.assertEqual(self.state(),before)
    def test_independent_reader_never_sees_partial_create_or_edit(self):
        for creating in (False,True):
            before=self.state()
            original=self.mutation.policy_versioning.record_version
            def inspect(*args,**kw):
                result=original(*args,**kw)
                self.db.flush()
                with self.Session(self.scoped_engine) as observer:
                    self.assertEqual(self.state(observer),before)
                return result
            with patch.object(self.mutation.policy_versioning,'record_version',side_effect=inspect):
                result=self.invoke(creating)
            with self.Session(self.scoped_engine) as observer:
                self.assertNotEqual(self.state(observer),before)
                self.assertTrue(self.mutation.policy_to_out(observer,observer.get(self.Policy,uuid.UUID(result.id))).has_condition_tree)
    def test_no_mid_operation_commit(self):
        calls=[];real=self.db.commit
        def commit():calls.append('commit');return real()
        original=self.mutation.policy_versioning.record_version
        def version(*a,**kw):
            self.assertEqual(calls,[])
            return original(*a,**kw)
        with patch.object(self.db,'commit',side_effect=commit),patch.object(self.mutation.policy_versioning,'record_version',side_effect=version):self.invoke()
        self.assertEqual(calls,['commit'])

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AtomicPolicyPostgreSQLTests))
    raise SystemExit(0 if result.wasSuccessful() else 1)
