"""Audit #58/#197: execute authored handlers with explicit synthetic native fakes.
These tests do not establish DayZ inventory, geometry, energy or replication.

Audit-light fix-round spec/plan/tasks (2026-11-19):
- P1: mounted identity follows the actual admitted slot; cross fallback is cargo-only.
- P2: helmet and pack startup depend on the shared adapter's availability.
- Tasks: execute failing authored-handler regressions, make the smallest adapter
  changes, validate the legacy-test diff in temporary copies, retain runtime gates.
RED: python3 -B -m unittest tests.unit.test_auditlight_runtime.ReviewRegressions -v
Ran 3 tests; FAILED (failures=3). Actual lines: "True is not false" and
"[('off', 'taped_light_unavailable')] != [('ready', 'admitted_unverified')]"
(for both helmet and pack startup).
GREEN: the same command -> Ran 3 tests; OK.
Native proxy alignment, compilation, persistence/rejoin and normal packaged
server/two-client acceptance remain PENDING.
"""
import re
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.unit.test_group_server import body, EArray
from tests.unit.test_group_ui import ui_member
from tests.unit.test_hc_taped_pack_loader import build, start, MANIFEST, CATALOG, light_catalogue

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCTapedLightNative.c'
SERVICE = ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCTapedLightService.c'
HELMET = ROOT / 'mods/HollowCountry/scripts/4_World/Survival/HCTapedHelmetMounts.c'


_build = build

def build(*args, **kwargs):
    gate = _build(*args, **kwargs)
    # Explicit synthetic shared adapter; individual opt-out tests replace it.
    gate.env['HCTapedLightAdmission'] = NS(Admitted=lambda: True)
    return gate


def invoke(path, cls, method, state, env, *args, source=None):
    text = source or path.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    code = body(text, match.end())
    types = r'(?:HCTaped\w+|EntityAI|ItemBase|InventoryLocation|ComponentEnergyManager|TStringArray)'
    code = re.sub(r'ref array<ref HCTapedLightHostRow> ', 'HCGroupNative ', code)
    code = code.replace('new InventoryLocation', 'new HCGroupLocation')
    code = re.sub(r'\b(?:ref )?' + types + r' (?=\w+\s*[=;])', 'HCGroupNative ', code)
    code = re.sub(r'\b' + types + r' (?=\w+\s*\()', 'int ', code)
    return ui_member(code, method, state, env, *args)


class StableReceipts(unittest.TestCase):
    def test_host_rename_preserves_existing_receipt_identity(self):
        # Synthetic future config rename: the explicit selector changes, the
        # durable receipt key must survive without rewriting operator receipts.
        source = CATALOG.read_text().replace('row.HostClass == "AK101"', 'row.HostClass == "FutureAK101"')
        row = NS(HostClass='FutureAK101', LightClass='UniversalLight', SlotName='weaponFlashlight')
        catalog = light_catalogue()
        actual = invoke(CATALOG, 'HCTapedLightCatalog', 'CrossPairId', catalog, {}, row, source=source)
        self.assertEqual('cross_AK101_TLRLight', actual)

    def test_existing_operator_optout_survives_the_renamed_selector(self):
        from tests.unit.test_hc_taped_pack_receipts import receipt, receipts
        row = receipt('cross_AK101_TLRLight', checked=False)
        row['Disabled'] = True
        text = receipts(row)
        gate = build(MANIFEST.read_text(), receipts=text)
        catalog = gate.env['HCTapedLightCatalog']
        catalog.rows[0].HostClass = 'FutureAK101'
        source = CATALOG.read_text().replace('row.HostClass == "AK101"', 'row.HostClass == "FutureAK101"')
        catalog.CrossPairId = lambda row: invoke(CATALOG, 'HCTapedLightCatalog', 'CrossPairId', catalog, {}, row, source=source)
        self.assertEqual('', gate.ApplyManifest(MANIFEST.read_text()))
        gate.mHCSettingOn = True
        self.assertEqual('', gate.ApplyReceipts(text))
        self.assertTrue(gate.ReceiptDisabled('cross_AK101_TLRLight'))
        self.assertNotIn('cross_FutureAK101_TLRLight', catalog.CrossPairIds())


class WearableBindings(unittest.TestCase):
    def setUp(self):
        self.server = True
        self.helmet = True
        self.pack = True
        self.env = dict(GetGame=lambda: NS(IsServer=lambda: self.server),
                        HCTapedWearableCatalog=NS(Admitted=lambda: self.helmet),
                        HCTapedPackMounts=NS(PairQualified=lambda p: self.pack))
        self.owner = NS()

    def row(self, host, light='UniversalLight'):
        self.env['HCTapedLightHostRow'] = lambda: NS(PairId='', PrerequisiteSlot='', PrerequisiteClass='')
        return invoke(NATIVE, 'HCTapedLightV1Qualification', 'HCWearableRow', self.owner, self.env, host, light, False)

    def test_exact_helmet_and_pack_rows_and_no_descendants(self):
        helmet = self.row('Mich2001Helmet')
        self.assertEqual(('helmetFlashlight', ''), (helmet.SlotName, helmet.PairId))
        pack = self.row('TortillaBag')
        self.assertEqual(('helmetFlashlight', 'tortilla_universal_mount'), (pack.SlotName, pack.PairId))
        for host in ('TortillaBag_Winter', 'GorkaHelmet', 'Unknown'):
            self.assertIsNone(self.row(host))
        self.assertIsNone(self.row('Mich2001Helmet', 'TLRLight'))

    def test_server_opt_out_refuses_while_client_candidate_is_only_a_hint(self):
        self.helmet = self.pack = False
        self.assertIsNone(self.row('Mich2001Helmet'))
        self.assertIsNone(self.row('TortillaBag'))
        self.server = False
        self.assertIsNotNone(self.row('Mich2001Helmet'))
        self.assertIsNotNone(self.row('TortillaBag'))


class OperationalStatus(unittest.TestCase):
    def test_no_admitted_pair_cannot_publish_ready(self):
        gate = build(MANIFEST.read_text(), receipts=(MANIFEST.parent / 'pair-receipts.json').read_text())
        _, published = start(gate, setting=True)
        self.assertEqual('degraded', published[-1][0])
        self.assertIn('slot_unavailable', published[-1][1])
        self.assertEqual(1, len([line for line in gate.logs if '[HC TapedPackMounts] pack_pairs_refused' in line]))
        self.assertEqual(1, len([line for line in gate.logs if '[HC TapedPackMounts] weapon_pairs_refused' in line]))


class ReviewRegressions(unittest.TestCase):
    def test_mounted_pair_optout_cannot_fall_back_but_loose_cargo_can(self):
        events = []
        slot = {'value': 'helmetFlashlight'}
        energy = NS(IsSwitchedOn=lambda: False, CanSwitchOn=lambda: True,
                    CanWork=lambda: True, SwitchOn=lambda: events.append('on'))
        light = NS(GetType=lambda: 'UniversalLight', IsDamageDestroyed=lambda: False,
                   GetCompEM=lambda: energy,
                   GetInventory=lambda: NS(GetCurrentInventoryLocation=lambda loc: True))
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False, IsInVehicle=lambda: False,
                   FindAttachmentBySlotName=lambda s: None)
        host = NS(GetType=lambda: 'TortillaBag', GetHierarchyRootPlayer=lambda: actor,
                  IsDamageDestroyed=lambda: False,
                  FindAttachmentBySlotName=lambda s: light if s == slot['value'] else None)
        actor.GetItemInHands = lambda: host
        owner = NS()
        env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                   HCTapedLightAdmission=NS(Admitted=lambda: True),
                   HCTapedLightHostRow=lambda: NS(PairId='', PrerequisiteSlot='', PrerequisiteClass=''),
                   HCTapedLightCatalog=NS(Rows=lambda: EArray()),
                   HCTapedPackMounts=NS(PairQualified=lambda p: p == 'tortilla_universal_cross'),
                   ItemBase=NS(Cast=lambda v: v), InventoryLocationType=NS(CARGO=3),
                   HCGroupLocation=lambda: NS(GetType=lambda: 3 if slot['value'] == 'cargo' else 1))
        for method in ('HCWearableRow', 'Row'):
            setattr(owner, method, lambda *args, method=method: invoke(
                NATIVE, 'HCTapedLightV1Qualification', method, owner, env, *args))
        env['HCTapedLightV1Qualification'] = owner
        runtime = NS()
        for method in ('MountedLight', 'HCToggleCandidate', 'HCToggle'):
            setattr(runtime, method, lambda *args, method=method: invoke(
                NATIVE, 'HCTapedLightRuntime', method, runtime, env, *args))
        self.assertFalse(runtime.HCToggle(actor, host))
        self.assertEqual([], events)
        self.assertIsNone(owner.Row(host, light))
        slot['value'] = 'Chemlight'
        self.assertTrue(runtime.HCToggle(actor, host))
        self.assertEqual(['on'], events)
        self.assertEqual('Chemlight', owner.Row(host, light).SlotName)
        slot['value'] = 'cargo'
        self.assertEqual('Chemlight', owner.Row(host, light).SlotName)
        self.assertFalse(runtime.HCToggle(actor, host))
        self.assertEqual(['on'], events)
        slot['value'] = 'another_attachment'
        self.assertIsNone(owner.Row(host, light))
        slot['value'] = 'cargo'
        light.GetInventory = lambda: NS(GetCurrentInventoryLocation=lambda loc: False)
        self.assertIsNone(owner.Row(host, light))

    def test_shared_adapter_optout_closes_helmet_startup(self):
        from tests.unit.test_hc_taped_lights import helmet_member
        published, admission = [], []
        state = NS(mHCStarted=False, NativeSlotAvailable=lambda: True,
                   mHCStatus=NS(HCPublish=lambda *a: published.append(a)))
        env = dict(HCTapedLightAdmission=NS(Admitted=lambda: False), FileExist=lambda p: False,
                   HCTapedWearableCatalog=NS(HCSetAdmitted=admission.append, Rows=lambda: EArray(),
                                             CompatibilityQueue=lambda: EArray(), Qualified=lambda: False),
                   HCV2Admission=NS(Line=lambda *a: 'synthetic'), Print=lambda text: None)
        helmet_member(HELMET, 'HCTapedHelmetMounts', 'OnStart', state, env, NS())
        self.assertEqual([('off', 'taped_light_unavailable')], published)
        self.assertEqual([False], admission)

    def test_shared_adapter_optout_closes_pack_startup_with_usable_slots(self):
        from tests.unit.test_hc_taped_default_on import native_slots, PATCHED
        gate = build(MANIFEST.read_text(), receipts=(MANIFEST.parent / 'pair-receipts.json').read_text())
        native_slots(gate, PATCHED)
        gate.env['HCTapedLightAdmission'] = NS(Admitted=lambda: False)
        _, published = start(gate, setting=True)
        self.assertEqual([('off', 'taped_light_unavailable')], published)
        self.assertFalse(any('admission result=admitted' in line for line in gate.logs))


class NativeSwitch(unittest.TestCase):
    def test_server_switches_same_native_component_and_off_works_without_energy(self):
        events = []
        energy = NS(IsSwitchedOn=lambda: True, SwitchOff=lambda: events.append('off'),
                    CanSwitchOn=lambda: False, CanWork=lambda: False,
                    SwitchOn=lambda: events.append('on'))
        actor, host = NS(), NS()
        light = NS(GetCompEM=lambda: energy)
        state = NS(HCToggleCandidate=lambda a, h: light)
        env = {'GetGame': lambda: NS(IsServer=lambda: True),
               'HCTapedLightAdmission': NS(Admitted=lambda: True)}
        self.assertTrue(invoke(NATIVE, 'HCTapedLightRuntime', 'HCToggle', state, env, actor, host))
        self.assertEqual(['off'], events)
        energy.IsSwitchedOn = lambda: False
        self.assertFalse(invoke(NATIVE, 'HCTapedLightRuntime', 'HCToggle', state, env, actor, host))
        energy.CanSwitchOn = energy.CanWork = lambda: True
        self.assertTrue(invoke(NATIVE, 'HCTapedLightRuntime', 'HCToggle', state, env, actor, host))
        self.assertEqual(['off', 'on'], events)
        env['GetGame'] = lambda: NS(IsServer=lambda: False)
        self.assertFalse(invoke(NATIVE, 'HCTapedLightRuntime', 'HCToggle', state, env, actor, host))
        self.assertEqual(['off', 'on'], events)



class NativeBindingExecution(unittest.TestCase):
    def test_wearable_bindings_use_vehicle_slots_and_existing_transaction_policy(self):
        from tests.unit.test_taped_light_v1 import native_member
        for host_type, pair, slot, cross in (
                ('Mich2001Helmet', '', 'helmetFlashlight', False),
                ('TortillaBag', 'tortilla_universal_mount', 'helmetFlashlight', False),
                ('TortillaBag', 'tortilla_universal_cross', 'Chemlight', True)):
            with self.subTest(host=host_type, pair=pair):
                row = NS(HostClass=host_type, LightClass='UniversalLight', SlotName=slot,
                         PairId=pair, PrerequisiteSlot='', PrerequisiteClass='')
                probes = []
                def config(path, out):
                    probes.append(path)
                    out.extend([slot])
                owner = NS(Ready=lambda: True, Row=lambda h, l: row)
                env = dict(GetGame=lambda: NS(ConfigGetTextArray=config),
                           HCTapedLightJournal=lambda: NS(Build=lambda: 'synthetic'),
                           HCBuildIdentity=NS(Matches=lambda b: True, Canonical=lambda: 'synthetic'),
                           TStringArray=EArray, HCTapedLightBinding=lambda: NS(),
                           HCTapedLightCatalog=NS(MANIFEST='weapon_manifest', OBSERVATIONS='weapon_receipt'),
                           HCTapedWearableCatalog=NS(MANIFEST='wearable_authoring_manifest'),
                           HCTapedPackCatalog=NS(MANIFEST='pack_authoring_manifest'))
                binding = invoke(NATIVE, 'HCTapedLightV1Qualification', 'Resolve', owner, env, NS(), NS())
                self.assertEqual(['CfgVehicles ' + host_type + ' attachments',
                                  'CfgVehicles UniversalLight inventorySlot'], probes)
                self.assertEqual(('CfgVehicles', pair, slot, cross),
                                 (binding.HostConfigRoot, binding.PairId, binding.SlotName, binding.CrossSlot))
                self.assertEqual((1, 2, True), (binding.TapeUnits, binding.MaxDistance, binding.ReturnToCargo))
                self.assertEqual('wearable_authoring_manifest' if host_type == 'Mich2001Helmet' else 'pack_authoring_manifest', binding.ManifestDigest)
                self.assertEqual('', binding.MeasurementDigest)
                actor = NS()
                host = NS(GetHierarchyRootPlayer=lambda: actor)
                light = NS(GetHierarchyRootPlayer=lambda: actor, FindAttachmentBySlotName=lambda s: None)
                actor.GetItemInHands = lambda: host
                tape = NS(GetHierarchyRootPlayer=lambda: actor)
                destinations, reservations = [], []
                class Location:
                    def SetAttachment(self, h, l, native_slot):
                        destinations.append((h, l, native_slot))
                custody = NS(Ready=lambda: True, mHCReserved=EArray(), mHCBinding=binding,
                             Reserve=lambda item, destination: reservations.append(item) or True)
                custody_env = dict(GetGame=lambda: NS(IsServer=lambda: True),
                                   HCGroupLocation=Location,
                                   InventorySlots=NS(GetSlotIdFromString=lambda s: s))
                self.assertTrue(native_member('HCTapedLightV1Custody', 'Acquire', custody,
                                              custody_env, actor, host, light, tape, True))
                self.assertEqual([(host, light, slot)], destinations)
                self.assertEqual([light, host, tape], reservations)
                reservations.clear()
                actor.GetItemInHands = lambda: None
                self.assertFalse(native_member('HCTapedLightV1Custody', 'Acquire', custody,
                                               custody_env, actor, host, light, tape, True))
                self.assertEqual([], reservations)

    def test_toggle_access_is_only_owned_held_or_worn_and_never_nested_cargo(self):
        from tests.unit.test_taped_light_v1 import native_member
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False, IsInVehicle=lambda: False,
                   GetItemInHands=lambda: None, FindAttachmentBySlotName=lambda slot: None)
        host = NS(GetHierarchyRootPlayer=lambda: actor, IsDamageDestroyed=lambda: False,
                  GetType=lambda: 'TortillaBag')
        light = NS(IsDamageDestroyed=lambda: False, GetCompEM=lambda: NS())
        state = NS(MountedLight=lambda h: light)
        call = lambda: invoke(NATIVE, 'HCTapedLightRuntime', 'HCToggleCandidate', state, {}, actor, host)
        self.assertIsNone(call())
        actor.FindAttachmentBySlotName = lambda slot: host if slot == 'Back' else None
        self.assertIs(light, call())
        host.GetHierarchyRootPlayer = lambda: NS()
        self.assertIsNone(call())
        host.GetHierarchyRootPlayer = lambda: actor
        actor.IsUnconscious = lambda: True
        self.assertIsNone(call())


class UnverifiedBindingProvenance(unittest.TestCase):
    def test_unverified_wearables_do_not_fabricate_measurement_digest(self):
        from tests.unit.test_taped_light_service import service_rules, SyntheticPort
        env = service_rules()
        binding = SyntheticPort(env).binding
        binding.HostClass = 'TortillaBag'
        binding.LightClass = 'UniversalLight'
        binding.SlotName = 'helmetFlashlight'
        binding.PairId = 'tortilla_universal_mount'
        binding.MeasurementDigest = ''
        self.assertTrue(env['BindingValid'](binding, 'synthetic-build'))
        binding.HostClass = 'UnknownPack'
        self.assertFalse(env['BindingValid'](binding, 'synthetic-build'))


class WearableTransactionConservation(unittest.TestCase):
    def test_mount_replay_remove_share_existing_finite_journal_and_debit(self):
        from tests.unit.test_taped_light_service import service_rules, SyntheticPort
        for host, pair, slot, cross in (
                ('Mich2001Helmet', '', 'helmetFlashlight', False),
                ('TortillaBag', 'tortilla_universal_mount', 'helmetFlashlight', False),
                ('TortillaBag', 'tortilla_universal_cross', 'Chemlight', True)):
            with self.subTest(host=host, pair=pair):
                env = service_rules()
                env['HCTapedPackMounts'] = NS(BindingAllowed=lambda b: True)
                env['HCTapedWearableCatalog'] = NS(Admitted=lambda: True)
                port = SyntheticPort(env)
                binding = port.binding
                binding.HostClass, binding.PairId, binding.SlotName = host, pair, slot
                binding.LightClass, binding.CrossSlot, binding.MeasurementDigest = 'UniversalLight', cross, ''
                state = env['HCTapedLightState']()
                self.assertEqual(env['HCTapedLightCode'].OK, env['Open'](state, port))
                for key, mounting in (('mount', True), ('mount', True), ('remove', False)):
                    self.assertEqual(env['HCTapedLightCode'].OK, env['Run'](state, port, key, mounting))
                self.assertEqual([1], port.consumptions)
                self.assertEqual([True, False], port.moves)
                self.assertEqual(('light', 'battery', 50),
                                 (port.sample.LightId, port.sample.BatteryId, port.sample.BatteryEnergy))


if __name__ == '__main__':
    unittest.main()
