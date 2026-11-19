"""HC-59: authored finite supply over explicit SYNTHETIC native/disk ports.

Spec/plan/task: HC-59 supplied Wave 3 contract, HC-4/32 integrity and HC-18
locality input. Missing docs/SPECIFICATION.md and docs/specs/001-survival-overhaul/spec.md
are not substituted with native acceptance. One behavioral scenario covers two
actors, compatible outputs, failed creation/save and a synthetic restart.
Offline execution never establishes DayZ inventory, access or repair behavior.

Actual RED (2026-11-18), same focused command as GREEN:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_wreck_supply -v
AssertionError: Lists differ: ['CivSedanWheel'] != ['HatchbackWheel']
GREEN after the compatible picker: Ran 1 test / OK.
"""
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_refusal_report import MethodsTranslator
from tests.unit.test_search_economy_houses import HMap, find_out
from tests.unit.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/Vehicles/HCWreckSalvage.c'


class SyntheticArray(EArray):
    def Insert(self, item):
        self.append(item)
        return len(self) - 1


class WreckSupply(unittest.TestCase):
    def test_two_actors_restart_never_replenish_compatible_finite_parts(self):
        source = SOURCE.read_text().replace('.IndexOf(', '.find(')
        source = source.replace('key.Hash()', 'native_hash(key)')
        # Language lowering only: inline array literals and native fixed arrays.
        source = re.sub(r'(array<string> \w+ = )\{([^}]+)\};',
                        r'\1SyntheticArray([\2]);', source)
        source = source.replace('vector transform[4];', 'vector transform = SyntheticTransform();')
        # Qualify injected boundary methods omitted by MethodsTranslator.
        source = re.sub(r'(?<![\w.])Save\(\)', 'self.Save()', source)
        source = re.sub(r'(?<![\w.])Load\(\)', 'self.Load()', source)
        now, outputs, persisted, logs = [100], [], {}, []
        create_ok, save_ok = [True], [True]
        # Explicit synthetic config slots, not native config fixtures.
        slot_config = {}
        for i, (wheel, vehicle) in enumerate([
                ('HatchbackWheel', 'OffroadHatchback'), ('Hatchback_02_Wheel', 'Hatchback_02'),
                ('CivSedanWheel', 'CivilianSedan'), ('Sedan_02_Wheel', 'Sedan_02')]):
            slot_config['CfgVehicles ' + wheel + ' inventorySlot'] = ['synthetic-slot-' + str(i)]
            slot_config['CfgVehicles ' + vehicle + ' attachments'] = ['synthetic-slot-' + str(i)]
        game = N(IsServer=lambda: True, GetTime=lambda: now[0], GetTickTime=lambda: now[0] / 1000,
                 GetWorldName=lambda: 'chernarusplus', ConfigIsExisting=lambda path: True,
                 ConfigGetInt=lambda path: 2,
                 ConfigGetTextArray=lambda path, dest: dest.extend(slot_config.get(path, [])))
        class Status:
            def HCPublish(self, state, reason):
                self.state, self.reason = state, reason
            def HCReason(self):
                return self.reason
        env = dict(HCModule=object, EArray=SyntheticArray, HMap=HMap, find_out=find_out,
                   SyntheticArray=SyntheticArray, SyntheticTransform=lambda: [None] * 4,
                   GetGame=lambda: game, Print=logs.append, tostr=str, native_hash=lambda key: 0,
                   Math=N(Round=round),
                   Math3D=N(MatrixIdentity4=lambda matrix: None),
                   InventoryLocation=lambda: N(SetGround=lambda obj, matrix: None),
                   ItemBase=N(Cast=lambda value: value), ECE_PLACE_ON_SURFACE=1, RF_DEFAULT=0,
                   HCWreckSalvageRow=lambda: N(), HCSearchNoise=N(Emit=lambda player: None),
                   HCUnitBudget=lambda: N(HCReset=lambda *args: None, HCTake=lambda cost: True),
                   HCWorkBudget=lambda: N(HCReset=lambda *args: None, HCContinue=lambda: True),
                   HCOperationalStatus=Status,
                   HCShelterCatalog=N(Count=lambda: 6, CandidateCount=lambda: 5),
                   HCV2Admission=N(Line=lambda *args: 'synthetic-admission'),
                   HCV2Gates=N(Qualified=lambda gate: False),
                   HCBuildIdentity=N(SameWorld=lambda a, b: a == b),
                   HCRefusal=N(BUSY='busy', SERVICE='service', SALVAGE='salvage_unavailable',
                               CAPACITY='capacity', SESSION='session_changed'))
        def create(location, kind, flags, rotation):
            if not create_ok[0]:
                return None
            outputs.append(kind)
            return N(SetQuantity=lambda quantity: None)
        env['GameInventory'] = N(LocationCreateEntity=create)
        for code in MethodsTranslator(source, 'HCWreckSalvage',
                                      ('Reviewed', 'PositionValid', 'Key', 'Roll', 'Budget', 'Part',
                                       'HCWheel', 'HCPartForWreck', 'HCWheelFits')).classes():
            exec(code, env)
        policy = env['HCWreckSalvage']
        # The synthetic native hash is zero; authored Key/Roll/Budget select a
        # one-part source and a wheel without duplicating gameplay policy here.
        policy.Allowed = lambda *args: True  # geometry/authority need DayZ tests
        methods = ('Enroll', 'Debit', 'CanStart', 'Begin', 'Continuing', 'Complete', 'End',
                   'IsEnabled', 'HCReport', 'Fault', 'OnStart', 'OnStop', 'OnTick', 'Purge',
                   'HCGetOperationalStatus', 'HCRefuseStart', 'HCRefuseBegin')
        for code in MethodsTranslator(source, 'HCWreckSalvageModule', methods).classes():
            exec(code, env)
        owner = env['HCWreckSalvageModule']
        module = owner()
        module.Load = lambda: setattr(module, 'm_State', N(Rows=SyntheticArray())) or True
        module.OnStart(N(EnableTravel=True))
        self.assertTrue(module.m_Active)
        self.assertEqual('ready', module.HCGetOperationalStatus().state)
        self.assertIn('shelters=6 wreck_classes=24 salvage_receipts=0 state=ready',
                      next(line for line in logs if 'shelters=6' in line))
        # Slot drift refuses the authoring policy without loading/creating stock.
        slot_config['CfgVehicles CivSedanWheel inventorySlot'] = ['synthetic-wrong-slot']
        refused = owner()
        refused.Load = lambda: self.fail('config refusal must precede journal admission')
        refused.OnStart(N(EnableTravel=True))
        self.assertFalse(refused.m_Active)
        self.assertEqual('refused', refused.HCGetOperationalStatus().state)
        slot_config['CfgVehicles CivSedanWheel inventorySlot'] = ['synthetic-slot-2']
        def save():
            if not save_ok[0]:
                return False
            persisted['rows'] = json.dumps([vars(row) for row in module.m_State.Rows])
            return True
        module.Save = save
        player = lambda: N(GetIdentity=lambda: object(), GetPosition=lambda: [1, 0, 1])
        alice, bob = player(), player()
        tool = object()
        wreck = N(GetType=lambda: 'Land_Wreck_sed01_aban1_black', GetPosition=lambda: [10, 0, 20])
        target = N(GetObject=lambda: wreck)
        def action(actor):
            return N(Completed=False, m_Player=actor, m_Target=target, m_MainItem=tool,
                     Key='', Wreck=None, Tool=None, Index=-1, StartedMs=0)
        first, competing = action(alice), action(bob)
        module.Begin(first)
        module.Begin(competing)
        self.assertEqual(1, module.m_Sessions.Count(), 'one source lease, never one per actor')
        self.assertEqual(1, module.m_State.Rows.Count())
        now[0] += 7500
        module.Complete(first)
        module.Complete(first)
        module.Complete(competing)
        self.assertEqual(['CivSedanWheel'], outputs, 'sed01 must not yield a hatchback wheel')
        self.assertEqual(0, module.m_State.Rows[0].Left)
        self.assertEqual(0, json.loads(persisted['rows'])[0]['Left'])
        module.End(first)
        module.Begin(action(bob))
        self.assertEqual(0, module.m_Sessions.Count())

        # SYNTHETIC JSON loader boundary after restart: only persisted rows are
        # rehydrated, not a Python allocation/depletion policy.
        module = owner()
        module.m_Active = True
        module.m_State = N(Rows=SyntheticArray(N(**row) for row in json.loads(persisted['rows'])))
        module.m_Index = HMap({row.Key: i for i, row in enumerate(module.m_State.Rows)})
        module.Save = save
        self.assertEqual(0, module.Enroll(wreck))
        self.assertFalse(module.CanStart(bob, target, tool))
        module.Begin(action(bob))
        self.assertFalse(module.Debit(0))
        self.assertEqual(['CivSedanWheel'], outputs)

        # Other exact reviewed car families retain the same single finite
        # allocation; neither native creation failure nor save uncertainty refunds.
        for family, wheel in [('hb01', 'HatchbackWheel'), ('hb02', 'Hatchback_02_Wheel'),
                              ('sed02', 'Sedan_02_Wheel')]:
            colour = dict(hb01='blue', hb02='black', sed02='grey')[family]
            wreck = N(GetType=lambda f=family, c=colour: 'Land_Wreck_' + f + '_aban1_' + c,
                      GetPosition=lambda: [30, 0, 40])
            expected_before = list(outputs)
            data = action(alice)
            module.Begin(data)
            now[0] += 7500
            create_ok[0] = family != 'hb02'
            save_ok[0] = family != 'sed02'
            module.Complete(data)
            module.Complete(data)
            self.assertEqual(expected_before + ([wheel] if family == 'hb01' else []), outputs)
            self.assertEqual(0, module.m_State.Rows[data.Index].Left)
            module.End(data)
        self.assertFalse(module.m_Active, 'failed save closes the source without refund')
        self.assertEqual('refused', module.HCGetOperationalStatus().state)
        saved_image = persisted['rows']
        module.OnStop()
        self.assertEqual('off', module.HCGetOperationalStatus().state)
        self.assertEqual(0, module.m_Sessions.Count())
        self.assertIsNone(module.m_State)
        self.assertEqual(saved_image, persisted['rows'], 'stop cannot rewrite uncertain receipts')
        module.OnStart(N(EnableTravel=False))
        module.OnTick(1.0)
        self.assertFalse(module.m_Active)
        self.assertEqual('off', module.HCGetOperationalStatus().state)

        # Authored disposition integrity is part of the same behavior contract;
        # this is not a stock-map/native census test.
        manifest = json.loads((ROOT / 'mission/hollow-country/travel/wreck-dispositions.json').read_text())
        self.assertEqual(40, len(manifest['entries']))
        for row in manifest['entries']:
            self.assertEqual(row['disposition'] == 'finite-car-parts', policy.Reviewed(row['class']))
            if row['disposition'] == 'finite-car-parts':
                self.assertEqual(row['wheel'], policy.HCPartForWreck(row['class'], 'synthetic', 1))
            else:
                self.assertEqual('', policy.HCPartForWreck(row['class'], 'synthetic', 1))
        self.assertEqual('', policy.HCPartForWreck('Land_Wreck_hb01_unreviewed', 'synthetic', 1))
        self.assertEqual('', policy.HCPartForWreck('Land_Wreck_hb01_aban1_blue', 'synthetic', 0))


if __name__ == '__main__':
    unittest.main()
