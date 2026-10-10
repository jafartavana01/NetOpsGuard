"""Real FastAPI parsing/CSRF/response contract; mocked mutation, not DB proof."""
import unittest,uuid
from types import SimpleNamespace as NS
from unittest.mock import MagicMock,patch
from test_atomic_policy import payload

class AtomicHTTPTests(unittest.TestCase):
    def setUp(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api import routes_policies
        from app.api.deps import get_current_admin
        from app.database import get_db
        from app.security import CSRF_COOKIE_NAME
        self.api=routes_policies;self.db=MagicMock()
        app=FastAPI();app.include_router(self.api.router)
        app.dependency_overrides[get_db]=lambda:self.db
        app.dependency_overrides[get_current_admin]=lambda:NS(username='reviewer',is_superadmin=True,role_id=None)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.client.cookies.set(CSRF_COOKIE_NAME,'test-only-csrf')
        self.headers={'X-CSRF-Token':'test-only-csrf'}
    def test_old_split_requests_rejected_before_mutation(self):
        p=payload();del p['scope_mode']
        with patch.object(self.api,'_mutate_policy') as mutate:
            for method,url in [('post','/api/policies'),('put','/api/policies/'+str(uuid.uuid4()))]:
                r=getattr(self.client,method)(url,json=p,headers=self.headers)
                self.assertEqual(r.status_code,422)
            mutate.assert_not_called()
        self.db.commit.assert_not_called()
    def test_complete_tree_forwarded_as_one_operation(self):
        from app.schemas.policy import PolicyOut
        p=payload(scope_mode='tree',condition_tree={'logical_operator':'AND','conditions':[{'object_type':'device','operator':'equal','referenced_object_id':str(uuid.uuid4())}]})
        with patch.object(self.api,'_mutate_policy',return_value=PolicyOut(id=str(uuid.uuid4()),name='scoped',has_condition_tree=True)) as mutate:
            r=self.client.post('/api/policies',json=p,headers=self.headers)
            self.assertEqual(r.status_code,201)
            self.assertTrue(r.json()['has_condition_tree'])
            self.assertEqual(mutate.call_args.args[1].condition_tree.conditions[0].referenced_object_id,p['condition_tree']['conditions'][0]['referenced_object_id'])
            mutate.assert_called_once()
    def test_csrf_still_required(self):
        with patch.object(self.api,'_mutate_policy') as mutate:
            self.assertEqual(self.client.post('/api/policies',json=payload()).status_code,403)
            mutate.assert_not_called()
