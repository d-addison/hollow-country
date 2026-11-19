"""HC-31: one behavioral slice on authored handlers and synthetic geometry only.

Restricted Enforce translation is an existing test port, never DayZ evidence.
Spec/plan/task: HC-31 / #151 access / #60 / FR-011 / NFR-003; lead owns HC-11.
"""
from pathlib import Path
from types import MethodType, SimpleNamespace as N
import copy
import contextlib
import io
import json
import tempfile
import unittest

from tests.unit.test_infected_admission import Array, translate

ROOT = Path(__file__).resolve().parents[2]
SAMPLER = ROOT / 'mods/HollowCountry/scripts/4_World/Interiors/HCCellarSampler.c'


class MeasuredCellarSlice(unittest.TestCase):
    def test_failed_stairs_never_accept_and_first_slice_stays_bounded(self):
        # Explicit synthetic nine-point success, followed by a failed bottom anchor.
        row = N(StairsMeasured=True, StairTop=[0, 0, 1], StairBottom=[0, -2, 1],
                BoxMin=[0, 0, 0], BoxMax=[0, 0, 0], AcceptedInstances=0,
                SampleCount=0, Inconsistent=False)
        instance = N(Eligible=False, Reason='')
        outcomes = iter((True, False))
        sampler = N(m_Row=row, m_Instance=instance, m_House=object(),
                    m_BoxMin=[-3, -3, -2], m_BoxMax=[3, -1, 2],
                    HCStairPoint=lambda point: next(outcomes), HCVolumeValid=lambda *args: True)
        record = translate(str(SAMPLER), 'protected void HCRecord(',
                           ('HCStairPoint', 'HCVolumeValid'))
        record(sampler, True, 'synthetic nine-point success')
        self.assertEqual(row.AcceptedInstances, 0,
                         'failed stair sample was counted accepted')
        self.assertFalse(instance.Eligible)
        self.assertEqual(instance.Reason, 'stair_anchor_probe_failed')
        self.assertIsNone(sampler.m_House)
        self.assertTrue(row.StairsMeasured, 'one failed instance must not rewrite authored anchors')

        # Execute the retained object cursor with the real shared budgets. The
        # synthetic native port returns no time cost; this proves count bounds only.
        from tests.unit.test_hc_infected_doors import shared_budget
        world = SAMPLER.parents[1]
        game = N(GetTickTime=lambda: 0.)
        units = shared_budget(world / 'Core/HCUnitBudget.c', 'HCUnitBudget', {},
                              ('HCReset', 'HCTake', 'HCUsed'), game)
        work = shared_budget(world / 'World/HCWorkBudget.c', 'HCWorkBudget', {},
                             ('HCReset', 'HCMayContinue', 'HCContinue'), game)
        probe = translate(str(SAMPLER), 'protected void HCProbeTick(',
                          ('HCCheckPoint', 'HCSeedBox', 'HCRecord'))
        visited = []
        cursor = N(m_Check=0, m_Seed=0, m_Units=units, m_Work=work,
                   HCCheckPoint=lambda index: visited.append(index) or True,
                   HCSeedBox=lambda index: False, HCRecord=lambda *args: None)
        # A test-selected 5-unit budget permits one point, then resumes at point 1.
        for _ in range(2):
            units.HCReset(5)
            work.HCReset(24)
            probe(cursor)
            self.assertLessEqual(units.HCUsed(), 5)
        self.assertEqual(visited, [0, 1])
        cursor.m_Check = -1
        units.HCReset(24)
        work.HCReset(24)
        probe(cursor)
        self.assertEqual(cursor.m_Seed, 3)
        self.assertEqual(units.HCUsed(), 21)
        # An expired cooperative clock yields before altering the retained cursor.
        work.HCMayContinue = lambda now: False
        probe(cursor)
        self.assertEqual(cursor.m_Seed, 3)
        off = N(m_Running=False)
        tick = translate(str(SAMPLER), 'override void OnTick(',
                         ('HCAbort', 'HCProbeTick', 'HCSummaryTick'))
        tick(off, 1.)  # no buffers/native ports available on the off path
        logs = []
        stopper = N(m_Running=True, m_House=object(), m_Instance=instance, m_Row=row,
                    m_Objects=Array([object()]), m_Cargos=Array(), m_Hits=Array([object()]),
                    m_Status=N(HCPublish=lambda *args: logs.append(args)),
                    HCReceipt=lambda *args: logs.append(args))
        stopper.HCAbort = MethodType(translate(str(SAMPLER), 'protected void HCAbort(',
                                              ('HCReceipt',), Print=logs.append), stopper)
        translate(str(SAMPLER), 'override void OnStop(', ('HCAbort',))(stopper)
        self.assertFalse(stopper.m_Running)
        self.assertIsNone(stopper.m_House)
        self.assertIsNone(stopper.m_Objects)
        self.assertEqual(stopper.m_ObjectCursor, 0)
        self.assertEqual(stopper.m_Check, -1)
        self.assertEqual(logs[-1], ('off', 'sampler_stopped'))

        from tools.audit import cellar_triggers as ct
        authored = json.loads((ROOT / 'mission/hollow-country/cellars/classes.json').read_text())
        self.assertEqual(len(authored['Classes']), 28)
        self.assertEqual(len({r['SurveyTask'] for r in authored['Classes']}), 28)
        self.assertTrue(all(r['Disposition'] == 'pending' and not r['StairsMeasured']
                            for r in authored['Classes']))
        # Synthetic scene: authored bounds and anchors, no real map observations.
        good = dict(BuildingClass='Land_SyntheticCellar', Confidence=1.0, SampleCount=9,
                    StairsMeasured=True, StairTop=[0, 0, 1], StairBottom=[0, -2, 1],
                    BoxMin=[-3, -3, -2], BoxMax=[3, -1, 2], Instances=[dict(
                        Position=[100, 10, 200], Yaw=90, Eligible=True,
                        GeometryMeasured=True, StairAnchorsValid=True, SliceSelected=True)])
        measured = dict(SchemaVersion=1, WorldName='chernarusplus', Complete=True,
                        TriggerDefaults=authored['TriggerDefaults'], Classes=[good])
        failed = copy.deepcopy(measured)
        failed['Classes'][0]['Instances'][0].update(Eligible=False, StairAnchorsValid=False,
                                                   Reason='stair_anchor_probe_failed')
        payload, report = ct.generate(failed)
        self.assertEqual(payload['Triggers'], [])
        self.assertEqual(report['admitted'], 0)
        self.assertIn('stair_anchor_probe_failed', str(report))
        failed['Classes'][0]['Confidence'] = 0
        self.assertIn('stair_anchor_probe_failed', str(ct.generate(failed)[1]))
        for field in ('Eligible', 'GeometryMeasured', 'StairAnchorsValid', 'SliceSelected'):
            missing = copy.deepcopy(measured)
            del missing['Classes'][0]['Instances'][0][field]
            self.assertEqual(ct.generate(missing)[0]['Triggers'], [], field)
        # A class result never automatically qualifies other instances or classes.
        second = copy.deepcopy(good)
        second['BuildingClass'] = 'Land_SyntheticOtherCellar'
        measured['Classes'] = [good, second] + copy.deepcopy(authored['Classes'][2:])
        payload, report = ct.generate(measured)
        self.assertEqual(len(payload['Triggers']), 4)
        self.assertEqual(len(report['classes']), 28)
        self.assertEqual(report['admitted'], 0)
        self.assertEqual(report['pending'], 28)
        self.assertEqual(report['runtime'], 'PENDING')
        self.assertEqual(payload['Triggers'][1]['Position'], [100, 8, 200])
        self.assertEqual(payload['Triggers'][1]['Size'], [6, 2, 4])
        self.assertEqual(payload['Triggers'][0]['Breadcrumbs'][0]['Position'], [101, 10, 200])
        over = copy.deepcopy(measured)
        over['Classes'][2] = dict(copy.deepcopy(good), BuildingClass='Land_SyntheticThirdCellar')
        with self.assertRaisesRegex(ValueError, 'two selected spaces'):
            ct.generate(over)
        uncertain = copy.deepcopy(measured)
        uncertain['Classes'][0]['Inconsistent'] = True
        self.assertEqual(len(ct.generate(uncertain)[0]['Triggers']), 2)
        # Native stock bytes, drift refusal and rollback share the existing overlay protocol.
        with tempfile.TemporaryDirectory(prefix='hc31-synthetic-') as directory:
            root = Path(directory)
            measurement = root / 'measurement.json'
            measurement.write_text(json.dumps(measured))
            generated, mission = root / 'generated', root / 'mission'
            mission.mkdir()
            with contextlib.redirect_stdout(io.StringIO()):
                ct.generate_files(measurement, generated, ct.MIN_CONFIDENCE)
            with self.assertRaisesRegex(ValueError, 'native-baseline'):
                ct.install_plan(generated, mission)
            native = mission / ct.TRIGGER_FILE
            before = b'{"Triggers":[{"Comment":"synthetic native stock"}]}\n'
            native.write_bytes(before)
            candidate = ct.install_plan(generated, mission)
            ct.overlays.install(candidate, mission, managed_name=ct.overlays.CELLARS_MANAGED)
            installed = native.read_bytes()
            self.assertEqual(json.loads(installed)['Triggers'][0]['Comment'], 'synthetic native stock')
            native.write_bytes(installed + b' ')
            with self.assertRaisesRegex(ValueError, 'drift'):
                ct.overlays.rollback(mission, managed_name=ct.overlays.CELLARS_MANAGED)
            native.write_bytes(installed)
            ct.overlays.rollback(mission, managed_name=ct.overlays.CELLARS_MANAGED)
            self.assertEqual(native.read_bytes(), before)
            output = generated / ct.TRIGGER_FILE
            output.write_bytes(output.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'hash'):
                ct.install_plan(generated, mission)


if __name__ == '__main__':
    unittest.main()
