"""Complete policy mutation request contract; production Pydantic models."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from pydantic import ValidationError
from app.schemas.policy import PolicyCreate,PolicyUpdate

def payload(**extra):
    return dict(name='scoped',enabled=True,priority=1,default_priv_lvl=15,
        default_action='deny',requires_manual_approval=False,manual_default_command_set_id=None,
        command_set_ids=[],scope_mode='unrestricted',condition_tree=None)|extra

class AtomicPolicySchemaTests(unittest.TestCase):
    def test_omitted_intent_rejected_for_create_and_edit(self):
        for model in (PolicyCreate,PolicyUpdate):
            p=payload();del p['scope_mode']
            with self.subTest(model=model),self.assertRaises(ValidationError):model(**p)
    def test_explicit_catchall_supported(self):
        for model in (PolicyCreate,PolicyUpdate):self.assertEqual(model(**payload()).scope_mode,'unrestricted')
    def test_restrictions_cannot_hide_in_unrestricted_request(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(condition_device_id='selected'))
    def test_tree_required_when_declared(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(scope_mode='tree'))
    def test_tree_cannot_silently_override_legacy_restriction(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(scope_mode='tree',condition_device_id='selected',condition_tree={'logical_operator':'AND','conditions':[]}))
    def test_legacy_dimensions_must_be_explicit(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(scope_mode='legacy'))
    def test_partial_legacy_supported(self):
        p=PolicyCreate(**payload(scope_mode='legacy',condition_device_id='selected',condition_group_id=None,condition_device_group_id=None))
        self.assertEqual(p.condition_device_id,'selected')
    def test_security_fields_must_be_complete(self):
        for key in ('enabled','priority','default_priv_lvl','default_action','requires_manual_approval','manual_default_command_set_id','command_set_ids'):
            p=payload();del p[key]
            with self.subTest(key=key),self.assertRaises(ValidationError):PolicyUpdate(**p)
    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(scope_typo='device'))
    def test_nested_unknown_conditions_rejected(self):
        with self.assertRaises(ValidationError):PolicyCreate(**payload(scope_mode='tree',condition_tree={'logical_operator':'AND','conditions':[],'scope_typo':'x'}))
