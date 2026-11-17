"""Expected-red regressions; fixtures explicit and synthetic, no native behavior asserted."""
import sys,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'));tempfile.tempdir=str(ROOT/'tmp')
from tools.setup import taped_light_probe as p,probe_runtime as rt
from tools.audit import taped_light_report as r
from tests.unit import test_taped_light_probe as pf,test_taped_light_report as f

class Remaining(unittest.TestCase):
 def test_a_slot_omitted_by_the_per_proxy_cap_stays_pending(self):
  types=pf.proxy_types();types['AK74']['proxies']=(pf.LIGHT_UNIVERSAL_PROXY,)
  cfg=pf.proxy_config();cfg['CfgNonAIVehicles Proxyweaponlight_universal']['inventorySlot']=['unrelated%d'%i for i in range(8)]+['weaponFlashlight']
  world=pf.World(types=types,config=cfg);pf.run_hook(world,slots=pf._NoSelectionSlots)
  report=r.build_report(pf.classification(),pf.observations_of(world))
  slot=next(h for h in report['hosts'] if h['class']=='AK74')['lights']['UniversalLight']['slots']['weaponFlashlight']
  self.assertEqual('pending',slot['verdict'],slot)
 def test_conflicting_readbacks_of_one_proxy_cannot_qualify(self):
  entries=[f.proxy(),dict(f.proxy(),cfg_exists=False,model='',inventory_slots=[])]
  row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=entries)
  report=r.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
  self.assertEqual('pending',report['hosts'][0]['lights']['UniversalLight']['verdict'])
 def test_non_numeric_proxy_instance_suffix_cannot_qualify(self):
  row=f.row('AK74','slot_host',f.gun_slots(weapon_model=False),f.good_gun_lights(),proxies=[f.proxy(number='garbage')])
  report=r.build_report(f.classification([f.host('AK74','slot_host')]),f.observations([row]))
  self.assertEqual('pending',report['hosts'][0]['lights']['UniversalLight']['verdict'])
 def test_a_ref_returning_method_cannot_hide_duplicate_locals_at_the_stager(self):
  real=p.render_hook
  method='    ref array<string> HCReview()\n    {\n        int sample = 0;\n        int sample = 1;\n        return null;\n    }\n'
  def render(*a,**kw):
   text=real(*a,**kw).decode();i=text.rfind('}')
   return (text[:i]+method+text[i:]).encode()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=pf.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
   with mock.patch.object(p,'render_hook',side_effect=render):
    with self.assertRaises(ValueError):
     plan=p.stage(source,dest,pf.classification(),battleye_sha256=pf.SYNTH_BE_SHA,_wsl_parent=root)
     print('REF_RETURN_BYPASS',dict(status=plan['status'],plan_exists=(dest/p.PLAN_NAME).exists(),extra_method_lint=rt.lint_hook(method,explicit_numbers=True)))

if __name__=='__main__':unittest.main(verbosity=2)
