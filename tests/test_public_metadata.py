"""Public status responses must not disclose raw install or database details."""
import sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services import build_info_service as build
from app.api import routes_system as system
class PublicMetadataTests(unittest.TestCase):
    def test_public_allowlist_preserves_operator_fields(self):
        value={'status':'recorded','commit':'abc','build_profile':'recommended','binary_path':'/private/build',
               'configure_arguments':['private-value'],'future_secret':'fixture-only'}
        with patch.object(build,'get_build_info',return_value=value):
            self.assertEqual(build.get_public_build_info(),{'status':'recorded','commit':'abc','build_profile':'recommended'})
    def test_internal_build_information_unchanged(self):
        value={'binary_path':'/private/build','configure_arguments':['private-value']}
        with patch.object(build,'load_build_info',return_value=value.copy()):
            self.assertEqual(build.get_build_info()['binary_path'],value['binary_path'])
    def test_database_and_service_error_text_not_returned(self):
        db=MagicMock();db.execute.side_effect=RuntimeError('fixture-only-sensitive-db-error')
        with patch.object(system.service_control,'get_status',side_effect=system.service_control.ServiceControlError('fixture-only-private-path')),patch.object(build,'get_public_build_info',return_value={}):
            result=system.system_status(db,SimpleNamespace())
        self.assertEqual(result['database'],'unavailable')
        self.assertNotIn('fixture-only',str(result))
if __name__=='__main__':unittest.main(verbosity=2)
