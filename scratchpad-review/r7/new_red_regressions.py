"""Expected-red behavioral assertions for independently reproduced remaining gaps."""
import sys,tempfile,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'));tempfile.tempdir=str(ROOT/'tmp')
from tools.setup import taped_light_probe as p,probe_runtime as rt,diagnostic_mission as dm
from tools.audit import taped_light_report as report
from tests.unit import test_taped_light_report as f,test_taped_light_probe as pf
from contextlib import ExitStack

class RemainingRegressions(unittest.TestCase):
    def test_complexity_rule_applies_to_inline_method_braces(self):
        hook='class HCCheck : CustomMission\n{\n    void F() {\n        string row = '+' + '.join(['"x"']*28)+';\n    }\n}\n'
        self.assertEqual(27,rt.max_statement_plus(hook))
        self.assertTrue(any('Formula too complex' in s for s in rt.lint_hook(hook)))
    def test_numeric_rule_checks_compound_concatenation(self):
        hook='class HCCheck : CustomMission\n{\n    void F(int count)\n    {\n        string row = "n=";\n        row += count;\n    }\n}\n'
        self.assertTrue(any('bare numeric' in s for s in rt.lint_hook(hook,explicit_numbers=True)))
    def test_control_found_type_contradiction_cannot_qualify_host(self):
        c=f.classification([f.host('AK74','slot_host')]);o=f.observations([f.row('AK74','slot_host',f.gun_slots(),f.good_gun_lights())])
        o['hosts'][0]['lights'][0]['per_slot'][2]['found_type']='Flashlight'
        self.assertEqual('pending',report.build_report(c,o)['hosts'][0]['verdict'])
    def test_final_inventory_checks_that_opened_directories_still_occupy_their_names(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=pf.make_source_runtime(root/'vanilla');dest=root/'taped-light-test'
            real_launch=rt.launcher_problems;real_walk=dm.walk_plain;real_child=dm._open_child_dir
            state={'launch':False,'walk':False,'done':False}
            def launch(*a,**kw):
                state['launch']=True
                return real_launch(*a,**kw)
            def walk(*a,**kw):
                state['walk']=True
                try:return real_walk(*a,**kw)
                finally:state['walk']=False
            def child(fd,name):
                descriptor=real_child(fd,name)
                if state['launch'] and state['walk'] and name=='db' and not state['done']:
                    state['done']=True
                    target=dest/'mpmissions/dayzOffline.chernarusplus/db';outside=root/'moved-db'
                    target.rename(outside);target.symlink_to(outside,target_is_directory=True)
                return descriptor
            with mock.patch.object(rt,'launcher_problems',side_effect=launch),mock.patch.object(dm,'walk_plain',side_effect=walk),mock.patch.object(dm,'_open_child_dir',side_effect=child):
                with self.assertRaises(ValueError):
                    p.stage(source,dest,pf.classification(),battleye_sha256=pf.SYNTH_BE_SHA,_wsl_parent=root)

if __name__=='__main__':unittest.main(verbosity=2)
