"""#211: execute authored raid guards; all engine/Expansion objects are synthetic.

Range arithmetic is real Python arithmetic; geometry, native groups, attendance
and provider availability are explicit fixtures. These tests prove authored
branch behavior only, never DayZ perception, inventory or route execution.
"""
import re
import unittest
from types import SimpleNamespace as NS

from tests.unit.test_admin_test_kit import ROOT, authored_method, base_scope, compile_authored
from tests.unit.test_group_server import EArray, execute_member

ADAPTER = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'
HELPERS = ('HCPartyAllowed', 'HCLiveParty', 'HCPerceive', 'HCVisible', 'HCReady',
           'HCCancel', 'HCSense', 'HCReserve', 'HCWalkTo', 'HCTryLockpick', 'HCFindLoot', 'HCTakeLoot')


def invoke(name, receiver, scope, *args, cls='HCXAIBaseRaid'):
    """Use the existing foreach translator, adapting declarations/bindings only."""
    params, body = authored_method(ADAPTER, cls, name, modded=False)
    body = body.replace('.Patrol.m_Group', '.Patrol.group')
    body = re.sub(r'array<[^>]+>', 'HCGroupArray', body)
    body = re.sub(r'\b(?:HCXAISiteDirector|eAIGroup|eAIBase|Object|ItemBase|Building|HCBuildingClaim)\s+(?=\w+\s*[=;])',
                  'HCGroupValue ', body)
    for helper in HELPERS:
        body = re.sub(r'(?<![.\w])' + helper + r'\(', 'self.' + helper + '(', body)
    kind = 'void' if name in ('HCSense', 'HCCancel', 'HCStep', 'HCVisitStep', 'HCWarned') else 'bool'
    return execute_member(kind + ' ' + name + '(' + params + ') {' + body + '}',
                          name, dict(scope, HCGroupArray=EArray), receiver, *args)


class Entity(NS):
    """Native handles compare by identity, not by matching fixture fields."""
    def __eq__(self, other): return self is other
    def __ne__(self, other): return self is not other


class Fixture:
    def __init__(self, visitor=False):
        self.calls = []
        self.visible = True
        self.candidate = True
        self.used = False
        self.owned = False
        self.unattended = True
        self.budget = True
        self.component = 3
        self.party = Entity(route=EArray([(1, 0, 1), (2, 0, 2)]), mode=7, combat=False)
        self.actor = Entity(alive=True, pending=False, unconscious=False)
        self.actor.GetPosition = lambda: (0, 0, 0)
        self.actor.GetGroup = lambda: self.party
        self.actor.IsAlive = lambda: self.actor.alive
        self.actor.IsPendingDeletion = lambda: self.actor.pending
        self.actor.IsUnconscious = lambda: self.actor.unconscious
        self.party.IsInCombat = lambda: self.party.combat
        self.party.Count = lambda: 1
        self.party.GetMember = lambda index: self.actor
        # Deliberately return the live array: HCWalkTo must copy before clearing.
        self.party.GetWaypoints = lambda: self.party.route
        self.party.GetWaypointBehaviour = lambda: self.party.mode
        self.party.ClearWaypoints = self.party.route.Clear
        self.party.AddWaypoint = self.party.route.Insert
        self.party.SetWaypointBehaviour = lambda mode: setattr(self.party, 'mode', mode)
        self.site = Entity(ProposalId='leased-party', ProviderFaction='HCTravellers' if visitor else 'HCRaiders',
                           Patrol=NS(group=self.party))
        self.states = EArray([self.site])
        self.nearby, self.cargos = EArray(), EArray()
        self.crate = Entity(kind='storage', position=(5, 0, 0), pending=False, ref='crate')
        self.crate.GetPosition = lambda: self.crate.position
        self.crate.IsPendingDeletion = lambda: self.crate.pending
        self.house = Entity(kind='building', pending=False, doors=1, door_index=0)
        self.house.IsPendingDeletion = lambda: self.house.pending
        self.house.GetDoorCount = lambda: self.house.doors
        self.house.GetDoorSoundPos = lambda door: (5, 0, 0)
        self.house.GetDoorIndex = lambda component: self.house.door_index
        self.compatible = True
        self.claimed = True
        self.claims = NS(HCHoldsClaim=self.holds_claim)
        self.camp = Entity(Position=(0, 0, 0), FireRef='fire', GroupId=NS(ToInt=lambda: 17),
                           LastProbe=1, LastVisit=1)
        self.scan = NS(Crates=EArray([self.crate]))
        self.state = NS(m_Config=NS(NoticeRangeMeters=10, SourceRangeMeters=8,
            MaxObjects=2, MaxDoors=2, MaxRouteNodes=4, MaxPlayers=2,
            WarningSeconds=9, RaidSeconds=90),
            m_Site=self.site, m_Actor=self.actor, m_Seen=None, m_Source=None,
            m_Building=None, m_Door=-1, m_Component=-1, m_Point=(5, 0, 0),
            m_PartyCursor=0, m_ObjectCursor=0, m_DoorCursor=0,
            m_Reserved=False, m_Walking=False, m_Busy=False, m_Group=None,
            m_Original=EArray(), m_Behaviour=None, m_Camp=self.camp,
            m_Owner=Entity(Commit=lambda now: True), m_Inventory=None, m_Due=10, m_Ends=100)
        self.scope = base_scope(
            HCXAISiteDirector=NS(Active=lambda: NS(States=lambda: self.states)),
            HCW38SituationRuntime=NS(HCCandidate=lambda site: self.candidate and site is not None,
                                     HCUsed=lambda lease: self.used),
            HCBaseRaid=NS(HCOwns=lambda lease: self.owned, HCEnabled=lambda: True,
                          HCUnattended=self.attendance),
            HCWorldMaterializer=NS(MAX_PLAYERS=6), eAIBase=NS(Cast=lambda value: value),
            ItemBase=NS(Cast=lambda value: value if value and value.kind == 'storage' else None),
            Building=NS(Cast=lambda value: value if value and value.kind == 'building' else None),
            HCCampScan=NS(StorageItem=lambda item: True, RefOf=lambda item: item.ref),
            HCBuildingClaim=NS(HCDoor=lambda *args: self.compatible,
                               HCGet=lambda: self.claims, HCIdentity=lambda house: 'house-id'),
            GetGame=lambda: NS(GetObjectsAtPosition3D=self.objects),
            HCServer=NS(HCTickWork=lambda: NS(HCTakeFor=lambda *args: self.budget)),
            HCUnitBudget=NS(HC_WORK_BASE_RAID=12),
            HCCampProbes=NS(HCEnabled=lambda: True, HCVisitorsEnabled=lambda: True),
            eAIWaypointBehavior=NS(ONCE='ONCE'), Print=lambda line: None)
        for helper in ('HCPartyAllowed', 'HCLiveParty', 'HCPerceive', 'HCWalkTo', 'HCReserve', 'HCCancel'):
            helper_cls = 'HCXAIBaseRaid'
            if visitor and helper == 'HCPartyAllowed':
                helper_cls = 'HCAdminVisitorParty'
            setattr(self.state, helper, lambda *args, helper=helper, helper_cls=helper_cls:
                    self.run(helper, *args, cls=helper_cls))
        self.state.HCReady = lambda: True
        self.state.HCVisible = self.geometry
        for effect in ('HCTryLockpick', 'HCFindLoot', 'HCTakeLoot'):
            setattr(self.state, effect, lambda effect=effect: self.calls.append(effect))

    def run(self, name, *args, cls='HCXAIBaseRaid'):
        return invoke(name, self.state, self.scope, *args, cls=cls)

    def objects(self, point, radius, nearby, cargos):
        self.calls.append('objects')
        nearby.extend(self.nearby)
        cargos.extend(self.cargos)

    def geometry(self, target, point):
        self.calls.append('geometry')
        self.state.m_Component = self.component
        return self.visible

    def attendance(self, *args):
        self.calls.append('attendance')
        return self.unattended

    def holds_claim(self, group, identity):
        self.calls.append(('claim', group, identity))
        return self.claimed


class PerceptionGuards(unittest.TestCase):
    def test_storage_requires_current_range_and_geometry_and_seen_rechecks_them(self):
        for position, visible, expected in (((10, 0, 0), True, True),
                ((10.01, 0, 0), True, False), ((5, 0, 0), False, False)):
            with self.subTest(position=position, visible=visible):
                f = Fixture()
                f.crate.position, f.visible = position, visible
                f.nearby.append(f.crate)
                f.run('HCSense')
                self.assertIs(f.crate if expected else None, f.state.m_Seen)
                self.assertEqual(expected, bool(f.run('HCSeen', f.camp, f.scan)))
                if expected:
                    f.visible = False
                    self.assertFalse(f.run('HCSeen', f.camp, f.scan))
                if position[0] > 10:
                    self.assertNotIn('geometry', f.calls)

    def test_sense_clears_stale_targets_and_refuses_unavailable_or_owned_parties(self):
        for guard in ('no-states', 'candidate', 'faction', 'used', 'owned', 'combat', 'dead', 'overflow'):
            with self.subTest(guard=guard):
                f = Fixture()
                f.state.m_Seen = f.state.m_Source = f.crate
                f.state.m_Building, f.state.m_Door = f.house, 0
                if guard == 'no-states': f.states.clear()
                elif guard == 'candidate': f.candidate = False
                elif guard == 'faction': f.site.ProviderFaction = 'HCTravellers'
                elif guard == 'used': f.used = True
                elif guard == 'owned': f.owned = True
                elif guard == 'combat': f.party.combat = True
                elif guard == 'dead': f.actor.alive = False
                elif guard == 'overflow': f.party.Count = lambda: 7
                f.run('HCSense')
                self.assertEqual((None, None, None, -1),
                    (f.state.m_Seen, f.state.m_Source, f.state.m_Building, f.state.m_Door))
                self.assertEqual([], f.calls)

    def test_sense_bounds_snapshot_and_examines_one_object_per_tick(self):
        f = Fixture()
        f.nearby.extend([None, f.crate])
        f.run('HCSense')
        self.assertIsNone(f.state.m_Seen)
        f.run('HCSense')
        self.assertIs(f.crate, f.state.m_Seen)
        for overflow in ('objects', 'cargo'):
            f = Fixture()
            f.nearby.append(f.crate)
            (f.nearby if overflow == 'objects' else f.cargos).extend([f.crate] * 3)
            f.run('HCSense')
            self.assertIsNone(f.state.m_Seen)
            self.assertEqual(['objects'], f.calls)

    def test_storage_seen_requires_camp_membership_and_live_unreserved_party(self):
        f = Fixture()
        f.nearby.append(f.crate)
        f.run('HCSense')
        self.assertTrue(f.run('HCSeen', f.camp, f.scan))
        f.scan.Crates.clear()
        self.assertFalse(f.run('HCSeen', f.camp, f.scan))
        f.camp.FireRef = 'crate'
        self.assertTrue(f.run('HCSeen', f.camp, f.scan))
        for field, value in (('m_Reserved', True), ('m_Actor', None), ('m_Seen', None)):
            saved = getattr(f.state, field)
            setattr(f.state, field, value)
            self.assertFalse(f.run('HCSeen', f.camp, f.scan))
            setattr(f.state, field, saved)
        self.assertFalse(f.run('HCSeen', None, f.scan))
        self.assertFalse(f.run('HCSeen', f.camp, None))

    def test_door_sighting_requires_compatible_door_component_and_live_claim(self):
        for guard in ('ok', 'incompatible', 'wall', 'wrong-door', 'too-many-doors', 'occluded'):
            with self.subTest(guard=guard):
                f = Fixture()
                f.nearby.append(f.house)
                if guard == 'incompatible': f.compatible = False
                elif guard == 'wall': f.component = -1
                elif guard == 'wrong-door': f.house.door_index = 1
                elif guard == 'too-many-doors': f.house.doors = 3
                elif guard == 'occluded': f.visible = False
                f.run('HCSense')
                self.assertEqual(guard == 'ok', bool(f.state.m_Seen))
                self.assertEqual(guard == 'ok', bool(f.run('HCSeen', f.camp, f.scan)))
                if guard == 'ok':
                    self.assertIn(('claim', 17, 'house-id'), f.calls)
                    f.claimed = False
                    self.assertFalse(f.run('HCSeen', f.camp, f.scan))
                    f.claimed, f.house.door_index = True, 1
                    self.assertFalse(f.run('HCSeen', f.camp, f.scan))
                    f.house.door_index, f.claims = 0, None
                    self.assertFalse(f.run('HCSeen', f.camp, f.scan))


class RouteRestoration(unittest.TestCase):
    def test_raid_and_visit_interruptions_restore_original_route_and_behavior(self):
        for cls, step in (('HCXAIBaseRaid', 'HCStep'), ('HCAdminVisitorParty', 'HCVisitStep')):
            for interruption in ('attendance-return', 'observer-return', 'cancel', 'expiry', 'combat'):
                with self.subTest(cls=cls, interruption=interruption):
                    f = Fixture(visitor=cls == 'HCAdminVisitorParty')
                    original = list(f.party.route)
                    f.nearby.append(f.crate)
                    f.run('HCSense')
                    self.assertTrue(f.run('HCSeen', f.camp, f.scan))
                    if cls == 'HCXAIBaseRaid':
                        self.assertTrue(f.run('HCReserve', f.state.m_Owner, f.camp, 1))
                        f.run('HCWarned', f.camp, 1)
                    else:
                        self.assertTrue(f.run('HCVisit', f.state.m_Owner, f.camp, 10, cls=cls))
                    self.assertTrue(f.run('HCWalkTo', (5, 0, 0)))
                    self.assertTrue(f.run('HCWalkTo', (6, 0, 0)))
                    self.assertEqual([(6, 0, 0)], f.party.route)
                    self.assertEqual('ONCE', f.party.mode)
                    # Both attendance and observer vetoes are returned by the
                    # shared HCUnattended boundary (covered in test_bases_raid).
                    if interruption in ('attendance-return', 'observer-return'):
                        f.unattended = False
                    elif interruption == 'combat': f.party.combat = True
                    if interruption == 'cancel': f.run('HCCancel')
                    else: f.run(step, 100 if interruption == 'expiry' else 20, cls=cls)
                    self.assertEqual(original, f.party.route)
                    self.assertEqual(7, f.party.mode)
                    self.assertFalse(f.state.m_Reserved)
                    self.assertFalse(f.state.m_Walking)
                    self.assertEqual([], f.state.m_Original)
                    for field in ('m_Group', 'm_Camp', 'm_Owner', 'm_Inventory', 'm_Seen',
                                  'm_Source', 'm_Building', 'm_Site', 'm_Actor'):
                        self.assertIsNone(getattr(f.state, field), field)
                    self.assertNotIn('HCTakeLoot', f.calls)
                    f.run('HCCancel')  # Idempotent; no duplicated original nodes.
                    self.assertEqual(original, f.party.route)

    def test_invalid_route_and_changed_group_do_not_replace_waypoints(self):
        for route in (None, EArray(), EArray([(0, 0, 0)] * 5)):
            f = Fixture()
            f.party.GetWaypoints = lambda: route
            original = list(f.party.route)
            self.assertFalse(f.run('HCWalkTo', (5, 0, 0)))
            self.assertEqual(original, f.party.route)
        f = Fixture()
        self.assertTrue(f.run('HCWalkTo', (5, 0, 0)))
        other = Entity(route=EArray([(9, 0, 9)]))
        other.GetWaypoints = lambda: other.route
        f.site.Patrol.group = other
        f.actor.GetGroup = lambda: other
        self.assertFalse(f.run('HCWalkTo', (6, 0, 0)))
        f.run('HCCancel')
        self.assertEqual([(1, 0, 1), (2, 0, 2)], f.party.route)
        self.assertEqual([(9, 0, 9)], other.route)


class CustodyGuards(unittest.TestCase):
    def test_custody_requires_exact_reserved_actor_source_live_party_range_and_sight(self):
        for guard in ('ok', 'unreserved', 'actor', 'source', 'camp', 'dead', 'deleted',
                      'unconscious', 'group', 'candidate', 'source-range', 'notice-range', 'occluded'):
            with self.subTest(guard=guard):
                f = Fixture()
                f.state.m_Reserved, f.state.m_Source = True, f.crate
                actor, source = f.actor, f.crate
                if guard == 'unreserved': f.state.m_Reserved = False
                elif guard == 'actor': actor = Entity()
                elif guard == 'source': source = Entity()
                elif guard == 'camp': f.state.m_Camp = None
                elif guard == 'dead': f.actor.alive = False
                elif guard == 'deleted': f.actor.pending = True
                elif guard == 'unconscious': f.actor.unconscious = True
                elif guard == 'group': f.site.Patrol.group = Entity()
                elif guard == 'candidate': f.candidate = False
                elif guard == 'source-range': f.crate.position = (8.01, 0, 0)
                elif guard == 'notice-range': f.actor.GetPosition = lambda: (20, 0, 0)
                elif guard == 'occluded': f.visible = False
                self.assertEqual(guard == 'ok', bool(f.run('HCCustodyAllowed', actor, source)))
                if guard not in ('ok', 'occluded'):
                    self.assertNotIn('geometry', f.calls)
                if guard == 'ok':
                    f.crate.position = (8, 0, 0)
                    self.assertTrue(f.run('HCCustodyAllowed', actor, source))

    def test_inventory_guard_composes_parent_lease_custody_and_attendance_checks(self):
        for guard in ('ok', 'parent', 'source', 'lease', 'provider', 'custody', 'attendance'):
            with self.subTest(guard=guard):
                f = Fixture()
                f.state.m_Reserved, f.state.m_Source = True, f.crate
                inventory = NS(Actor=f.actor, Source=f.crate, LeaseId='leased-party',
                               HCTheftOwner=f.state.m_Owner, HCTheftCamp=f.camp)
                row = Entity(LeaseId='leased-party')
                parent_rows = []
                if guard == 'source': inventory.Source = None
                elif guard == 'lease': inventory.LeaseId = 'unleased-party'
                elif guard == 'custody': inventory.Actor = Entity()
                elif guard == 'attendance': f.unattended = False
                port = NS(HCCustodyAllowed=lambda actor, source: f.run('HCCustodyAllowed', actor, source))
                scope = base_scope(super=NS(HCPartyCurrent=lambda value:
                    parent_rows.append(value) or guard != 'parent'),
                    HCBaseRaid=NS(HCOwns=lambda lease: f.run('HCOwns', lease),
                                  HCGet=lambda: None if guard == 'provider' else port,
                                  HCUnattended=f.attendance))
                fn = compile_authored(ADAPTER, 'HCXAIBaseRaidInventory', 'HCPartyCurrent', scope,
                    modded=False, fields=('Actor', 'Source', 'LeaseId', 'HCTheftOwner', 'HCTheftCamp'))
                self.assertEqual(guard == 'ok', bool(fn(inventory, row)))
                self.assertEqual([row], parent_rows)
                if guard not in ('ok', 'attendance'):
                    self.assertNotIn('attendance', f.calls)

    def test_visitors_never_have_stock_custody(self):
        f = Fixture()
        self.assertFalse(f.run('HCCustodyAllowed', f.actor, f.crate, cls='HCAdminVisitorParty'))


if __name__ == '__main__':
    unittest.main()
