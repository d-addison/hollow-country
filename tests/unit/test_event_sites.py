"""#33/#46 playable optional events: reviewed ChernarusPlus sites, objective adapters, journaled rewards.

Spec/plan trace: V1 scope (events without AI groups), docs/LOCAL_ACCEPTANCE_V1.md #33.
The restricted translator executes the authored Enforce bodies against EXPLICIT SYNTHETIC
collaborators (fake journal directory, fake engine, handles). Nothing here establishes
DayZ behavior, native persistence or acceptance; the sites stay Surveyed=false and the
marker-gated opt-in stays PENDING local acceptance. The optional data tests read the stock
mission files only when they are installed and are skipped otherwise.

Actual TDD record (2026-11-17):
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_event_sites -v
  RED:   Ran 35 tests ... FAILED (failures=1, errors=33); the sources, data files and
         the RewardCache field did not exist (FileNotFoundError for HCEventSitesGate.c, etc.).
  GREEN: Ran 38 tests ... OK after the Enforce sources, sites.json and reward-pool.json landed.

Round 2 (#147): replace obsolete mint/permanent-refusal expectations with
existing physical stock and shared live-provider ports. Preserve finite stock,
no-refill, same-handle, no-delete and admission assertions. All fixtures synthetic.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit import test_event_runtime as runtime_tests
from tests.unit.test_event_runtime import ROOT, Handle, environment, translate
from tests.unit.test_group_server import EArray

REPO = ROOT.parents[2]
DATA = REPO / "docs/events"
VANILLA = Path("/mnt/d/SteamLibrary/steamapps/common/DayZServer/mpmissions/dayzOffline.chernarusplus")
MARKER = "$profile:HollowCountry/acceptance/events_sites.disable"  # opt-out: the sites are on by default
SITES_ON = ("[HollowCountry] V1 admission feature=EventSites preference=on gate=events_sites qualified=0 result=admitted "
            "unverified: events_sites has no recorded native verdict; opt out with acceptance/events_sites.disable")
SITES_OFF = ("[HollowCountry] V1 admission feature=EventSites preference=off gate=events_sites qualified=0 "
             "result=off: operator opt-out acceptance/events_sites.disable")


def v1_admission():
    """The parent-owned shared Core/HCV1Admission.c line format, translated unchanged."""
    source = (ROOT / "4_World/Core/HCV1Admission.c").read_text()
    admission = N()
    env = {"FileExist": lambda path: False, "HCV1Admission": admission}
    for name in ("Line", "Refused"):
        setattr(admission, name, translate(source, name, env, "HCV1Admission"))
    return admission


def load(filename, owner, env, statics=None):
    """Translate every method of one authored class into a Python stand-in class."""
    source = (ROOT / "4_World/Events" / filename).read_text()
    source = source[source.index("class " + owner):]
    following = source.find("\nclass ", 1)
    if following >= 0:
        source = source[:following]
    # Unset static fields start null, as native Enforce statics do.
    defaults = {"s_" + name: None for name in re.findall(r"\bs_(\w+)\b", source)}
    defaults.update(statics or {})
    cls = type(owner, (), defaults)
    env[owner] = cls
    source = re.sub(r"\bs_(\w+)\b", owner + r".s_\1", source)
    for static, name in re.findall(r"^    (?:override )?(static )?(?:bool|int|float|string|void|vector|HCEvent\w+|array<[^>]+>) (\w+)\(", source, re.M):
        fn = translate(source, name, env, owner, not bool(static))
        setattr(cls, name, staticmethod(fn) if static else fn)
    return cls


class FakeIO:
    """Synthetic immutable-file directory with the HCEventJournalIO surface."""
    def __init__(self):
        self.files = {}
        self.log = []
        self.fail_write = False
        self.names_broken = False

    def Names(self):
        return None if self.names_broken else EArray(sorted(self.files))

    def Exists(self, name):
        return name in self.files

    def WriteNew(self, name, text, limit):
        self.log.append(("write", name))
        if self.fail_write or name in self.files or not 0 < len(text) <= limit:
            return False
        self.files[name] = text
        return True

    def Remove(self, name):
        self.log.append(("remove", name))
        return self.files.pop(name, None) is not None


class FakeGame:
    def __init__(self, io=None, server=True):
        self.server = server
        self.io = io
        self.stock = []  # Explicit existing native stock; never populated by a query.
        self.created = []
        self.deleted = []
        self.height = 7.0
        self.create_ok = True
        self.cargo_ok = True
        self.log = []

    def IsServer(self):
        return self.server

    def SurfaceY(self, x, z):
        return self.height

    def CreateObjectEx(self, kind, position, flags, rotation=0):
        self.log.append(("create", kind, flags))
        if self.io is not None:
            self.io.log.append(("create", kind))
        if not self.create_ok:
            return None
        cache = Handle(identity="", position=list(position), kind=kind)
        cache.flags = flags
        cache.Open = lambda: None
        cache.SetSynchDirty = lambda: None
        game = self

        def cargo(name):
            if not game.cargo_ok:
                return None
            item = Handle(identity="", position=list(position), kind=name)
            item.parent = cache
            cache.contents.append(name)
            return item
        cache.contents = []
        cache.GetInventory = lambda: N(CreateEntityInCargo=cargo)
        self.created.append(cache)
        return cache

    def GetObjectsAtPosition3D(self, anchor, radius, objects, proxies):
        objects.extend(self.stock)

    def ObjectDelete(self, obj):
        obj.deleted = True
        self.deleted.append(obj)


def physical_cache(position, kind="SmallProtectorCase", items=("Rag",)*4):
    cache = Handle(identity="", position=list(position), kind=kind)
    cache.contents = []
    for name in items:
        item = Handle(identity="", position=list(position), kind=name)
        item.parent = cache
        cache.contents.append(item)
    cargo = N(GetItemCount=lambda: len(cache.contents), GetItem=lambda i: cache.contents[i])
    cache.GetInventory = lambda: N(GetCargo=lambda: cargo)
    return cache


def pool(entries, caches=3, per_cache=4):
    result = N(Version=1, MaxCaches=caches, ItemsPerCache=per_cache,
               Entries=EArray([N(Type=t, Count=c) for t, c in entries]))
    return result


class Fixture(unittest.TestCase):
    def setUp(self):
        self.e = environment()
        self.logs = []
        self.e["Print"] = self.logs.append
        self.e["native_int"] = lambda text: int(text) if re.fullmatch(r"[0-9]+", text) else 0
        self.e["HCEventQualification"] = N(Admitted=lambda: True)
        self.game = FakeGame()
        self.e["GetGame"] = lambda: self.game
        self.e["ItemBase"] = N(Cast=lambda value: value)
        self.e["Object"] = N()
        for name, value in (("ECE_PLACE_ON_SURFACE", 1060), ("ECE_NOPERSISTENCY_WORLD", 8388608),
                            ("ECE_NOLIFETIME", 4194304)):
            self.e[name] = value
        self.e["HCEventTarget"] = lambda: N(MissionId="", Item=None, DeliveryContainer=None, Presence=None, Infected=None)
        self.e["HCEventRewardIO"] = FakeIO
        self.e["HCEventSitesGate"] = N(Admitted=lambda: True)
        self.e["HCW38SituationPolicy"] = N(HCGet=lambda: N(PhysicalScanObjects=64, PhysicalScanCargo=16))
        self.e["HCServer"] = N(HCTickWork=lambda: N(HCTakeFor=lambda consumer, cost: consumer == 11))
        self.e["HCUnitBudget"] = N(HC_WORK_SITUATIONS=11)
        self.e["FileExist"] = lambda path: False
        self.e["HCV2Admission"] = N(Line=lambda *args: "synthetic admission runtime=PENDING")

    def gate(self, env=None):
        env = env if env is not None else dict(self.e)
        env["FileExist"] = lambda path: False
        return env

    def sites(self):
        load("HCEventReviewedSites.c", "HCEventReviewedSites", self.e)
        return self.e["HCEventReviewedSites"].Curated()

    def ledger(self, entries=None, io=None, **limits):
        load("HCEventRewards.c", "HCEventRewardPools", self.e)
        cls = load("HCEventRewards.c", "HCEventRewardLedger", self.e)
        ledger = cls()
        ledger.m_IO = None
        ledger.m_Pool = None
        ledger.m_Remaining = EArray()
        ledger.m_Granted = EArray()
        ledger.m_Boot = 0
        ledger.m_Ready = False
        ledger.m_Fault = False
        self.io = io if io is not None else FakeIO()
        if entries is None:
            configured = self.e["HCEventRewardPools"].V1()
        else:
            configured = pool(entries, **limits)
        self.assertTrue(ledger.Configure(self.io, configured))
        return ledger


class SitesGate(Fixture):
    def load_gate(self, env):
        env["HCV1Admission"] = v1_admission()
        cls = load("HCEventSitesGate.c", "HCEventSitesGate", env, dict(s_Checked=False, s_OptIn=False))
        return cls

    def test_qualified_stays_false_and_marker_is_server_only_and_cached_once(self):
        env = dict(self.e)
        probes = []
        env["FileExist"] = lambda path: probes.append(path) or False  # no .disable marker: default open
        env["HCEventSitesGate"] = None
        cls = self.load_gate(env)
        self.assertFalse(cls.Qualified())
        self.game.server = False
        self.assertFalse(cls.Admitted(), "a client never admits server-only sites")
        self.assertEqual([], probes, "client must not probe or cache the marker")
        self.game.server = True
        self.assertTrue(cls.Admitted())
        self.assertTrue(cls.Admitted())
        self.assertEqual([MARKER], probes)
        self.assertEqual([SITES_ON], self.logs)

    def test_disable_marker_is_not_admitted_and_logs_pending_once(self):
        env = self.gate()
        env["FileExist"] = lambda path: path == MARKER
        cls = self.load_gate(env)
        self.assertFalse(cls.Admitted())
        self.assertFalse(cls.Admitted())
        self.assertEqual([SITES_OFF], self.logs)

    def test_absent_marker_is_admitted_by_default_and_logs_once(self):
        env = self.gate()  # FileExist answers False for every path: no .disable marker
        cls = self.load_gate(env)
        self.assertTrue(cls.Admitted())
        self.assertTrue(cls.Admitted())
        self.assertEqual([SITES_ON], self.logs)

    def test_marker_text_is_the_documented_opt_out_path(self):
        source = (ROOT / "4_World/Events/HCEventSitesGate.c").read_text()
        self.assertIn('!FileExist("%s")' % MARKER, source)
        self.assertEqual(1, source.count("FileExist("))
        qualified = re.search(r"static bool Qualified\(\)\s*\{\s*return false;\s*\}", source)
        self.assertIsNotNone(qualified)


class ReviewedSites(Fixture):
    def test_three_reviewed_unsurveyed_chernarus_sites_with_distinct_ids(self):
        sites = self.sites()
        self.assertEqual(3, len(sites))
        self.assertEqual(3, len({s.Id for s in sites}))
        for site in sites:
            self.assertTrue(site.Reviewed)
            self.assertFalse(site.Surveyed, "source review is not a field survey")
            self.assertEqual("chernarusplus", site.WorldName)
            self.assertTrue(site.RewardCache)
            self.assertEqual("SmallProtectorCase", site.ItemClass)
            self.assertLessEqual(len(site.Provenance), 160)
            self.assertEqual(64, len(site.SourceSha256))
            x, y, z = site.Position
            self.assertTrue(0 < x < 15360 and 0 < z < 15360 and 0 <= y < 1000)

    def test_sites_merge_is_bounded_idempotent_and_never_overrides_operator_sites(self):
        sites = self.sites()
        settings = self.e["HCEventSettings"]()
        cls = self.e["HCEventReviewedSites"]
        cls.Merge(settings)
        cls.Merge(settings)
        self.assertEqual({s.Id for s in sites}, {s.Id for s in settings.Sites})
        self.assertTrue(self.e["HCEventRuntimePolicy"].SettingsValid(settings))
        operator = self.e["HCEventSettings"]()
        mine = self.e["HCEventSite"]()
        mine.Id = sites[0].Id
        mine.WorldName = "chernarusplus"
        mine.Position = [1., 2., 3.]
        operator.Sites = EArray([mine])
        cls.Merge(operator)
        self.assertEqual(3, len(operator.Sites))
        self.assertEqual([1., 2., 3.], operator.Sites[0].Position, "operator edit wins")
        crowded = self.e["HCEventSettings"]()
        for index in range(7):
            filler = self.e["HCEventSite"]()
            filler.Id = "other-%d" % index
            filler.WorldName = "chernarusplus"
            crowded.Sites.Insert(filler)
        cls.Merge(crowded)
        self.assertLessEqual(len(crowded.Sites), 8)
        self.assertTrue(self.e["HCEventRuntimePolicy"].SettingsValid(crowded))

    def test_gate_closed_builds_no_curated_roster_even_with_events_admitted(self):
        site = self.sites()[0]
        self.e["HCEventSitesGate"] = N(Admitted=lambda: False)
        self.assertEqual([], self.e["HCEventRoster"].Build(site, True))

    def test_roster_is_reach_the_site_and_recover_the_cache_only(self):
        for site in self.sites():
            roster = self.e["HCEventRoster"].Build(site, True)
            self.assertEqual({3, 1}, {m.Family for m in roster}, "no AI, no delivery, no vanilla loot hunt")
            for mission in roster:
                self.assertTrue(self.e["HCEventRuntimePolicy"].MissionValid(mission, "chernarusplus"))
                self.assertEqual(0, mission.RewardUnits, "director reward units stay zero")
                self.assertEqual(0, mission.ActorBudget)
                self.assertEqual(site.Position, mission.Source)
                self.assertEqual(mission.Family == 1, mission.RewardCache)

    def test_reward_cache_is_valid_only_for_recovery_missions(self):
        site = self.sites()[0]
        recovery = [m for m in self.e["HCEventRoster"].Build(site, True) if m.Family == 1][0]
        self.assertTrue(self.e["HCEventRuntimePolicy"].MissionValid(recovery, "chernarusplus"))
        for family in (2, 3, 4, 6, 7):
            broken = copy.deepcopy(recovery)
            broken.Family = family
            self.assertFalse(self.e["HCEventRuntimePolicy"].MissionValid(broken, "chernarusplus"), family)

    def test_existing_sites_and_uncurated_rosters_are_unchanged(self):
        site = self.e["HCEventSite"]()
        site.Id = "plain"
        site.WorldName = "chernarusplus"
        site.Reviewed = True
        site.ItemClass = "Rag"
        site.AnchorClass = "Land_Synthetic"
        roster = self.e["HCEventRoster"].Build(site, True)
        self.assertEqual({1, 2, 3, 4, 5, 6, 7}, {m.Family for m in roster})
        self.assertFalse(any(m.RewardCache for m in roster))


class ConfigurationMerge(Fixture):
    def loader(self):
        loader, env = runtime_tests.EventConfigurationTests().loader()
        env["Print"] = self.logs.append
        load("HCEventReviewedSites.c", "HCEventReviewedSites", env)
        return loader, env

    def test_closed_gate_leaves_the_stock_template_and_open_gate_merges_in_memory_only(self):
        loader, env = self.loader()
        cfg = loader.Load()
        self.assertEqual(2, len(cfg.Sites), "gate closed: stock template only")
        env["HCEventSitesGate"] = N(Admitted=lambda: True)
        cfg = loader.Load()
        self.assertEqual(5, len(cfg.Sites))
        self.assertEqual(3, len([s for s in cfg.Sites if s.RewardCache]))
        self.assertEqual(1, loader.m_IO.writes, "curated sites are never persisted to settings.json")
        self.assertNotIn("kamenka", loader.m_IO.text)

    def test_open_gate_merges_after_the_template_write_and_keeps_an_invalid_file_refused(self):
        loader, env = self.loader()
        env["HCEventSitesGate"] = N(Admitted=lambda: True)
        cfg = loader.Load()
        self.assertEqual(5, len(cfg.Sites))
        self.assertEqual(1, loader.m_IO.writes)
        self.assertNotIn("kamenka", loader.m_IO.text)
        loader.m_IO.text = '{"WorkPerTick":0}'
        self.assertIsNone(loader.Load())


class RewardLedger(Fixture):
    def test_v1_pool_is_finite_vanilla_and_valid(self):
        load("HCEventRewards.c", "HCEventRewardPools", self.e)
        pools = self.e["HCEventRewardPools"]
        v1 = pools.V1()
        self.assertTrue(pools.Valid(v1))
        self.assertLessEqual(v1.MaxCaches * v1.ItemsPerCache, sum(e.Count for e in v1.Entries))
        self.assertLessEqual(sum(e.Count for e in v1.Entries), 64)
        broken = copy.deepcopy(v1)
        broken.Entries.append(copy.deepcopy(broken.Entries[0]))
        self.assertFalse(pools.Valid(broken), "duplicate class")
        for field, value in (("MaxCaches", 0), ("ItemsPerCache", 9), ("Version", 2)):
            broken = copy.deepcopy(v1)
            setattr(broken, field, value)
            self.assertFalse(pools.Valid(broken), field)

    def test_commit_journals_before_returning_and_spends_the_site(self):
        ledger = self.ledger()
        plan = ledger.Commit("site-a")
        self.assertEqual(4, len(plan.Items))
        names = sorted(self.io.files)
        self.assertEqual(["1-boot.txt", "1-grant-1.txt"], names)
        self.assertIn("site-a", self.io.files["1-grant-1.txt"])
        for item in plan.Items:
            self.assertIn(item, self.io.files["1-grant-1.txt"])
        self.assertIsNone(ledger.Commit("site-a"), "same site, same boot: at most once")
        self.assertEqual(2, len(self.io.files))

    def test_journal_failure_returns_no_plan_and_still_spends_the_site(self):
        ledger = self.ledger()
        self.assertIsNotNone(ledger.Commit("warmup"))
        self.io.fail_write = True
        self.assertIsNone(ledger.Commit("site-a"))
        self.io.fail_write = False
        self.assertIsNone(ledger.Commit("site-a"), "an uncertain write never allows a second cache")

    def test_latched_fault_blocks_every_later_grant_even_after_writes_recover(self):
        ledger = self.ledger()
        self.assertIsNotNone(ledger.Commit("site-a"))
        self.io.fail_write = True
        self.assertIsNone(ledger.Commit("site-b"))
        self.io.fail_write = False
        self.assertIsNone(ledger.Commit("site-c"), "a latched journal fault admits no further grant this session")
        self.assertEqual(["1-boot.txt", "1-grant-1.txt"], sorted(self.io.files))

    def test_pool_is_finite_and_cap_is_per_boot(self):
        ledger = self.ledger([("Rag", 3), ("Matchbox", 1)], caches=3, per_cache=2)
        first = ledger.Commit("a")
        second = ledger.Commit("b")
        self.assertEqual(sorted(first.Items + second.Items), ["Matchbox", "Rag", "Rag", "Rag"])
        self.assertIsNone(ledger.Commit("c"), "pool exhausted")
        capped = self.ledger([("Rag", 9)], caches=1, per_cache=2)
        self.assertIsNotNone(capped.Commit("a"))
        self.assertIsNone(capped.Commit("b"), "cache cap")

    def test_restart_starts_a_new_boot_prunes_old_files_and_never_replays_a_grant(self):
        io = FakeIO()
        first = self.ledger(io=io)
        first.Commit("site-a")
        again = self.ledger(io=io)
        plan = again.Commit("site-a")
        self.assertIsNotNone(plan, "a new session gets its own capped grant")
        self.assertEqual(["2-boot.txt", "2-grant-1.txt"], sorted(io.files))
        self.assertTrue(all(name.startswith("2-") for name in io.files), "prior boot pruned only after the new marker")
        self.assertLess(io.log.index(("write", "2-boot.txt")), io.log.index(("remove", "1-boot.txt")))

    def test_foreign_or_unreadable_directory_fails_closed(self):
        io = FakeIO()
        io.files["notes.txt"] = "x"
        self.assertIsNone(self.ledger(io=io).Commit("a"))
        broken = FakeIO()
        broken.names_broken = True
        self.assertIsNone(self.ledger(io=broken).Commit("a"))
        failing = FakeIO()
        failing.fail_write = True
        ledger = self.ledger(io=failing)
        self.assertIsNone(ledger.Commit("a"))
        self.assertEqual({}, failing.files)
        self.assertIsNone(ledger.Commit("a"), "a failed boot marker latches closed")

    def test_invalid_site_ids_and_pools_are_refused(self):
        ledger = self.ledger()
        for site in ("", " ", "a\nb", "x" * 49):
            self.assertIsNone(ledger.Commit(site), repr(site))
        self.assertEqual({}, self.io.files, "validation precedes any journal write")
        cls = load("HCEventRewards.c", "HCEventRewardLedger", self.e)
        refused = cls()
        self.assertFalse(refused.Configure(FakeIO(), pool([("Rag", 0)])))

    def test_process_holder_creates_one_ledger_with_the_v1_pool(self):
        load("HCEventRewards.c", "HCEventRewardPools", self.e)
        load("HCEventRewards.c", "HCEventRewardLedger", self.e)
        holder = load("HCEventRewards.c", "HCEventRewards", self.e, dict(s_Ledger=None))
        first = holder.Ledger()
        self.assertIs(first, holder.Ledger())


class CacheSpawner(Fixture):
    def spawner(self, entries=None, **limits):
        ledger = self.ledger(entries, **limits)
        load("HCEventRewards.c", "HCEventRewards", self.e, dict(s_Ledger=ledger))
        self.e["HCEventRewards"].Ledger = staticmethod(lambda: ledger)
        self.game.io = self.io
        cls = load("HCEventRewardCache.c", "HCEventCacheSpawner", self.e)
        site = self.sites()[0]
        mission = [m for m in self.e["HCEventRoster"].Build(site, True) if m.Family == 1][0]
        return cls, mission

    def test_existing_cache_is_bound_by_same_handle_without_minting(self):
        cls, mission = self.spawner()
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        for _ in range(2):
            target = cls.Create(mission)
            self.assertIs(cache, target.Item)
            self.assertIs(cache, target.Presence)
        self.assertEqual(4, len(cache.contents))
        self.assertEqual([], self.io.log, "native stock needs no mint journal")
        self.assertEqual([], self.game.created, "repeated references never duplicate loot")

    def test_gate_server_and_mission_checks_precede_any_journal_or_spawn(self):
        cls, mission = self.spawner()
        self.e["HCEventSitesGate"] = N(Admitted=lambda: False)
        self.assertIsNone(cls.Create(mission))
        self.e["HCEventSitesGate"] = N(Admitted=lambda: True)
        self.game.server = False
        self.assertIsNone(cls.Create(mission))
        self.game.server = True
        plain = copy.deepcopy(mission)
        plain.RewardCache = False
        self.assertIsNone(cls.Create(plain))
        wrong = copy.deepcopy(mission)
        wrong.Family = 3
        self.assertIsNone(cls.Create(wrong))
        self.assertIsNone(cls.Create(None))
        self.assertEqual([], self.io.log)
        self.assertEqual([], self.game.created)

    def test_existing_stock_does_not_depend_on_spawn_terrain(self):
        cls, mission = self.spawner()
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        for height in (mission.Source[1] + 40.0, float('nan')):
            self.game.height = height
            self.assertIs(cache, cls.Create(mission).Item, "existing stock requires no placement")
        self.assertEqual([], self.io.log)
        self.assertEqual([], self.game.created)

    def test_physical_stock_needs_no_reward_journal(self):
        cls, mission = self.spawner()
        self.io.fail_write = True
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        self.assertIs(cache, cls.Create(mission).Item)
        self.assertEqual([], self.io.log)
        self.assertEqual([], self.game.created)

    def test_absent_stock_never_retries_into_a_duplicate(self):
        cls, mission = self.spawner()
        for _ in range(3):
            self.assertIsNone(cls.Create(mission), "missing stock never mints a replacement")
        self.assertEqual([], self.game.created)
        self.assertEqual([], self.io.log)

    def test_empty_native_cache_is_never_deleted_or_refilled(self):
        cls, mission = self.spawner()
        cache = physical_cache(mission.Source, items=())
        self.game.stock.append(cache)
        for _ in range(3):
            self.assertIsNone(cls.Create(mission))
        self.assertEqual([], cache.contents, "empty stock never refills")
        self.assertEqual([], self.game.deleted, "native owner retains empty container")
        self.assertEqual([], self.game.created)

    def test_discard_never_deletes_borrowed_native_stock(self):
        cls, mission = self.spawner()
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        self.assertIs(cache, cls.Create(mission).Item)
        cache.owner = Handle()
        cls.Discard(cache)
        self.assertEqual([], self.game.deleted, "never delete what a player holds")
        cache.owner = None
        cls.Discard(cache)
        self.assertEqual([], self.game.deleted, "native owner also retains untouched stock")

class ObjectiveAdapters(Fixture):
    """Reach-the-site and recover-the-cache through the real authored observer and binding."""
    def setUp(self):
        super().setUp()
        self.f = runtime_tests.NativeObservationTests()
        self.f.setUp()
        self.f.e.update({k: v for k, v in self.e.items() if k in (
            "HCW38SituationPolicy", "HCServer", "HCUnitBudget", "FileExist", "HCV2Admission",
            "HCEventSitesGate", "HCEventRewardIO", "ECE_PLACE_ON_SURFACE", "ECE_NOPERSISTENCY_WORLD", "ECE_NOLIFETIME")})
        self.f.e["Print"] = self.logs.append
        self.f.e["native_int"] = self.e["native_int"]
        self.f.e["GetGame"] = lambda: self.game
        self.f.e["ItemBase"] = N(Cast=lambda value: value)
        self.f.e["HCEventTarget"] = self.e["HCEventTarget"]
        self.e = self.f.e
        self.f.e["HCEventQualification"] = N(Admitted=lambda: True)

    def curated(self):
        load("HCEventReviewedSites.c", "HCEventReviewedSites", self.e)
        return self.e["HCEventReviewedSites"].Curated()

    def missions(self, index=0):
        site = self.curated()[index]
        return {m.Family: m for m in self.e["HCEventRoster"].Build(site, True)}

    def test_reach_the_site_needs_dwell_inside_the_reviewed_radius(self):
        mission = self.missions()[3]
        run = self.f.run
        run.Objective = mission
        self.assertTrue(self.f.o.Prepare(run.Lease, mission))
        player = self.f.player
        player.position = list(mission.Source)
        self.assertIsNone(self.f.o.Observe(run, player, 100))
        self.assertIsNone(self.f.o.Observe(run, player, 105))
        self.assertTrue(self.f.o.Observe(run, player, 110).Observed)
        far = Handle(identity="bob", position=[mission.Source[0] + 200., mission.Source[1], mission.Source[2]])
        self.assertIsNone(self.f.o.Observe(run, far, 120), "bounds: 200 m away never counts")
        self.assertIsNone(self.f.o.Observe(run, far, 140))

    def test_recover_the_cache_binds_once_and_completes_only_when_carried(self):
        mission = self.missions()[1]
        io = FakeIO()
        ledger = self.ledger(io=io)
        load("HCEventRewards.c", "HCEventRewards", self.e, dict(s_Ledger=ledger))
        self.e["HCEventRewards"].Ledger = staticmethod(lambda: ledger)
        self.game.io = io
        load("HCEventRewardCache.c", "HCEventCacheSpawner", self.e)
        binder = load("HCEventWorldBinding.c", "HCEventWorldBinding", self.e)
        observer = self.f.o
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        self.assertTrue(binder.Bind(observer, mission))
        self.assertTrue(binder.Bind(observer, mission), "rebind reuses the registered cache")
        self.assertEqual([], self.game.created)
        self.assertIs(cache, observer.Target(mission.Id).Item)
        self.assertTrue(observer.Ready(mission))
        run = self.f.run
        run.Objective = mission
        self.assertTrue(observer.Prepare(run.Lease, mission))
        self.assertIsNone(observer.Observe(run, self.f.player, 100), "standing next to it is not recovery")
        cache.owner = self.f.player
        evidence = observer.Observe(run, self.f.player, 101)
        self.assertTrue(evidence.Observed)
        self.assertEqual("alice", evidence.ParticipantId)
        cache.owner = Handle(identity="outsider")
        self.assertIsNone(observer.Observe(run, self.f.player, 102), "someone else's cache is not recovery")

    def test_bind_refuses_without_site_gate_or_with_physical_stock_opt_out(self):
        mission = self.missions()[1]
        io = FakeIO()
        ledger = self.ledger(io=io)
        load("HCEventRewards.c", "HCEventRewards", self.e, dict(s_Ledger=ledger))
        self.e["HCEventRewards"].Ledger = staticmethod(lambda: ledger)
        load("HCEventRewardCache.c", "HCEventCacheSpawner", self.e)
        binder = load("HCEventWorldBinding.c", "HCEventWorldBinding", self.e)
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        self.e["HCEventSitesGate"] = N(Admitted=lambda: False)
        self.assertFalse(binder.Bind(self.f.o, mission))
        self.assertEqual([], self.game.created)
        self.e["HCEventSitesGate"] = N(Admitted=lambda: True)
        self.e["FileExist"] = lambda path: path.endswith("w38_rewards.disable")
        self.assertFalse(binder.Bind(self.f.o, mission))
        self.assertEqual([], self.game.created)
        self.e["FileExist"] = lambda path: False
        self.assertTrue(binder.Bind(self.f.o, mission))
        self.assertIs(cache, self.f.o.Target(mission.Id).Item)
        self.assertEqual([], self.game.deleted)

    def test_cache_missions_fail_closed_with_an_already_full_target_table(self):
        mission = self.missions()[1]
        io = FakeIO()
        ledger = self.ledger(io=io)
        load("HCEventRewards.c", "HCEventRewards", self.e, dict(s_Ledger=ledger))
        self.e["HCEventRewards"].Ledger = staticmethod(lambda: ledger)
        load("HCEventRewardCache.c", "HCEventCacheSpawner", self.e)
        binder = load("HCEventWorldBinding.c", "HCEventWorldBinding", self.e)
        observer = self.f.o
        cache = physical_cache(mission.Source)
        self.game.stock.append(cache)
        for index in range(32):
            filler = Handle(identity="", kind="Filler%d" % index)
            filler.GetHierarchyParent = lambda: None
            self.assertTrue(observer.RegisterTarget("filler-%d" % index, filler))
        self.assertFalse(binder.Bind(observer, mission))
        self.assertEqual([], self.game.deleted, "registration failure never deletes native stock")
        self.assertEqual([], self.game.created)
        self.assertEqual(4, len(cache.contents))


class BindDiagnosticTests(unittest.TestCase):
    """Why a reviewed target did not bind: one bounded line per (mission, reason)."""

    def setUp(self):
        fixture = runtime_tests.NativeObservationTests()
        fixture.setUp()
        self.f = fixture
        self.e = fixture.e
        self.logs = []
        self.e["Print"] = lambda text: self.logs.append(text)
        self.objects = []
        self.e["GetGame"] = lambda: N(IsServer=lambda: True, SurfaceY=lambda x, z: 0.0,
            GetObjectsAtPosition3D=lambda anchor, radius, objects, proxies: objects.extend(self.objects))
        self.e["ItemBase"] = N(Cast=lambda value: value)
        self.e["ZombieBase"] = N(Cast=lambda value: value)
        self.e["HCEventTarget"] = lambda: N(Presence=None, Item=None)
        self.mission = fixture.mission
        self.mission.Family = 1
        self.mission.ItemClass = "SyntheticSupply"
        self.binder = load("HCEventWorldBinding.c", "HCEventWorldBinding", self.e)

    def candidate(self, kind="SyntheticSupply"):
        item = Handle(identity="", kind=kind)
        item.HCEventEconomyCandidate = lambda: True
        return item

    def bind_lines(self):
        return [text for text in self.logs if text.startswith("[HC Events] bind failed;")]

    def test_query_overflow_is_reported_once_however_often_it_is_retried(self):
        self.objects = [self.candidate() for _ in range(129)]
        for _ in range(5):
            self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(["[HC Events] bind failed; %s; reason=query_overflow; wanted=SyntheticSupply; nearest_candidate_m=unknown_query_refused; radius_m=15" % self.mission.Id], self.bind_lines())

    def test_zero_candidates_are_reported_as_no_candidate(self):
        self.objects = [self.candidate("SomethingElse")]
        for _ in range(3):
            self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(["[HC Events] bind failed; %s; reason=no_candidate; wanted=SyntheticSupply; nearest_candidate_m=none_within_15; radius_m=15" % self.mission.Id], self.bind_lines())

    def test_more_than_one_candidate_is_reported_as_ambiguous(self):
        self.objects = [self.candidate(), self.candidate()]
        for _ in range(3):
            self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(["[HC Events] bind failed; %s; reason=ambiguous; wanted=SyntheticSupply; nearest_candidate_m=0.0; radius_m=15" % self.mission.Id], self.bind_lines())

    def test_infected_clear_retries_zero_then_accepts_multiple_candidates(self):
        self.mission.Family = 7
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        def zombie():
            actor = Handle(identity="", kind="SyntheticZombie")
            actor.HCEventEconomyCandidate = lambda: True
            actor.GetID = lambda: id(actor)  # Explicit synthetic stable entity id.
            return actor
        self.objects = [zombie(), zombie()]
        self.assertTrue(self.binder.Bind(self.f.o, self.mission))
        self.assertTrue(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(["[HC Events] bind failed; %s; reason=no_candidate; constraint=no_infected_in_radius; wanted=ZombieBase; nearest_candidate_m=none_within_60; radius_m=60" % self.mission.Id], self.bind_lines())

    def test_a_new_reason_for_the_same_mission_is_reported_again(self):
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.objects = [self.candidate(), self.candidate()]
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(2, len(self.bind_lines()))

    def test_delivery_destination_failures_name_the_container_not_the_item(self):
        # Review P2 (f0e12b5): a missing container logged wanted=<item>, and a destination that
        # resolved to the item itself failed with no line at all.
        self.mission.Family = 2
        self.mission.ContainerClass = "SyntheticContainer"
        self.objects = [self.candidate()]
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.mission.ContainerClass = "SyntheticSupply"
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual(["[HC Events] bind failed; %s; reason=destination_no_candidate; wanted=SyntheticContainer; radius_m=15" % self.mission.Id,
                          "[HC Events] bind failed; %s; reason=destination_same_item; wanted=SyntheticSupply; radius_m=15" % self.mission.Id],
                         self.bind_lines())

    def test_success_and_unrelated_refusals_log_nothing(self):
        self.objects = [self.candidate()]
        self.assertTrue(self.binder.Bind(self.f.o, self.mission))
        self.mission.Family = 5
        self.assertFalse(self.binder.Bind(self.f.o, self.mission))
        self.assertEqual([], self.bind_lines())

    def test_the_report_set_is_bounded(self):
        for index in range(200):
            mission = copy.copy(self.mission)
            mission.Id = "bounded-%d" % index
            self.assertFalse(self.binder.Bind(self.f.o, mission))
        self.assertEqual(64, len(self.bind_lines()))


class SourceContracts(unittest.TestCase):
    """Static contracts that no synthetic run can prove."""
    FILES = ("HCEventSitesGate.c", "HCEventReviewedSites.c", "HCEventRewards.c", "HCEventRewardCache.c")

    def source(self, name):
        return (ROOT / "4_World/Events" / name).read_text()

    def test_cache_creation_uses_only_the_verified_native_calls(self):
        text = self.source("HCEventRewardCache.c")
        for token in ("GetObjectsAtPosition3D(", "GetCargo()", "GetItemCount()"):
            self.assertIn(token, text)
        for forbidden in ("SetPosition", "SetOrientation", "CallLater", "GetPlayers", "ECE_DYNAMIC_PERSISTENCY",
                          "RPC", "ScriptRPC", "CreateInInventory"):
            self.assertNotIn(forbidden, text)
        for forbidden in ("CreateObjectEx(", "CreateEntityInCargo(", "ObjectDelete(", "SetQuantity("):
            self.assertNotIn(forbidden, text)

    def test_cache_comment_does_not_overclaim_persistence(self):
        text = self.source("HCEventRewardCache.c")
        self.assertNotIn("cannot leave a persisted duplicate", text)
        self.assertIn("player takes are ordinary loot", text)
        self.assertIn("native persistence remains authoritative", text)

    def test_ledger_has_no_engine_creation_and_never_parses_game_state(self):
        text = self.source("HCEventRewards.c")
        for forbidden in ("CreateObject", "CreateEntity", "GetGame", "ObjectDelete", "SetQuantity"):
            self.assertNotIn(forbidden, text)

    def test_new_sources_follow_the_enforce_compile_rules(self):
        for name in self.FILES + ("HCEventWorldBinding.c", "HCEventRoster.c"):
            text = self.source(name)
            self.assertIsNone(re.search(r"\?[^\n;]*:", re.sub(r'"[^"\n]*"', '""', re.sub(r"//[^\n]*", "", text))), name + " ternary")
            self.assertIsNone(re.search(r"^\s*(\|\||&&)", text, re.M), name + " leading logical operator")
            self.assertNotIn("else if", text, name)

    def test_director_reward_units_remain_zero(self):
        policy = self.source("HCEventRuntimePolicy.c")
        self.assertIn("mission.RewardUnits != 0", policy)
        director = self.source("HCEventDirector.c")
        self.assertNotIn("RewardCache", director)


class SiteData(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((DATA / "sites.json").read_text())
        self.pool = json.loads((DATA / "reward-pool.json").read_text())
        self.source = (ROOT / "4_World/Events/HCEventReviewedSites.c").read_text()
        self.rewards = (ROOT / "4_World/Events/HCEventRewards.c").read_text()

    def test_shipped_site_data_matches_the_script_constants(self):
        rows = re.findall(r'Build\("([^"]+)",\s*"([^"]+)",\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\)', self.source)
        self.assertEqual(3, len(rows))
        self.assertEqual(len(rows), len(self.data["sites"]))
        for (site_id, group, x, y, z), entry in zip(rows, self.data["sites"]):
            self.assertEqual(site_id, entry["id"])
            self.assertEqual(group, entry["event_group"])
            self.assertEqual([float(x), float(y), float(z)], entry["position"])

    def test_every_site_records_why_it_is_safe_and_what_is_not_proven(self):
        for entry in self.data["sites"]:
            safe = entry["why_safe"]
            self.assertGreaterEqual(safe["nearest_map_group"]["distance_m"], 150)
            self.assertGreaterEqual(safe["nearest_player_spawn_m"], 500)
            self.assertGreaterEqual(safe["clear_of_event_wrecks_m"], 10)
            self.assertFalse(safe["surveyed"])
            for key in ("not_inside_building", "reachable_on_foot", "not_spawn_point", "unproven"):
                self.assertTrue(safe[key], key)
            x, y, z = entry["position"]
            ox, oy, oz = entry["event_origin"]
            self.assertAlmostEqual(x, ox + entry["offset"][0], places=3)
            self.assertAlmostEqual(z, oz + entry["offset"][1], places=3)
            self.assertEqual(y, oy)
        for name, digest in self.data["sources"].items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", name)
        self.assertIn(self.data["sources"]["cfgeventspawns.xml"], self.source)

    def test_reward_pool_json_matches_the_script_pool(self):
        entries = re.findall(r'Entry\("([^"]+)",\s*(\d+)\)', self.rewards)
        self.assertEqual([[t, int(c)] for t, c in entries], [[e["type"], e["count"]] for e in self.pool["entries"]])
        self.assertEqual(int(re.search(r"pool\.MaxCaches = (\d+);", self.rewards)[1]), self.pool["max_caches_per_session"])
        self.assertEqual(int(re.search(r"pool\.ItemsPerCache = (\d+);", self.rewards)[1]), self.pool["items_per_cache"])
        self.assertTrue(all(re.fullmatch(r"[A-Za-z0-9_]+", e["type"]) for e in self.pool["entries"]))

    @unittest.skipUnless((VANILLA / "cfgeventspawns.xml").exists(), "stock mission files not installed")
    def test_positions_and_clearances_recompute_from_the_installed_stock_mission(self):
        for name, digest in self.data["sources"].items():
            self.assertEqual(digest, hashlib.sha256((VANILLA / name).read_bytes()).hexdigest(), name)
        events = (VANILLA / "cfgeventspawns.xml").read_text()
        groups = [(m[0], float(m[1]), float(m[3])) for m in re.findall(
            r'<group name="([^"]+)" pos="([-\d.]+) ([-\d.]+) ([-\d.]+)"', (VANILLA / "mapgrouppos.xml").read_text())]
        spawns = [(float(a), float(b)) for a, b in re.findall(r'<pos x="([-\d.]+)" z="([-\d.]+)"', (VANILLA / "cfgplayerspawnpoints.xml").read_text())]
        for entry in self.data["sites"]:
            origin = re.search(r'<pos x="([-\d.]+)" z="([-\d.]+)" a="[-\d.]+" y="([-\d.]+)" group="%s"' % entry["event_group"], events)
            self.assertEqual([float(origin[1]), float(origin[3]), float(origin[2])], entry["event_origin"])
            x, _, z = entry["position"]
            nearest = min((((gx - x) ** 2 + (gz - z) ** 2) ** .5, n) for n, gx, gz in groups)
            self.assertEqual(entry["why_safe"]["nearest_map_group"]["type"], nearest[1])
            self.assertAlmostEqual(entry["why_safe"]["nearest_map_group"]["distance_m"], nearest[0], delta=0.1)
            kids = re.search(r'<group name="%s">(.*?)</group>' % entry["event_group"], (VANILLA / "cfgeventgroups.xml").read_text(), re.S)
            solid = [(float(a), float(b)) for t, a, b in re.findall(r'<child type="([^"]+)"[^>]*? x="([-\d.]+)" z="([-\d.]+)"', kids[1]) if "Decal" not in t]
            clear = min(((entry["offset"][0] - a) ** 2 + (entry["offset"][1] - b) ** 2) ** .5 for a, b in solid)
            self.assertAlmostEqual(entry["why_safe"]["clear_of_event_wrecks_m"], clear, delta=0.1)
            self.assertGreaterEqual(clear, 10)
            spawn = min(((a - x) ** 2 + (b - z) ** 2) ** .5 for a, b in spawns)
            self.assertAlmostEqual(entry["why_safe"]["nearest_player_spawn_m"], spawn, delta=0.1)


if __name__ == "__main__":
    unittest.main()
