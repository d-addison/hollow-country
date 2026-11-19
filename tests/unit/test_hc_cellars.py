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
MODULE = ROOT / 'mods/HollowCountry/scripts/4_World/Atmosphere/HCCellarsModule.c'
CLIENT = ROOT / 'mods/HollowCountry/scripts/5_Mission/Atmosphere/HCCellarsClient.c'
ADMISSION = ROOT / 'mods/HollowCountry/scripts/3_Game/Atmosphere/HCCellarAdmission.c'


class MeasuredCellarSlice(unittest.TestCase):
    def test_failed_stairs_never_accept_and_first_slice_stays_bounded(self):
        # Explicit synthetic startup counters: a three-class survey, one with
        # measured geometry. Neither geometry nor V2 preferences qualify it.
        from tests.unit.test_hc_operational_status import authored_status
        logs = []
        make_status, cache = authored_status(logs)
        module = N(m_HC31Status=make_status(), m_HC31Started=False,
                   m_MeasuredClasses=1, m_PendingClasses=3,
                   m_Survey=None, m_Measurement=None,
                   HCReadCounts=lambda: True)
        reads = []
        module.HCReadCounts = lambda: reads.append('startup') or True
        # Startup test ports supply IO/counts; the real counter is exercised below.
        if 'protected void HCReceipt(' in MODULE.read_text():
            module.HCReceipt = MethodType(translate(str(MODULE), 'protected void HCReceipt(', (),
                                                     Print=logs.append), module)
        gate = N(HCAdmitted=lambda: False, HCReason=lambda: 'native_cellar_qualification_pending')
        start = translate(str(MODULE), 'override void OnStart(', ('HCReadCounts', 'HCReceipt'),
                          Print=logs.append, HCCellarAdmission=gate,
                          HCV2Admission=N(Line=lambda *args: 'synthetic V2 preference diagnostic'),
                          HCV2Gates=N(Qualified=lambda *args: False))
        start(module, N(EnableAmbientLife=True))
        start(module, N(EnableAmbientLife=True))
        receipts = [line for line in logs if line.startswith('[HC Plan] HC-31 cellar_measured=')]
        self.assertEqual(len(receipts), 1, 'cellar startup must publish one measured-count receipt')
        self.assertIn('cellar_measured=1 admitted=0 pending=3 state=refused', receipts[0])
        self.assertEqual(reads, ['startup'])
        self.assertIs(translate(str(MODULE), 'override HCOperationalStatus HCGetOperationalStatus(', ())(module),
                      module.m_HC31Status)
        self.assertIn('runtime=PENDING', receipts[0])
        start(module, N(EnableAmbientLife=True))
        self.assertEqual(receipts, [line for line in logs if line.startswith('[HC Plan] HC-31 cellar_measured=')])
        getter = translate(str(MODULE), 'override HCOperationalStatus HCGetOperationalStatus(', ())
        self.assertIs(getter(module), module.m_HC31Status)
        cache.HCCapture('Cellars', True, getter(module))
        self.assertIn('module=Cellars state=refused', cache.HCLine(0))
        self.assertIn('reason=native_cellar_qualification_pending', cache.HCLine(0))
        enabled = translate(str(MODULE), 'override bool IsEnabled(', ())
        for settings in (None, N(EnableAmbientLife=False)):
            self.assertFalse(enabled(module, settings))
            self.assertEqual(module.m_HC31Status.HCState(), 'off')
        translate(str(MODULE), 'override void OnStop(', ())(module)
        self.assertFalse(module.m_HC31Started)
        self.assertEqual(module.m_HC31Status.HCState(), 'off')
        module.HCReadCounts = lambda: False
        start(module, N(EnableAmbientLife=True))
        self.assertEqual(module.m_HC31Status.HCReason(), 'measurement_counts_unavailable')

        survey = N(SchemaVersion=1, WorldName='chernarusplus', Classes=Array([
            N(BuildingClass='Land_SyntheticA'), N(BuildingClass='Land_SyntheticB'),
            N(BuildingClass='Land_SyntheticC')]))
        measurement = N(SchemaVersion=1, WorldName='chernarusplus', Complete=True,
                        SkippedTiles=0, Classes=Array([
                            N(BuildingClass='Land_SyntheticA', Instances=Array([
                                N(GeometryMeasured=True), N(GeometryMeasured=True)])),
                            # High class scores/selection must not imply measured geometry.
                            N(BuildingClass='Land_SyntheticB', SampleCount=99,
                              Eligible=True, SliceSelected=True,
                              Instances=Array([N(GeometryMeasured=False)]))]))
        counter = translate(str(MODULE), 'protected bool HCCountEvidence(', ())
        module.m_Survey, module.m_Measurement = survey, measurement
        self.assertTrue(counter(module))
        self.assertEqual((module.m_MeasuredClasses, module.m_PendingClasses), (1, 3))
        for field, value in (('Complete', False), ('SkippedTiles', 1), ('WorldName', 'synthetic-other')):
            invalid = copy.deepcopy(measurement)
            setattr(invalid, field, value)
            module.m_Measurement = invalid
            self.assertFalse(counter(module), field)
            self.assertEqual(module.m_MeasuredClasses, 0)
        for invalid_rows in (
            Array([measurement.Classes[0], measurement.Classes[0]]),
            Array([N(BuildingClass='Land_SyntheticUnknown', Instances=Array())]),
            Array([N(BuildingClass='Land_SyntheticA', Instances=Array([N(GeometryMeasured=True)] * 8193))]),
        ):
            module.m_Measurement = N(**dict(vars(measurement), Classes=invalid_rows))
            self.assertFalse(counter(module))
        module.m_Measurement = None
        self.assertTrue(counter(module))
        self.assertEqual((module.m_MeasuredClasses, module.m_PendingClasses), (0, 3))
        # Count the actual authored queue too, without a hard-coded startup 28.
        authored = json.loads((ROOT / 'mission/hollow-country/cellars/classes.json').read_text())
        module.m_Survey = N(**dict(authored, Classes=Array([N(**row) for row in authored['Classes']])))
        self.assertTrue(counter(module))
        self.assertEqual(module.m_PendingClasses, len(authored['Classes']))

        # IO is an explicit synthetic out-parameter port: the DTOs above are
        # preloaded; authored loader code still selects paths and byte bounds.
        files, loaded = set(), []
        module.m_Survey, module.m_Measurement = survey, None
        module.HCCountEvidence = lambda: counter(module)
        reader = translate(str(MODULE), 'protected bool HCReadCounts(', ('HCCountEvidence',),
                           FileExist=lambda path: path in files,
                           HCGroupJson=N(Load=lambda path, limit, target: loaded.append((path, limit)) or True))
        self.assertTrue(reader(module))
        self.assertEqual(loaded, [('$mission:hollow-country/cellars/classes.json', 32768)])
        files.add('$profile:HollowCountry/cellars-measured.json.tmp')
        self.assertFalse(reader(module))
        files.clear()
        files.add('$profile:HollowCountry/cellars-measured.json.bak')
        self.assertFalse(reader(module))
        files.add('$profile:HollowCountry/cellars-measured.json')
        files.add('$profile:HollowCountry/cellar-classes.json')
        module.m_Measurement = measurement
        self.assertTrue(reader(module))
        self.assertEqual(loaded[-2:], [('$profile:HollowCountry/cellar-classes.json', 32768),
                                      ('$profile:HollowCountry/cellars-measured.json', 1048576)])

        sampler_logs = []
        sampler_receipt = translate(str(SAMPLER), 'protected void HCReceipt(', (), Print=sampler_logs.append)
        sampler_receipt(N(m_Status=make_status(), m_Data=survey, m_MeasuredClasses=1), 'ready',
                        'measurement_only_native_stair_route_unobserved')
        self.assertTrue(sampler_logs[0].startswith('[HC Cellars] HC-31 sampler '),
                        'sampler must not duplicate the module startup receipt')

        gate.HCAdmitted = lambda: translate(str(ADMISSION), 'static bool HCAdmitted(', ())(None)
        gate.HCReason = lambda: translate(str(ADMISSION), 'static string HCReason(', ())(None)
        self.assertFalse(gate.HCAdmitted())
        # Execute real mission startup with no world/player/render ports: closed
        # admission must return before helper allocation or any heuristic sample.
        events = []
        mission = N(m_HCCellars=None)
        init = translate(str(CLIENT), 'override void OnInit(', (), Print=logs.append,
                         super=N(OnInit=lambda: events.append('super')),
                         GetGame=lambda: N(IsDedicatedServer=lambda: False),
                         HCCellarAdmission=gate,
                         HCCellarsClient=N(HCPreferenceEnabled=lambda: True))
        init(mission)
        self.assertEqual(events, ['super'])
        self.assertIsNone(mission.m_HCCellars)
        self.assertTrue(any('client state=refused refused=' + gate.HCReason() in line for line in logs))
        translate(str(CLIENT), 'void HCSample(', ('HCClear',), HCCellarAdmission=gate)(N(), 1.)

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
