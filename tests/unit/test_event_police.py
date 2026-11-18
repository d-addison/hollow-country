"""Police source repair, task/plan trace: #33/#46, user contract 2026-11-17.

Given empty CE at boot, bind finite journaled cargo for recovery/delivery/salvage;
Given later local infected, bind nearest deterministically on existing roster budget.
Plan: reuse HCEventCacheSpawner + HCEventRewardLedger, preserve source-review gates,
never replenish spent grants, preserve registrations, keep production acceptance pending.
All engine/storage fixtures below are EXPLICIT SYNTHETIC; no DayZ behavior proven.

Actual RED, before source implementation (2026-11-17):
Command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
 tests.unit.test_event_police.PoliceBinding.test_empty_ce_binds_three_distinct_items_from_one_journaled_barrel
 tests.unit.test_event_police.PoliceBinding.test_infected_late_population_chooses_nearest_and_stable_id_tie -v
Verbatim failure output:
======================================================================
FAIL: test_empty_ce_binds_three_distinct_items_from_one_journaled_barrel (tests.unit.test_event_police.PoliceBinding.test_empty_ce_binds_three_distinct_items_from_one_journaled_barrel)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/v1-police/tests/unit/test_event_police.py", line 51, in test_empty_ce_binds_three_distinct_items_from_one_journaled_barrel
    self.assertTrue(self.binder.Bind(self.observer, mission), mission.Id)
AssertionError: False is not true : coastal-police-source-1

======================================================================
FAIL: test_infected_late_population_chooses_nearest_and_stable_id_tie (tests.unit.test_event_police.PoliceBinding.test_infected_late_population_chooses_nearest_and_stable_id_tie)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/code/hc-worktrees/v1-police/tests/unit/test_event_police.py", line 141, in test_infected_late_population_chooses_nearest_and_stable_id_tie
    self.assertTrue(self.binder.Bind(self.observer, mission))
AssertionError: False is not true

----------------------------------------------------------------------
Ran 2 tests in 0.356s

FAILED (failures=2)

Additional regression RED assertions (each failing before its source correction):
  Terrain/log retries: AssertionError: 5 not less than or equal to 1
  Closed native barrel: AssertionError: False is not true
GREEN command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest
 tests.unit.test_event_integration tests.unit.test_event_runtime
 tests.unit.test_event_sites tests.unit.test_event_police -v
Native compilation, field/door clearance, actual cargo transitions and two-client
replication remain PENDING; no missing engine experiment is accepted here.
"""
import copy
from types import SimpleNamespace as N
import unittest

from tests.unit import test_event_sites as sites
from tests.unit import test_event_runtime as runtime
from tests.unit import test_event_integration as integration
from tests.unit.test_group_server import EArray


class PoliceBinding(sites.Fixture):
    def setUp(self):
        super().setUp()
        native = runtime.NativeObservationTests()
        native.setUp()
        self.observer = native.o
        self.e.update({k: v for k, v in native.e.items() if k in (
            'HCEventNativeObserver', 'HCEventNativeLease', 'HCEventDwell')})
        # Authored observer methods share native.e globals, including the game port.
        native.e.update(self.e)
        self.e = native.e
        self.e['GetGame'] = lambda: self.game
        self.e['HCEventQualification'] = N(Admitted=lambda: True)
        self.e['HCEventPoliceRewardIO'] = sites.FakeIO
        self.e['ZombieBase'] = N(Cast=lambda obj: obj if obj.kind == 'SyntheticZombie' else None)
        self.objects = []
        self.scans = []
        def query(anchor, radius, objects, proxies):
            self.scans.append((anchor, radius))
            objects.extend(self.objects)
        self.game.GetObjectsAtPosition3D = query
        sites.load('HCEventRewards.c', 'HCEventRewardPools', self.e)
        sites.load('HCEventRewards.c', 'HCEventRewardLedger', self.e)
        self.spawner = sites.load('HCEventRewardCache.c', 'HCEventCacheSpawner', self.e)
        self.binder = sites.load('HCEventWorldBinding.c', 'HCEventWorldBinding', self.e)
        self.site = self.e['HCEventSites'].ChernarusPlus()[0]
        # Synthetic: mapgrouppos gives the station's model origin, which stands above
        # the ground (stock neighbours sit ~5 m lower), so ground is below Source.
        self.game.height = self.site.Position[1] - 7
        self.nav_calls = []
        self.nav_ok = True
        def sample(wanted, radius):
            self.nav_calls.append((list(wanted), radius))
            if not self.nav_ok:
                return self.e['vector'].Zero
            return list(wanted)
        self.e['HCEventPoliceNav'] = N(Sample=sample)
        self.e['vector'].Zero = [0.0, 0.0, 0.0]
        self.missions = {m.Family: m for m in self.e['HCEventRoster'].Build(self.site, False)}

    def test_native_barrel_starts_closed_and_must_be_opened_before_cargo(self):
        original = self.game.CreateObjectEx
        def closed_barrel(kind, position, flags):
            cache = original(kind, position, flags)
            cache.opened = False
            cache.synced = False
            cache.Open = lambda: setattr(cache, 'opened', True)
            cache.SetSynchDirty = lambda: setattr(cache, 'synced', True)
            cargo = cache.GetInventory().CreateEntityInCargo
            cache.GetInventory = lambda: N(CreateEntityInCargo=lambda name:
                cargo(name) if cache.opened else None)
            return cache
        self.game.CreateObjectEx = closed_barrel
        self.assertTrue(self.binder.Bind(self.observer, self.missions[1]))
        self.assertTrue(self.game.created[0].opened)
        self.assertTrue(self.game.created[0].synced)
        self.assertEqual(3, len(self.game.created[0].contents))

    def test_empty_ce_binds_three_distinct_items_from_one_journaled_barrel(self):
        for family in (1, 2, 4):
            mission = self.missions[family]
            self.assertTrue(self.binder.Bind(self.observer, mission), mission.Id)
            self.assertTrue(self.observer.Ready(mission), mission.Id)
        self.assertEqual([], self.scans, 'police supplies do not depend on random CE')
        self.assertEqual(1, len(self.game.created))
        barrel = self.game.created[0]
        self.assertEqual('Barrel_Green', barrel.kind)
        self.assertCountEqual(['BandageDressing', 'SodaCan_Cola', 'MetalWire'], barrel.contents)
        self.assertEqual([self.site.Position[0] + 6, self.game.height,
                          self.site.Position[2] + 6], barrel.position)
        self.assertEqual(6, self.nav_calls[0][1], 'outdoor navmesh point sampled near the anchor')
        targets = [self.observer.Target(self.missions[f].Id) for f in (1, 2, 4)]
        self.assertEqual(3, len({id(t.Item) for t in targets}))
        self.assertIs(barrel, targets[1].DeliveryContainer)
        self.assertEqual(1, len([n for n in self.spawner.PoliceLedger().m_IO.files if '-grant-' in n]))
        for _ in range(10):
            for family in (1, 2, 4):
                self.assertTrue(self.binder.Bind(self.observer, self.missions[family]))
        self.assertEqual(1, len(self.game.created))

    def test_police_objectives_require_carriage_or_attributed_delivery(self):
        player = runtime.Handle(position=list(self.site.Position))
        for family in (1, 2, 4):
            mission = self.missions[family]
            self.assertTrue(self.binder.Bind(self.observer, mission))
            lease = 'synthetic:' + str(family)
            self.assertTrue(self.observer.Prepare(lease, mission))
            run = N(Lease=lease, Objective=mission)
            self.assertIsNone(self.observer.Observe(run, player, 100))
            target = self.observer.Target(mission.Id)
            target.Item.owner = player
            target.Item.parent = None
            if family == 2:
                self.assertIsNone(self.observer.Observe(run, player, 101))
                target.Item.owner = None
                target.Item.parent = target.DeliveryContainer
                self.observer.RecordDelivery(lease, target.Item, player, target.DeliveryContainer)
            self.assertTrue(self.observer.Observe(run, player, 102).Observed)
            self.assertTrue(self.binder.Bind(self.observer, mission))
            self.assertIs(target, self.observer.Target(mission.Id), 'leased target is retained')

    def test_two_sites_use_separate_grants_without_spending_supply_cache_pool(self):
        ordinary = self.ledger()
        self.e['HCEventRewards'] = N(Ledger=lambda: ordinary)
        for site in self.e['HCEventSites'].ChernarusPlus():
            self.game.height = site.Position[1] - 7
            for mission in self.e['HCEventRoster'].Build(site, False):
                if mission.Family in (1, 2, 4):
                    self.assertTrue(self.binder.Bind(self.observer, mission))
        self.assertEqual(2, len(self.game.created))
        self.assertEqual(0, len(ordinary.m_Granted))
        self.assertEqual(2, len(self.spawner.PoliceLedger().m_Granted))

    def test_failed_creation_stays_spent(self):
        self.game.create_ok = False
        self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.game.create_ok = True
        for family in (1, 2, 4):
            self.assertFalse(self.binder.Bind(self.observer, self.missions[family]))
        self.assertEqual([], self.game.created)

    def test_disabled_gate_and_unreviewed_operator_changes_never_spawn(self):
        self.e['HCEventSitesGate'] = N(Admitted=lambda: False)
        self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.e['HCEventSitesGate'] = N(Admitted=lambda: True)
        changed = copy.deepcopy(self.missions[1]); changed.Source[0] += 100
        self.assertFalse(self.binder.Bind(self.observer, changed))
        self.assertEqual([], self.game.created)

    def test_failed_journal_never_spawns(self):
        ledger = self.spawner.PoliceLedger()
        self.game.io = ledger.m_IO
        ledger.m_IO.fail_write = True
        self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual([], self.game.created)

    def test_bad_terrain_retries_keep_diagnostics_bounded_and_do_not_spend(self):
        self.game.height = self.site.Position[1] + 40
        for _ in range(5):
            self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertLessEqual(len(self.logs), 1)
        self.assertEqual([], self.game.created)
        self.game.height = self.site.Position[1] - 7
        self.assertTrue(self.binder.Bind(self.observer, self.missions[1]))

    def test_station_origin_above_ground_places_on_outdoor_navmesh(self):
        # Observed 2026-11-17 on the local server: police_supply_unavailable at both
        # stations while the three ground-level caches spawned.
        for drop in (7, 11):
            self.setUp()
            self.game.height = self.site.Position[1] - drop
            self.assertTrue(self.binder.Bind(self.observer, self.missions[1]), drop)
            barrel = self.game.created[0]
            self.assertLessEqual(self.e['vector'].DistanceSq(barrel.position, self.site.Position), 15 * 15)

    def test_ground_far_below_or_above_origin_refuses_without_spending(self):
        for height in (self.site.Position[1] - 13, self.site.Position[1] + 4):
            self.game.height = height
            self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual([], self.game.created)
        self.assertEqual(0, len([n for n in self.spawner.PoliceLedger().m_IO.files if '-grant-' in n]))

    def test_navmesh_refusal_does_not_spend_and_retries(self):
        self.nav_ok = False
        for _ in range(3):
            self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual([], self.game.created)
        self.assertEqual(0, len([n for n in self.spawner.PoliceLedger().m_IO.files if '-grant-' in n]))
        self.nav_ok = True
        self.assertTrue(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual(1, len(self.game.created))

    def test_creation_follows_durable_grant_and_partial_cargo_never_refills(self):
        ledger = self.spawner.PoliceLedger()
        self.game.io = ledger.m_IO
        original_create = self.game.CreateObjectEx
        def partial(kind, position, flags):
            cache = original_create(kind, position, flags)
            original_cargo = cache.GetInventory().CreateEntityInCargo
            cache.GetInventory = lambda: N(CreateEntityInCargo=lambda name:
                None if name == 'MetalWire' else original_cargo(name))
            return cache
        self.game.CreateObjectEx = partial
        self.assertTrue(self.binder.Bind(self.observer, self.missions[1]))
        self.assertTrue(self.binder.Bind(self.observer, self.missions[2]))
        self.assertFalse(self.binder.Bind(self.observer, self.missions[4]))
        before_create = self.game.io.log[:next(i for i, row in enumerate(self.game.io.log) if row[0] == 'create')]
        self.assertIn(('write', '1-grant-1.txt'), before_create)
        self.assertEqual(['BandageDressing', 'SodaCan_Cola'], self.game.created[0].contents)
        self.assertIn('[HC Events] reward cache created site coastal-police-source items 2/3', self.logs)
        for _ in range(5):
            self.assertFalse(self.binder.Bind(self.observer, self.missions[4]))
        self.assertEqual(1, len(self.game.created))

    def test_empty_cargo_is_removed_without_refill(self):
        self.game.cargo_ok = False
        self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual(1, len(self.game.deleted))
        self.game.cargo_ok = True
        self.assertFalse(self.binder.Bind(self.observer, self.missions[1]))
        self.assertEqual(1, len(self.game.created))

    def test_registration_capacity_retry_and_missing_items_never_spawn_a_second_barrel(self):
        for i in range(32):
            self.assertTrue(self.observer.RegisterTarget('filler'+str(i), runtime.Handle()))
        mission = self.missions[1]
        self.assertFalse(self.binder.Bind(self.observer, mission))
        self.assertEqual(1, len(self.game.created))
        self.observer.m_Targets.Remove(0)
        self.assertTrue(self.binder.Bind(self.observer, mission))
        target = self.observer.Target(mission.Id)
        target.Item.deleted = True
        self.assertTrue(self.binder.Bind(self.observer, mission))
        self.assertFalse(self.observer.Ready(mission))
        self.assertEqual(1, len(self.game.created))

    def test_infected_late_population_chooses_nearest_and_stable_id_tie(self):
        mission = self.missions[7]
        for _ in range(3):
            self.assertFalse(self.binder.Bind(self.observer, mission))
        self.assertEqual(1, len([s for s in self.logs if 'reason=no_candidate' in s]))
        def infected(offset, entity_id, eligible=True):
            actor = runtime.Handle(kind='SyntheticZombie', position=[
                mission.Source[0] + offset, mission.Source[1], mission.Source[2]])
            actor.HCEventEconomyCandidate = lambda: eligible
            actor.GetID = lambda: entity_id
            return actor
        near = infected(2, 9); tied = infected(-2, 3)
        dead = infected(0, 1); dead.alive = False
        deleted = infected(0, 2); deleted.deleted = True
        self.objects = [infected(10, 10), near, tied, dead, deleted, infected(0, 0, False)]
        for order in (self.objects, list(reversed(self.objects))):
            self.objects = order
            self.assertTrue(self.binder.Bind(self.observer, mission))
            self.assertIs(tied, self.observer.Target(mission.Id).Infected)
        self.assertFalse(any('ambiguous' in s for s in self.logs))


class RetryContract(unittest.TestCase):
    def test_blocked_announcement_is_not_a_permanent_session_record(self):
        f = runtime.EventRuntimeTests(); f.setUp(); engine = f.runtime()
        f.observer.ready = False
        self.assertEqual(f.code.BLOCKED, engine.Announce(f.mission, f.ctx))
        self.assertFalse(engine.HasMission(f.mission.Id))
        f.observer.ready = True
        self.assertEqual(f.code.OK, engine.Announce(f.mission, f.ctx))

    def test_five_site_retry_is_one_pair_per_five_seconds_and_no_terminal_repeat(self):
        f = integration.EventIntegrationTests(); f.setUp()
        f.cfg.Sites = EArray(N(Id='s'+str(i), WorldName='synthetic_world') for i in range(5))
        f.env['HCEventRoster'] = N(Build=lambda site, ai: EArray(
            N(Id=site.Id+'-'+str(fam), Family=fam) for fam in range(1, 8)))
        scans = []
        f.env['HCEventWorldBinding'] = N(Bind=lambda observer, mission: scans.append((f.now, mission.Id)),
            BindSites=lambda observer, settings, world: None)
        f.announce_code = 7; f.start()
        for second in range(1, 351):
            f.now = 100 + second
            f.module.OnTick(1)
        self.assertEqual(70, len(scans))
        first_pair = [t for t, mission in scans if mission == 's0-1']
        self.assertEqual([105, 280], first_pair)
        self.assertTrue(all(b[0]-a[0] >= 5 for a, b in zip(scans, scans[1:])))
        f.announce_code = 0
        for _ in range(70):
            f.module.RefreshRoster(f.module.Context())
        admitted = len(scans)
        for _ in range(35):
            f.module.RefreshRoster(f.module.Context())
        self.assertEqual(admitted, len(scans))


if __name__ == '__main__':
    unittest.main()
