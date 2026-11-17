"""Synthetic resource and native-capacity ports; metadata is not perception."""
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_ecology_runtime import ROOT, environment, translated


class NativeResourceSurveys(unittest.TestCase):
    def setUp(self):
        self.e = environment(); self.enabled = True; self.authority = True
        self.e['HCEcologyMigrationQualification'] = NS(Admitted=lambda: self.enabled)
        self.game = NS(GetWorldName=lambda: 'synthetic-world', SurfaceIsPond=lambda x,z: x == 10,
                       SurfaceIsSea=lambda x,z: z == 20)
        self.e['GetGame'] = lambda: self.game
        self.e['HCEcologyNative'] = NS(Authority=lambda: self.authority, SampleResource=lambda obj: obj.kind)
        text = (ROOT/'4_World/Ecology/HCEcologyResourceSurvey.c').read_text()
        self.pond = translated(text, 'Pond', self.e, 'HCEcologyResourceSurvey')
        self.observe = translated(text, 'ObjectSample', self.e, 'HCEcologyResourceSurvey')
        self.handle = NS(kind=1, GetPosition=lambda: [1.,2.,3.])

    def test_pond_uses_only_supplied_point_and_rejects_sea_or_invalid_sample(self):
        got = self.pond([10.,0.,0.], 'pond-a', 100)
        self.assertEqual((2, 'pond', [10.,0.,0.], 100, 'synthetic-world'),
                         (got.ResourceKind, got.SourceKind, got.Position, got.ObservedAtMs, got.WorldName))
        for point, key, now in [([11.,0.,0.], 'x', 100), ([10.,0.,20.], 'x', 100),
                                ([10.,float('nan'),0.], 'x', 100), ([10.,0.,0.], '../x', 100),
                                ([10.,0.,0.], 'x', -1)]:
            self.assertIsNone(self.pond(point,key,now))

    def test_resource_resampled_each_call_and_never_promoted_to_eligibility(self):
        got = self.observe(self.handle, 'food-a', 100)
        self.assertEqual((1, 'object', [1.,2.,3.]), (got.ResourceKind,got.SourceKind,got.Position))
        self.assertFalse(got.SensoryEligibility)
        self.handle.kind = 0
        self.assertIsNone(self.observe(self.handle, 'food-a', 101))
        self.assertIsNone(self.observe(None, 'food-a', 101))

    def test_resource_metadata_uses_the_same_canonical_world_as_migration(self):
        self.game.GetWorldName = lambda: 'SYNTHETIC-World'
        self.assertEqual('synthetic-world', self.pond([10.,0.,0.], 'pond-a', 100).WorldName)
        self.assertEqual('synthetic-world', self.observe(self.handle, 'food-a', 100).WorldName)

    def test_client_and_unqualified_process_cannot_survey(self):
        self.enabled = False
        self.assertIsNone(self.pond([10.,0.,0.], 'x', 100))
        self.assertIsNone(self.observe(self.handle, 'x', 100))
        self.enabled = True; self.authority = False
        self.assertIsNone(self.pond([10.,0.,0.], 'x', 100))
        self.assertIsNone(self.observe(self.handle, 'x', 100))


class NativeCapacityRead(unittest.TestCase):
    def test_reads_correct_live_ce_globals_and_missing_api_is_unknown(self):
        env=environment(); trace=[]; authority=[True]; available=[True]
        env['HCEcologyPopulation']=NS(ANIMAL=1,INFECTED=2)
        env['HCEcologyNative']=NS(Authority=lambda:authority[0])
        env['GetCEApi']=lambda:NS(GetCEGlobalInt=lambda key:trace.append(key) or {'AnimalMaxCount':200,'ZombieMaxCount':1000}[key]) if available[0] else None
        text=(ROOT/'4_World/Ecology/HCEcologyMigrationNative.c').read_text().replace('CEApi economy', 'HCEcologyEconomy economy')
        ceiling=translated(text,'Ceiling',env,'HCEcologyMigrationNative')
        self.assertEqual(200,ceiling(1)); self.assertEqual(1000,ceiling(2))
        self.assertEqual(['AnimalMaxCount','ZombieMaxCount'],trace)
        self.assertEqual(0,ceiling(99))
        available[0]=False;self.assertEqual(0,ceiling(1))
        authority[0]=False;self.assertEqual(0,ceiling(2))
