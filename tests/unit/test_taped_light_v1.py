"""W1.3 synthetic action/policy fixtures; never DayZ compilation or client acceptance.

TDD and installed-source records are in test_taped_light_v1_evidence.py.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import body, EArray
from tests.unit.test_group_ui import ui_member
from tests.unit import test_taped_light_service as policy
from tests.unit.test_taped_light_v1_evidence import EVIDENCE

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mods/HollowCountry/scripts'
NATIVE = SCRIPTS / '4_World/Survival/HCTapedLightNative.c'
CATALOG = SCRIPTS / '3_Game/Survival/HCTapedLightCatalog.c'


def member(path, cls, method, state, env, *args):
    text = path.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    if not match:
        raise AssertionError('Missing authored class: ' + cls)
    source = body(text, match.end())
    source = re.sub(r'\bHCTapedLight\w+\b', 'HCGroupNative', source)
    source = source.replace('s_Checked', 'mHCChecked').replace('s_OptIn', 'mHCOptIn')
    return ui_member(source, method, state, dict(env), *args)


class V1AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.server = True
        self.enabled = False
        self.probes = []
        self.gate = NS(mHCChecked=False, mHCOptIn=False)
        self.env = dict(GetGame=lambda:NS(IsServer=lambda:self.server),
                        FileExist=lambda path:self.probes.append(path) or self.enabled,
                        Print=lambda text:None)
        self.gate.Qualified = lambda:member(NATIVE, 'HCTapedLightAdmission', 'Qualified', self.gate, self.env)
        self.gate.LocalAcceptanceOptIn = lambda:member(NATIVE, 'HCTapedLightAdmission', 'LocalAcceptanceOptIn', self.gate, self.env)

    def admitted(self):
        return member(NATIVE, 'HCTapedLightAdmission', 'Admitted', self.gate, self.env)

    def test_client_cannot_probe_or_admit(self):
        self.server = False
        self.enabled = True
        self.assertFalse(self.admitted())
        self.assertFalse(self.gate.LocalAcceptanceOptIn())
        self.assertEqual([], self.probes)
        self.assertFalse(self.gate.mHCChecked)

    def test_server_probe_is_cached_and_never_qualifies(self):
        self.assertFalse(self.admitted())
        self.enabled = True
        self.assertFalse(self.admitted())
        self.assertEqual(['$profile:HollowCountry/acceptance/taped_light.enable'], self.probes)
        self.gate.mHCChecked = False
        self.assertTrue(self.admitted())
        self.enabled = False
        self.assertTrue(self.admitted())
        self.assertFalse(self.gate.Qualified())


class V1CatalogTests(unittest.TestCase):
    def test_exact_pair_and_slot_identity_never_casefolds_or_infers(self):
        row = NS(HostClass='M4A1', LightClass='UniversalLight', SlotName='weaponFlashlight')
        state = NS()
        for host, light, slot, expected in (
            ('M4A1', 'UniversalLight', 'weaponFlashlight', True),
            ('m4a1', 'UniversalLight', 'weaponFlashlight', False),
            ('M4A1', 'universallight', 'weaponFlashlight', False),
            ('M4A1', 'UniversalLight', 'weaponflashlight', False),
            ('Mosin9130', 'UniversalLight', 'weaponFlashlight', False),
        ):
            self.assertEqual(expected, member(CATALOG, 'HCTapedLightCatalog', 'Matches', state, {}, row, host, light, slot))

    def test_shipped_rows_equal_the_current_report_not_a_candidate_list(self):
        data = EVIDENCE
        self.assertEqual('PENDING', data['acceptance'])
        self.assertEqual(26, len(data['pairs']))
        rows = re.findall(r'Add\(rows, "([^"]+)", "([^"]+)", "([^"]+)", "([^"]*)", "([^"]*)"\);', CATALOG.read_text())
        self.assertEqual([(r['host'], r['light'], r['slot'], r['prerequisite_slot'], r['prerequisite_class']) for r in data['pairs']], rows)
        cache = Path.home()/'.cache/hollow-country/experiments'
        classification = cache/'taped-light-probe-004/classification.json'
        observation = cache/'taped-light-probe-006/observations.json'
        if not classification.exists() or not observation.exists():
            self.skipTest('installed read-only probe evidence absent')
        from tools.audit.taped_light_report import build_report
        for key, path in [('classification_sha256', classification), ('observations_sha256', observation)]:
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), data['provenance'][key])
        report = build_report(json.loads(classification.read_text()), json.loads(observation.read_text()))
        self.assertEqual([], report['integrity']['issues'])
        expected = []
        for host in report['hosts']:
            for light, result in host['lights'].items():
                for slot, entry in result.get('slots', {}).items():
                    if host['root'] == 'CfgWeapons' and slot in ('weaponFlashlight', 'pistolFlashlight') and entry['verdict'] == 'server_qualified':
                        prerequisite = entry['evidence']['prerequisite'] or {}
                        expected.append((host['class'], light, slot, prerequisite.get('slot', ''), prerequisite.get('handguard', '')))
        self.assertEqual(expected, rows)
        self.assertNotIn('R12', [r[0] for r in rows])


class V1CargoReceiptTests(unittest.TestCase):
    setUp = policy.TapedLightTests.setUp
    run_op = policy.TapedLightTests.run_op

    def test_mount_then_remove_into_cargo_preserves_identity_and_spends_once(self):
        self.port.binding.ReturnToCargo = True
        before = copy.deepcopy(self.port.sample)
        self.assertEqual(self.code.OK, self.run_op())
        transfer = self.port.Transfer
        def to_cargo(binding, mounting):
            result = transfer(binding, mounting)
            if not mounting:
                self.port.sample.Place = 0
            return result
        self.port.Transfer = to_cargo
        self.assertEqual(self.code.OK, self.run_op('remove-cargo', False))
        self.assertEqual([True, False], self.port.moves)
        self.assertEqual([1], self.port.consumptions)
        for field in ('LightId', 'BatteryId', 'LightHealth', 'BatteryHealth', 'BatteryEnergy'):
            self.assertEqual(getattr(before, field), getattr(self.port.sample, field))

    def test_destination_policy_is_part_of_the_replay_binding(self):
        self.port.binding.ReturnToCargo = True
        self.assertEqual(self.code.OK, self.run_op())
        self.port.binding.ReturnToCargo = False
        self.assertEqual(self.code.BLOCKED, self.run_op('changed-return-policy', False))


class V1HookTests(unittest.TestCase):
    def test_registered_native_actions_call_service_only_on_server(self):
        action = (SCRIPTS/'4_World/Actions/HCTapedLightActions.c').read_text()
        for name in ('HCActionMountTapedLight', 'HCActionRemoveTapedLight'):
            self.assertIn('actions.Insert(' + name + ')', action)
            self.assertIn('AddAction(' + name + ')', action)
        self.assertIn('modded class Weapon_Base', action)
        self.assertIn('override void OnExecuteServer(ActionData action_data)', action)
        self.assertNotIn('OnExecuteClient', action)
        native = NATIVE.read_text()
        self.assertIn('HCTapedLightService.Run(', native)
        self.assertIn('GameInventory.AddInventoryReservation(', native)
        self.assertIn('GameInventory.ClearInventoryReservation(', native)
        self.assertNotIn('CreateObject', native + action)
        self.assertNotIn('SetPosition', native + action)
        self.assertNotIn('SwitchOn(', native + action)
        self.assertNotIn('SwitchOff(', native + action)


def native_member(cls, method, state, env, *args):
    text = NATIVE.read_text()
    match = re.search(r'class ' + cls + r'\b[^\{]*\{', text)
    source = body(text, match.end())
    source = source.replace('array<EntityAI> items = new array<EntityAI>', 'HCGroupNative items = NewItems()')
    source = re.sub(r'\b(?:ItemBase|EntityAI|InventoryLocation|HCTapedLight\w+)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
    source = source.replace('new InventoryLocation', 'new HCGroupLocation')
    source = source.replace('static ItemBase ' + method, 'static int ' + method)
    return ui_member(source, method, state, dict(env), *args)


class V1NativeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.actor = NS()
        self.host = NS()
        self.held = self.host
        self.owner = self.actor
        self.host.GetHierarchyRootPlayer = lambda:self.owner
        self.host.IsDamageDestroyed = lambda:False
        self.actor.IsAlive = lambda:True
        self.actor.IsUnconscious = lambda:False
        self.actor.IsInVehicle = lambda:False
        self.actor.GetItemInHands = lambda:self.held

    def test_held_scope_rejects_remote_or_ground_host_and_hands_change(self):
        def held():
            return native_member('HCTapedLightRuntime', 'Held', NS(), {}, self.actor, self.host)
        self.assertTrue(held())
        self.owner = None
        self.assertFalse(held())
        self.owner = NS()
        self.assertFalse(held())
        self.owner = self.actor
        self.held = None
        self.assertFalse(held())

    def test_loose_selection_skips_unevidenced_attached_foreign_and_on_lights(self):
        items = EArray()
        self.actor.GetInventory = lambda:NS(EnumerateInventory=lambda mode,out:out.extend(items) or True)
        env = dict(NewItems=EArray, ItemBase=NS(Cast=lambda item:item),
                   InventoryTraversalType=NS(PREORDER=1), InventoryLocationType=NS(CARGO=3),
                   HCTapedLightV1Qualification=NS(Row=lambda host,item:item.known))
        class Location:
            def GetType(self): return self.place
        env['HCGroupLocation'] = Location
        def candidate(known=True, place=3, owner=None, on=False):
            item = NS(known=known, IsDamageDestroyed=lambda:False,
                      GetHierarchyRootPlayer=lambda:owner or self.actor,
                      GetCompEM=lambda:NS(IsSwitchedOn=lambda:on))
            def locate(location):
                location.place = place
                return True
            item.GetInventory = lambda:NS(GetCurrentInventoryLocation=locate)
            return item
        wanted = candidate()
        items.extend([candidate(known=False), candidate(place=1), candidate(owner=NS()), candidate(on=True), wanted])
        self.assertIs(wanted, native_member('HCTapedLightRuntime', 'LooseLight', NS(), env, self.actor, self.host))
        items.remove(wanted)
        self.assertIsNone(native_member('HCTapedLightRuntime', 'LooseLight', NS(), env, self.actor, self.host))

    def test_client_cannot_acquire_native_inventory_reservations(self):
        calls = []
        inventory = NS(HasInventoryReservation=lambda *args:False,
                       AddInventoryReservation=lambda *args:calls.append(args) or True,
                       c_InventoryReservationTimeoutMS=5000)
        state = NS(mHCReserved=EArray())
        env = dict(GetGame=lambda:NS(IsServer=lambda:False), GameInventory=inventory)
        self.assertFalse(native_member('HCTapedLightV1Custody', 'Reserve', state, env, NS(), None))
        self.assertEqual([], calls)


class V1ReservedDestinationTests(unittest.TestCase):
    def test_owned_destination_is_used_without_reselecting_the_only_free_cargo_cell(self):
        # SYNTHETIC native inventory: ordinary free-location search excludes the
        # cell we just reserved. It must not be called again while in custody.
        calls = []
        actor = NS(GetInventory=lambda:NS(FindFreeLocationFor=lambda *args:calls.append('free') or False))
        light = NS(GetType=lambda:'TLRLight', GetHierarchyRootPlayer=lambda:actor,
                   GetInventory=lambda:NS(GetCurrentInventoryLocation=lambda location:True))
        host = NS(GetType=lambda:'CZ75', GetHierarchyRootPlayer=lambda:actor,
                  GetInventory=lambda:NS(FindAttachment=lambda slot:light))
        destination = NS(GetType=lambda:3, GetParent=lambda:actor)
        state = NS(mHCActor=actor, mHCHost=host, mHCLight=light, mHCHeld=True,
                   mHCCustody=NS(Destination=lambda:destination), ActorAllowed=lambda:True)
        source = (SCRIPTS/'4_World/Survival/HCTapedLightService.c').read_text()
        match = re.search(r'class HCTapedLightPort\s*\{', source)
        source = body(source, match.end())
        source = re.sub(r'\b(?:InventoryLocation|EntityAI)\s+(?=\w+\s*[=;])', 'HCGroupNative ', source)
        source = source.replace('new InventoryLocation', 'new HCGroupLocation')
        env = dict(HCGroupLocation=lambda:NS(), InventorySlots=NS(GetSlotIdFromString=lambda slot:17),
                   InventoryLocationType=NS(ATTACHMENT=1,CARGO=3), FindInventoryLocationType=NS(CARGO=3),
                   GameInventory=NS(LocationCanMoveEntitySyncCheck=lambda src,dst:calls.append(dst) or True))
        binding = NS(HostClass='CZ75',LightClass='TLRLight',SlotName='pistolFlashlight',ReturnToCargo=True)
        self.assertTrue(ui_member(source, 'CanTransfer', state, env, binding, False))
        self.assertEqual([destination], calls)
