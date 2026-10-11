"""Keep the ten original F03 deletion scenarios on the actual service boundary.

The old AST-only route double cannot execute a delegated transactional service.
These cases now use the real SQLite fixture and actual DELETE handler, with
stronger status/reference preservation assertions. PostgreSQL remains separate.
"""
import importlib
import uuid
from fastapi import HTTPException
from test_deletion import DeletionTests, DeviceGroup, TacacsGroup, TacacsUser, Policy, RadiusPolicy


def assert_deletion_case(test, model, path, fn, field, object_type, mode):
    fixture=DeletionTests()
    try:
        fixture.setUp()
        if model=='NetworkDevice':
            obj=fixture.db.get(importlib.import_module('app.models.device').NetworkDevice,fixture.r1.id)
        elif model=='DeviceGroup':obj=fixture.group
        elif model=='TacacsGroup':
            obj=TacacsGroup(id=uuid.uuid4(),name='ops');fixture.db.add(obj);fixture.db.commit()
        else:
            obj=TacacsUser(id=uuid.uuid4(),username='target',password_hash='fixture');fixture.db.add(obj);fixture.db.commit()
        oid=obj.id
        if mode=='tree':
            policy=fixture.policy();leaf=fixture.tree(policy,kind=object_type,ref=oid);lid=leaf.id
        else:
            policy=fixture.policy(RadiusPolicy if mode=='radius' else Policy,**{field:oid})
        pid=policy.id
        handler=getattr(importlib.import_module(path[:-3].replace('/','.')),fn)
        with test.assertRaises(HTTPException) as error:handler(str(oid),fixture.db,fixture.admin)
        test.assertEqual(error.exception.status_code,409)
        test.assertIsNotNone(fixture.db.get(type(obj),oid),'Handler deleted a referenced object')
        test.assertIsNotNone(fixture.db.get(type(policy),pid),'Handler deleted a dependent policy')
        if mode=='tree':
            from app.models.policy_condition import PolicyCondition
            test.assertEqual(fixture.db.get(PolicyCondition,lid).referenced_object_id,oid)
        else:test.assertEqual(getattr(fixture.db.get(type(policy),pid),field),oid)
    finally:
        fixture.doCleanups()
