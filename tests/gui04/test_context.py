"""Presentation contract tests using the real permission dependency, no DB claim."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from app.web import operations_context as context


class PresentationPermissions(unittest.TestCase):
    def resolve(self, *, superadmin=False, role_id='role', permissions=None, missing=False):
        db=MagicMock()
        db.query.return_value.filter.return_value.first.return_value=(None if missing else SimpleNamespace(permissions=permissions or []))
        manager=MagicMock()
        manager.return_value.__enter__.return_value=db
        with patch.object(context,'get_sessionmaker',return_value=manager):
            result=context.operations_permissions(SimpleNamespace(is_superadmin=superadmin,role_id=role_id))
        self.assertFalse(db.commit.called)
        return result

    def test_read_only_has_no_actions(self):
        self.assertEqual(self.resolve(permissions=['ncm:view']),['ncm:view'])

    def test_independent_action_grants(self):
        self.assertEqual(set(self.resolve(permissions=['ncm:view','ncm:backup','network_ops:templates'])),{'ncm:view','ncm:backup','network_ops:templates'})

    def test_missing_role_fail_closed(self):
        self.assertEqual(self.resolve(missing=True),[])

    def test_empty_role_fail_closed(self):
        self.assertEqual(self.resolve(),[])

    def test_superadmin_matches_existing_contract(self):
        self.assertIn('ncm:deploy',self.resolve(superadmin=True))

    def test_no_role_compatibility_unchanged(self):
        self.assertIn('ncm:deploy',self.resolve(role_id=None))

    def test_no_unrelated_grants_exposed(self):
        self.assertNotIn('config:apply',self.resolve(superadmin=True))


if __name__=='__main__':unittest.main(verbosity=2)
