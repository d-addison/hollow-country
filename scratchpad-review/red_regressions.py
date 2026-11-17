"""Expected-failing review assertions, using explicit synthetic fixtures only."""
import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'head'))
from tests.unit import test_taped_light_report as f
from tools.audit import taped_light_report as r

class ReviewRegressions(unittest.TestCase):
    def baseline(self):
        return f.classification([f.host('AK74','slot_host')]),f.observations([f.row('AK74','slot_host',f.gun_slots(),f.good_gun_lights())])
    def test_partial_run_cannot_qualify_a_pair(self):
        c,o=self.baseline();o['status']='partial'
        result=r.build_report(c,o)
        self.assertEqual('pending',result['hosts'][0]['lights']['UniversalLight']['verdict'])
    def test_wrong_host_identity_cannot_qualify_a_pair(self):
        c,o=self.baseline();o['hosts'][0]['type']='OtherHost'
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['lights']['UniversalLight']['verdict'])
    def test_missing_control_preflight_cannot_qualify_a_host(self):
        c,o=self.baseline();o['lights'].pop(0)
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['verdict'])
    def test_control_spawn_failure_cannot_qualify_a_host(self):
        c,o=self.baseline();o['hosts'][0]['lights'][0]['spawned']=False
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['verdict'])
    def test_variant_fit_conflict_cannot_qualify(self):
        c,o=self.baseline();row=o['hosts'][0]
        row['prereq']=f.prereq_obs('weaponHandguardAK');row['lights']=f.refusal_lights()
        row['prereq_variant']=f.variant_obs('weaponHandguardAK',[f.good_gun_lights()[2]])
        row['prereq_variant']['lights'][0]['per_slot'][2]['light_fits']=False
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['verdict'])
    def test_contradictory_attachment_is_pending(self):
        c,o=self.baseline();o['hosts'][0]['lights'][2]['per_slot'][2]['can_add']=False
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['verdict'])
    def test_negative_counters_cannot_qualify(self):
        c,o=self.baseline();o['counters'].update(spawned=-1,deleted=-1,census_total=-2,census_scanned=-2)
        self.assertEqual('pending',r.build_report(c,o)['hosts'][0]['verdict'])

if __name__=='__main__':unittest.main(verbosity=2)
