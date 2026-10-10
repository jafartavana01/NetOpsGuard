"""Actual mutation orchestration with mocked helper stages, NOT DB rollback proof."""
import sys,unittest,uuid
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from contextlib import ExitStack
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.api import routes_policies as api,routes_policy_conditions as trees
from app.schemas.policy import PolicyCreate,PolicyUpdate
from test_atomic_policy import payload

class AtomicBoundaryTests(unittest.TestCase):
    def execute(self,fail=None,editing=False):
        db=MagicMock();q=db.query.return_value;q.filter.return_value=q;q.with_for_update.return_value=q
        q.first.return_value=api.Policy(id=uuid.uuid4(),name='old',priority=2)
        events=[];response=object()
        def stage(name,result=None):
            def call(*a,**kw):
                self.assertFalse(db.commit.called,'commit preceded '+name)
                events.append(name)
                if name==fail:raise RuntimeError(name)
                return result
            return call
        def flush():
            stage('flush')()
            for call in db.add.call_args_list:
                if isinstance(call.args[0],api.Policy) and call.args[0].id is None:call.args[0].id=uuid.uuid4()
        db.flush.side_effect=flush
        if fail=='commit':db.commit.side_effect=RuntimeError('commit')
        q.delete.side_effect=stage('remove_tree')
        with ExitStack() as stack:
            for obj,name,replacement in (
                (api,'_resolve_conditions',stage('references',(None,None,None))),
                (api,'_resolve_manual_command_set',stage('manual')),
                (api,'_make_room_for_priority',stage('priority')),
                (api,'_replace_command_sets',stage('associations',[])),
                (trees,'_build_tree',stage('tree')),
                (api.config_compiler,'_scope_inventory',stage('inventory')),
                (api.policy_scope,'resolve_scope',stage('validate',NS(deployable=True))),
                (api.policy_versioning,'record_version',stage('history')),
                (api,'policy_to_out',stage('response',response))):stack.enter_context(patch.object(obj,name,side_effect=replacement))
            request=(PolicyUpdate if editing else PolicyCreate)(**payload(scope_mode='tree',condition_tree={'logical_operator':'AND','conditions':[]}))
            if fail:
                with self.assertRaises(RuntimeError):api._mutate_policy(db,request,NS(username='reviewer'),policy_id=str(uuid.uuid4()) if editing else None)
                db.rollback.assert_called_once()
                if fail!='commit':db.commit.assert_not_called()
            else:
                self.assertIs(api._mutate_policy(db,request,NS(username='reviewer'),policy_id=str(uuid.uuid4()) if editing else None),response)
                db.commit.assert_called_once();db.rollback.assert_not_called()
                self.assertEqual(events[-1],'response')
    def test_create_single_commit_after_all_stages(self):self.execute()
    def test_edit_single_commit_after_all_stages(self):self.execute(editing=True)
    def test_all_create_faults_rollback(self):
        for stage in ('references','manual','priority','flush','associations','remove_tree','tree','inventory','validate','history','response','commit'):
            with self.subTest(stage=stage):self.execute(fail=stage)
    def test_all_edit_faults_rollback(self):
        for stage in ('references','manual','priority','flush','associations','remove_tree','tree','inventory','validate','history','response','commit'):
            with self.subTest(stage=stage):self.execute(fail=stage,editing=True)
