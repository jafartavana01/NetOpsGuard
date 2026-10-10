"""GUI-01 preservation and template contracts; no production database required."""
import json,re,unittest
from html.parser import HTMLParser
from pathlib import Path
from preview import ROOT,ENV,render,modules
from app.modules.sidebar import build_sidebar_sections
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a' and 'nav-item' in a.get('class','').split():self.links.append(a['href'])
class GUIContracts(unittest.TestCase):
 def test_every_server_filtered_destination_preserved_once(self):
  for admin in (False,True):
   home,sections=build_sidebar_sections(modules(),is_superadmin=admin)
   expected=[home.path]+[i.path for section in sections for i in section.items]
   parser=Links();parser.feed(render('/dashboard',admin))
   self.assertCountEqual(parser.links,expected);self.assertEqual(len(parser.links),len(set(parser.links)))
 def test_superadmin_visibility_preserved(self):
  parser=Links();parser.feed(render('/dashboard',False))
  self.assertNotIn('/platform/admin-users',parser.links);self.assertIn('/tacacs/groups',parser.links)
 def test_license_visibility_preserved(self):
  home,sections=build_sidebar_sections(modules(),is_superadmin=False,licensed_module_keys=set())
  parser=Links();parser.feed(render('/dashboard',False,set()))
  self.assertCountEqual(parser.links,[home.path]+[i.path for section in sections for i in section.items])
 def test_all_templates_compile(self):
  for name in ENV.list_templates():ENV.get_template(name)
 def test_authority_choices_unchanged(self):
  s=(ROOT/'app/templates/groups.html').read_text()
  self.assertIn("'EXTERNAL' : 'LEGACY'",s)
  self.assertNotRegex(s,r'<option[^>]*value="(?:LOCAL|HYBRID)"')
 def test_shell_blocks_invalid_candidate(self):
  s=(ROOT/'app/templates/app_shell.html').read_text()
  self.assertEqual(s.count('data.applicable === false'),2)
  self.assertIn('d.code',s);self.assertIn("confirmBtn.hidden = true",s)
 def test_component_text_is_not_raw_html(self):
  s=(ROOT/'app/static/js/gui-components.js').read_text()
  self.assertIn('heading.textContent = title',s);self.assertNotIn('.innerHTML',s)
 def test_navigation_uses_only_rendered_server_entries(self):
  s=(ROOT/'app/templates/partials/gui_navigation.html').read_text()
  self.assertIn('for item in nav_state.items if item.path == path',s)
  self.assertIn('if item.path not in nav_state.mapped',s)
 def test_token_families_and_legacy_aliases(self):
  s=(ROOT/'app/static/css/gui-v2/tokens.css').read_text()
  for token in ('bg-app','bg-sidebar','bg-surface','bg-surface-raised','bg-input','bg-hover','bg-selected','border-subtle','border-default','border-strong','text-primary','text-secondary','text-muted','text-disabled','accent-primary','success','success-bg','info','info-bg','warning','warning-bg','danger','danger-bg','font-ui','font-mono','radius-sm','radius-md','radius-lg'):
   self.assertIn('--'+token+':',s)
 def test_core_text_contrast(self):
  s=(ROOT/'app/static/css/gui-v2/tokens.css').read_text();colors=dict(re.findall(r'--([\w-]+):(#\w{6})',s))
  def lum(h):
   rgb=[int(h[i:i+2],16)/255 for i in (1,3,5)];rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
   return sum(a*b for a,b in zip(rgb,[.2126,.7152,.0722]))
  for foreground,background in [('text-primary','bg-surface'),('text-secondary','bg-surface'),('text-muted','bg-surface'),('success','success-bg'),('info','info-bg'),('warning','warning-bg'),('danger','danger-bg')]:
   a,b=sorted([lum(colors[foreground]),lum(colors[background])]);self.assertGreaterEqual((b+.05)/(a+.05),4.5,(foreground,background))
if __name__=='__main__':unittest.main(verbosity=2)
