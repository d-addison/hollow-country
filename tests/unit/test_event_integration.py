"""Authored Events lifecycle/registry with explicit synthetic collaborators.

Spec/plan trace: 001 NFR-001/003/004, AC-011, T023; handoff Events integration.
Given initialized runtime/sites, expose opt-in RPC; revoke peers before observing;
detach transport before runtime cleanup, including failed startup and restart.
The restricted translator executes authored bodies, not a second lifecycle.
Synthetic game/clock, roster, providers, journal and callback invoker establish
neither Enforce compilation nor native persistence, rendering or network behavior.

Actual TDD record (2026-11-17):
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_event_integration -v
  RED before module/registry edits: 13 tests, 12 failures and 3 errors (subtests).
  GREEN after edits: 13 tests passed.
  Events discovery: 125 tests, one legacy fixture error in test_event_runtime.py
  (EventModuleLifecycleTests does not initialize the new RPC field/static port).
  That fixture is outside this worker's ownership; main must adapt it before
  claiming combined acceptance. No engine or multiplayer acceptance is claimed.
"""
import math
import re
from types import SimpleNamespace as N
import unittest

from tests.unit import test_event_runtime as runtime_tests
from tests.unit import test_event_transport as transport_tests
from tests.unit.test_group_server import EArray

ROOT = runtime_tests.ROOT
MODULE = ROOT / "4_World/Events/HCEventModule.c"
REGISTRY = ROOT / "4_World/Core/HCModule.c"


def authored_module(env):
    source = MODULE.read_text()
    # Language-only adaptations: constructor syntax, native out parameter,
    # static storage, and the existing translator's chained call limitation.
    source = re.sub(r"new (\w+)\(", r"\1(", source)
    source = re.sub(r"GetGame\(\)\.GetWorldName\((\w[\w.]*)\);",
                    r"\1 = GetGame().GetWorldName();", source)
    source = source.replace("Math.RandomIntInclusive(1, 1000000000).ToString()",
                            "str(Math.RandomIntInclusive(1, 1000000000))")
    source = re.sub(r"\bs_(Instance|CleanupOwner)\b", r"HCEventModule.s_\1", source)
    # The extension hook has a comment-only body: Enforce permits that.
    source = re.sub(r"(void BindReviewedTargets\([^)]*\)\s*\{)(.*?)(\n    \})",
                    lambda m: m[1] + re.sub(r"//[^\n]*", "", m[2]) + "return;" + m[3],
                    source, flags=re.S)
    cls = type("AuthoredEventModule", (), {"s_Instance": None, "s_CleanupOwner": None,
                                  "m_AIProvider": None})
    env["HCEventModule"] = cls
    names = re.findall(r"^    (?:static |override )?(?:bool|string|void|HCEvent\w+) (\w+)\(", source, re.M)
    # Explicit synthetic V2 owner boundary for these legacy V1/RPC fixtures.
    # Actual HC-38/39/40 handlers execute in test_hc_situations.
    situation_ports = {'HCStartSituations', 'HCStepSituations', 'HCPublishSituations',
                       'HCSourceClosing', 'HCCloseSituations', 'HCStoryArrived', 'HCOfferSituation'}
    cls.HCStartSituations = lambda self, settings: None
    cls.HCStepSituations = lambda self: None
    cls.HCCloseSituations = lambda self: None
    for name in names:
        if name in situation_ports:
            continue
        fn = runtime_tests.translate(source, name, env, "HCEventModule", name != "Get")
        setattr(cls, name, staticmethod(fn) if name == "Get" else fn)
    return cls


class EventIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.callbacks = []
        self.runtimes = []
        self.transports = []
        self.now = 100.0
        self.server = True
        self.start_ok = True
        self.rpc_ok = True
        self.next_session = 0
        self.cfg = N(Enabled=True, Sites=EArray([N(WorldName="synthetic_world")]))
        self.logs = []
        self.env = dict(EArray=EArray, Print=lambda text: self.logs.append(text),
                        str=str, Math=N(Floor=math.floor, RandomIntInclusive=self.random))
        self.game = N(IsServer=lambda: self.server, GetTickTime=lambda: self.now,
                      GetWorldName=lambda: "synthetic_world")
        self.env["HCEventQualification"] = N(Admitted=lambda: True)
        self.sites_admitted = True
        self.env["HCEventSitesGate"] = N(Admitted=lambda: self.sites_admitted)
        self.env["HCEventWorldBinding"] = N(Bind=lambda observer, mission: True, BindSites=lambda observer, settings, world: None)
        self.ai_ready = True
        self.announce_code = 0
        self.builds = []
        self.env["HCEventAISelection"] = N(Create=lambda: N(synthetic=True, Ready=lambda world: self.ai_ready))
        self.env["GetGame"] = lambda: self.game
        self.env["HCEventContext"] = lambda: N(Server=False, WorldName="", Session="", Now=0)
        self.env["HCEventConfiguration"] = lambda: N(Load=lambda: self.cfg)
        self.env["HCEventJournal"] = lambda cfg: N(synthetic=True)
        self.env["HCEventNativeObserver"] = lambda: N(synthetic=True)
        self.env["HCEventAIProvider"] = lambda: N(synthetic=True)
        self.env["HCEventCode"] = N(OK=0)
        self.env["HCEventRoster"] = N(Build=self.roster)
        owner = self

        class Runtime:
            def __init__(self):
                self.session = None
                self.stops = 0
                self.members = ["synthetic-peer"]
                owner.runtimes.append(self)

            def Start(self, cfg, context, store, observer, ai):
                self.session = context.Session
                owner.calls.append("runtime.start")
                return owner.start_ok

            def Announce(self, mission, context):
                owner.calls.append("runtime.announce")
                return owner.announce_code

            def HasMission(self, mission):
                return False

            def Tick(self, context):
                owner.calls.append(("runtime.observe", list(self.members)))

            def Disconnect(self, player, context):
                owner.calls.append(("runtime.disconnect", player))
                self.members.clear()

            def Stop(self, context):
                owner.calls.append("runtime.stop")
                # Callback detachment must precede even partial runtime cleanup.
                owner.assertEqual([], owner.callbacks)
                self.stops += 1
                return True  # Explicit synthetic confirmation; not provider evidence.

        self.env["HCEventRuntime"] = Runtime
        self.env["DayZGame"] = N(Event_OnRPC=N(Insert=self.insert, Remove=self.remove))
        rpc_cls = transport_tests.methods(ROOT / "4_World/Events/HCEventRPC.c", self.env)
        self.env["HCEventRPC"] = self.transport_factory(rpc_cls)
        self.cls = authored_module(self.env)
        self.module = self.make_module()
        self.module.IsEnabled(N())

    def random(self, low, high):
        self.next_session += 1
        return self.next_session

    def roster(self, site, enabled):
        self.calls.append("roster.build")
        self.builds.append(enabled)
        return EArray([N(Id="synthetic-mission", Family=1)])

    def insert(self, callback):
        self.calls.append("rpc.attach")
        self.callbacks.append(callback)

    def remove(self, callback):
        self.calls.append("rpc.detach")
        self.callbacks.remove(callback)

    def transport_factory(self, cls):
        owner = self

        class Transport(cls):
            def __init__(self):
                self.m_Module = None
                self.m_Peers = EArray()
                self.m_Started = False
                self.m_Serial = 0
                self.m_GlobalWindow = 0.
                self.m_GlobalCount = 0
                self.m_LastTime = 0.
                self.m_Boot = ""
                owner.transports.append(self)

            def Start(self, module):
                # Failure can follow a callback attachment: cleanup must handle
                # partial admission, rather than discarding the only RPC owner.
                result = super().Start(module)
                return result and owner.rpc_ok

            def Tick(self):
                owner.calls.append("rpc.tick")
                super().Tick()

            def Stop(self):
                owner.calls.append("rpc.stop")
                super().Stop()

        return Transport

    def make_module(self):
        module = self.cls()
        module.m_Config = None
        module.m_Runtime = None
        module.m_StartedAt = 0.
        module.m_Session = ""
        # Enforce initializes a new ref field to null; no integration supplied.
        module.m_NativeObserver = None
        module.m_RosterElapsed = 0
        module.m_RosterCursor = 0
        module.m_EventRPC = None
        module.m_Stopping = False
        return module

    def start(self):
        self.module.OnStart(N())

    def test_start_attaches_rpc_after_runtime_and_site_roster(self):
        self.start()
        self.assertEqual(["runtime.start", "roster.build", "runtime.announce", "rpc.attach"], self.calls)
        self.assertIs(self.module, self.cls.Get())
        self.assertEqual(1, len(self.callbacks))

    def test_ai_encounter_is_offered_only_when_the_provider_is_ready(self):
        for ready in (False, True):
            self.builds.clear()
            self.ai_ready = ready
            self.cls.s_Instance = None
            module = self.make_module()
            module.IsEnabled(N())
            module.OnStart(N())
            self.assertEqual([ready], self.builds, "start roster")
            module.RefreshRoster(module.Context())
            self.assertEqual([ready, ready], self.builds, "late roster refresh")

    def test_absent_provider_adds_no_ai_mission_and_no_code_seven_line(self):
        self.ai_ready = False
        self.env["HCEventRoster"] = N(Build=lambda site, include: EArray(
            [N(Id="s-1", Family=1)] + ([N(Id="s-5", Family=5)] if include else [])))
        self.start()
        self.assertEqual([], [text for text in self.logs if "code 7" in text])
        self.assertEqual(1, len([c for c in self.calls if c == "runtime.announce"]))

    def test_late_admission_is_logged_once_per_mission(self):
        self.announce_code = 7
        self.start()
        self.assertEqual([], [text for text in self.logs if "admitted later" in text])
        self.announce_code = 0
        context = self.module.Context()
        for _ in range(3):
            self.module.RefreshRoster(context)
        self.assertEqual(["[HC Events] mission admitted later; synthetic-mission"],
                         [text for text in self.logs if "admitted later" in text])

    def test_not_admitted_line_names_the_mission_and_the_code(self):
        # Observed 2026-11-17: "roster mission not admitted; code 7" gave no mission id.
        self.announce_code = 7
        self.start()
        self.assertEqual(["[HC Events] roster mission not admitted; synthetic-mission; code 7"],
                         [text for text in self.logs if "not admitted" in text])

    def test_start_admission_is_not_reported_as_late(self):
        self.start()
        self.module.RefreshRoster(self.module.Context())
        self.assertEqual([], [text for text in self.logs if "admitted later" in text])

    def test_start_summary_prints_the_admitted_count_plainly(self):
        self.start()
        self.assertEqual(1, len([text for text in self.logs if text.startswith("[HC Events] admitted missions 1;")]))

    def test_roster_build_never_hard_codes_the_ai_flag(self):
        source = MODULE.read_text()
        self.assertNotIn("Build(site, true)", source)
        self.assertEqual(2, source.count("HCEventRoster.Build(site, "))

    def test_admitted_line_reports_the_reward_pool_state_accurately(self):
        for admitted, expected in ((True, "reward caches from finite journaled pool"), (False, "reward caches unavailable")):
            self.logs.clear()
            self.sites_admitted = admitted
            self.cls.s_Instance = None
            module = self.make_module()
            module.IsEnabled(N())
            module.OnStart(N())
            line = [text for text in self.logs if "admitted missions" in text][0]
            self.assertIn(expected, line)
            self.assertNotIn("rewards unavailable", line)

    def test_empty_or_wrong_world_roster_still_exposes_honest_browse(self):
        self.cfg.Sites = EArray([None, N(WorldName="another_world")])
        self.start()
        self.assertEqual(["runtime.start", "rpc.attach"], self.calls)
        self.assertEqual(1, len(self.callbacks))

    def test_tick_revokes_dead_rpc_peer_before_runtime_observes(self):
        self.start()
        rpc = self.transports[0]
        player = runtime_tests.Handle()
        peer = N(Identity=None, Player=player)
        rpc.m_Peers.Insert(peer)
        self.calls.clear()
        self.module.OnTick(1.)
        self.assertEqual(["rpc.tick", ("runtime.disconnect", player), ("runtime.observe", [])], self.calls)
        self.assertEqual([], rpc.m_Peers)

    def test_stop_detaches_transport_before_runtime_and_is_idempotent(self):
        self.start()
        self.calls.clear()
        self.module.OnStop()
        self.module.OnStop()
        self.module.OnTick(1.)
        self.assertEqual(["rpc.stop", "rpc.detach", "runtime.stop"], self.calls)
        self.assertIsNone(self.module.Runtime())
        self.assertIsNone(self.module.m_EventRPC)
        self.assertIsNone(self.cls.Get())
        self.assertEqual("", self.module.m_Session)

    def test_repeated_start_cleans_old_session_before_new_callback(self):
        self.start()
        old_runtime = self.runtimes[0]
        old_rpc = self.transports[0]
        self.calls.clear()
        self.start()
        self.assertEqual(["rpc.stop", "rpc.detach", "runtime.stop",
                          "runtime.start", "roster.build", "runtime.announce", "rpc.attach"], self.calls)
        self.assertEqual(1, old_runtime.stops)
        self.assertFalse(old_rpc.m_Started)
        self.assertEqual([], old_rpc.m_Peers)
        self.assertNotEqual(old_runtime.session, self.runtimes[-1].session)
        self.assertEqual(1, len(self.callbacks))

    def test_failed_runtime_start_is_cleaned_and_can_retry(self):
        self.start_ok = False
        self.start()
        self.assertEqual(["runtime.start", "runtime.stop"], self.calls)
        self.assertIsNone(self.module.Runtime())
        self.assertIsNone(self.cls.Get())
        self.assertEqual([], self.callbacks)
        self.start_ok = True
        self.start()
        self.assertEqual(1, len(self.callbacks))
        self.assertIs(self.module, self.cls.Get())

    def test_partial_rpc_start_failure_cleans_callback_and_runtime_then_retries(self):
        self.rpc_ok = False
        self.start()
        self.assertEqual(["runtime.start", "roster.build", "runtime.announce",
                          "rpc.attach", "rpc.stop", "rpc.detach", "runtime.stop"], self.calls)
        self.assertEqual([], self.callbacks)
        self.assertIsNone(self.module.Runtime())
        self.assertIsNone(self.cls.Get())
        self.rpc_ok = True
        self.start()
        self.assertEqual(1, len(self.callbacks))

    def test_restart_after_disabled_configuration_cleans_existing_session(self):
        self.start()
        self.calls.clear()
        self.cfg.Enabled = False
        self.start()
        self.assertEqual(["rpc.stop", "rpc.detach", "runtime.stop"], self.calls)
        self.assertIsNone(self.cls.Get())
        self.assertIsNone(self.module.Runtime())

    def test_absent_game_or_client_start_has_no_side_effects(self):
        for game in (None, N(IsServer=lambda: False)):
            with self.subTest(game=game):
                self.game = game
                self.start()
                self.assertEqual([], self.calls)
                self.assertIsNone(self.cls.Get())
                self.assertIsNone(self.module.Runtime())

    def test_invalid_clock_stops_before_observation_and_can_restart(self):
        for bad in (99., float("nan"), 1000000101.):
            with self.subTest(clock=bad):
                self.now = 100.
                self.start()
                self.calls.clear()
                self.now = bad
                self.module.OnTick(1.)
                self.assertEqual(["rpc.stop", "rpc.detach", "runtime.stop"], self.calls)
                self.assertEqual([], self.callbacks)
                self.assertIsNone(self.cls.Get())
                self.calls.clear()

    def test_stop_without_game_detaches_callback_and_attempts_runtime_cleanup(self):
        self.start()
        self.calls.clear()
        self.game = None
        self.module.OnStop()
        self.assertEqual(["rpc.stop", "rpc.detach", "runtime.stop"], self.calls)
        self.assertIsNone(self.module.Runtime())

    def test_stopping_unstarted_instance_preserves_live_singleton(self):
        self.start()
        other = self.make_module()
        other.OnStop()
        self.assertIs(self.module, self.cls.Get())
        self.assertEqual(1, len(self.callbacks))

    def test_registry_repeated_registration_keeps_one_event_and_group(self):
        # Both RegisterModules and Register are authored; duplicate suppression
        # comes from core, rather than a substitute registry in this fixture.
        source = REGISTRY.read_text().replace("HCModule", "HCEventModule")
        cls = type("AuthoredRegistry", (), {})
        self.env["HCGroupModule"] = lambda: N(GetName=lambda: "Groups")
        for name in ("RegisterModules", "Register", "GetModules"):
            setattr(cls, name, runtime_tests.translate(source, name, self.env, "HCEventModuleRegistry", True))
        registry = cls()
        registry.m_Modules = EArray()
        registry.RegisterModules()
        registry.RegisterModules()
        modules = registry.GetModules()
        self.assertEqual(["Groups", "Events"], [module.GetName() for module in modules])
        self.assertEqual(1, sum(isinstance(module, self.cls) for module in modules))




class EventCleanupLifecycleTests(unittest.TestCase):
    """Real authored module, runtime and RPC; synthetic journal/provider only."""

    def setUp(self):
        self.helper = runtime_tests.EventRuntimeTests()
        self.helper.setUp()
        prototype = self.helper.runtime()
        self.env = self.helper.e
        self.ai = self.helper.ai
        self.store = self.helper.store
        self.ai.ready = True
        self.ai.gone = False
        self.now = 100.
        self.created = []
        self.callbacks = []
        self.game = N(IsServer=lambda: True, GetTickTime=lambda: self.now,
                      GetWorldName=lambda: "synthetic_world")
        self.env["HCEventQualification"] = N(Admitted=lambda: True)
        self.env["HCEventWorldBinding"] = N(Bind=lambda observer, mission: True, BindSites=lambda observer, settings, world: None)
        self.env["HCEventAISelection"] = N(Create=lambda: N(synthetic=True))
        self.env["GetGame"] = lambda: self.game
        self.serial = 0

        def random(low, high):
            self.serial += 1
            return self.serial

        self.env["Math"].Floor = math.floor
        self.env["Math"].RandomIntInclusive = random
        self.env["HCEventConfiguration"] = lambda: N(Load=lambda: self.helper.cfg)
        self.env["HCEventJournal"] = lambda cfg: self.store
        self.env["HCEventNativeObserver"] = lambda: self.helper.observer
        self.env["HCEventAIProvider"] = lambda: self.ai
        self.env["HCEventAISelection"] = N(Create=lambda: self.ai)
        self.env["DayZGame"] = N(Event_OnRPC=N(
            Insert=lambda fn: self.callbacks.append(fn),
            Remove=lambda fn: self.callbacks.remove(fn)))
        rpc_cls = transport_tests.methods(ROOT / "4_World/Events/HCEventRPC.c", self.env)

        def rpc_factory():
            rpc = rpc_cls()
            rpc.m_Module = None
            rpc.m_Peers = EArray()
            rpc.m_Started = False
            rpc.m_Serial = 0
            return rpc

        def runtime_factory():
            r = type(prototype)()
            r.m_State = None
            r.m_Ready = False
            r.m_Busy = False
            r.m_StopRequested = False  # Native bool field default, if present.
            r.m_LastNow = 0
            r.m_Subscriptions = EArray()
            r.m_Cursor = 0
            self.created.append(r)
            return r

        self.env["HCEventRPC"] = rpc_factory
        self.env["HCEventRuntime"] = runtime_factory
        self.cls = authored_module(self.env)
        self.module = self.make_module()
        self.module.OnStart(N())
        self.runtime = self.module.Runtime()
        self.helper.mission.Family = 5
        self.helper.mission.ActorBudget = 2
        self.assertEqual(0, self.runtime.Announce(self.helper.mission, self.module.Context()))
        self.assertEqual(1, len(self.ai.starts))

    def make_module(self):
        m = self.cls()
        m.m_Config = self.helper.cfg
        m.m_Runtime = None
        m.m_EventRPC = None
        m.m_Stopping = False  # Native bool default, if present.
        m.m_StartedAt = 0.
        m.m_Session = ""
        return m

    def assert_retained(self):
        self.assertIs(self.runtime, self.module.Runtime())
        self.assertEqual([], self.callbacks)
        self.assertIsNone(self.cls.Get())
        self.assertFalse(self.runtime.Allowed(self.module.Context()))
        self.assertNotEqual(3, self.runtime.m_State.Runs[0].Phase)

    def test_unconfirmed_ai_stop_retains_owner_and_retries_without_new_groups(self):
        self.module.OnStop()
        self.assert_retained()
        self.module.OnStart(N())
        self.assert_retained()
        self.assertEqual(1, len(self.created))
        self.assertEqual(1, len(self.ai.starts))
        self.ai.gone = True
        self.module.OnTick(1.)
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)
        self.module.OnStart(N())
        self.assertEqual(2, len(self.created))
        self.assertEqual(1, len(self.callbacks))

    def test_new_registry_instance_cannot_abandon_previous_cleanup_owner(self):
        self.module.OnStop()
        replacement = self.make_module()
        replacement.OnStart(N())
        self.assert_retained()
        self.assertIsNone(replacement.Runtime())
        self.assertEqual(1, len(self.created))
        self.ai.gone = True
        replacement.OnStart(N())
        self.assertIsNone(self.module.Runtime())
        self.assertIsNotNone(replacement.Runtime())
        self.assertEqual(2, len(self.created))
        self.assertEqual(3, self.store.image.Runs[0].Phase)
        self.assertEqual(1, len(self.ai.starts))

    def test_busy_stop_disables_admission_and_retains_until_unwound_and_gone(self):
        self.runtime.m_Busy = True
        self.module.OnStop()
        self.assertIs(self.runtime, self.module.Runtime())
        self.assertEqual([], self.callbacks)
        self.runtime.m_Busy = False
        self.assertFalse(self.runtime.Allowed(self.module.Context()))
        self.module.OnTick(1.)
        self.assert_retained()
        self.ai.gone = True
        self.module.OnStop()
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)

    def test_failed_journal_never_reports_closed_even_if_provider_reports_gone(self):
        self.store.Save = lambda state: False
        self.ai.gone = True
        self.module.OnStop()
        self.assert_retained()
        self.module.OnStart(N())
        self.assert_retained()
        self.assertEqual(1, len(self.created))
        self.assertNotEqual(3, self.store.image.Runs[0].Phase)
        self.assertGreaterEqual(len(self.ai.stops), 1)

    def test_missing_game_retains_without_calling_native_provider_then_recovers(self):
        self.game = None
        self.module.OnStop()
        self.assert_retained()
        self.assertEqual([], self.ai.stops)
        self.game = N(IsServer=lambda: True, GetTickTime=lambda: self.now,
                      GetWorldName=lambda: "synthetic_world")
        self.ai.gone = True
        self.module.OnStop()
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)

    def test_invalid_clock_keeps_original_session_for_later_cleanup(self):
        session = self.module.m_Session
        self.now = 99.
        self.module.OnTick(1.)
        self.assert_retained()
        self.assertEqual(session, self.module.m_Session)
        self.now = 101.
        self.ai.gone = True
        self.module.OnTick(1.)
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)

    def test_stop_request_return_value_and_status_require_confirmed_cleanup(self):
        self.assertFalse(self.runtime.Stop(self.module.Context()))
        self.assertFalse(self.runtime.CleanupComplete())
        self.ai.gone = True
        self.assertTrue(self.runtime.Stop(self.module.Context()))
        self.assertTrue(self.runtime.CleanupComplete())

    def test_cleanup_quarantines_after_bounded_retries_and_fresh_start_rechecks_owner(self):
        logs = []
        self.env["Print"] = logs.append
        self.module.OnStop()
        for _ in range(20):
            self.module.OnTick(1.)
        attempts = len(self.ai.stops)
        self.assertLessEqual(attempts, 16)
        self.assertEqual(1, sum("quarantin" in line for line in logs))
        for _ in range(100):
            self.module.OnTick(1.)
        # Quarantine keeps retrying at a low bounded rate, not every tick.
        self.assertLessEqual(len(self.ai.stops) - attempts, 4)  # <= 2 retries in 100 ticks
        self.assertEqual(1, sum("quarantin" in line for line in logs))
        replacement = self.make_module()
        replacement.OnStart(N())
        self.assertIsNone(replacement.Runtime())
        self.assertEqual(1, len(self.created))
        self.ai.gone = True
        replacement.OnStart(N())
        self.assertIsNone(self.module.Runtime())
        self.assertIsNotNone(replacement.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)

    def test_quarantined_cleanup_completes_when_slow_confirmation_arrives(self):
        logs = []
        self.env["Print"] = logs.append
        self.module.OnStop()
        for _ in range(20):
            self.module.OnTick(1.)
        self.assertTrue(any("quarantin" in line for line in logs))
        self.assert_retained()
        self.ai.gone = True
        for _ in range(60):
            self.module.OnTick(1.)
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[0].Phase)
        self.assertIsNone(self.cls.s_CleanupOwner)

    def test_100_module_starts_announce_roster_with_bounded_retention(self):
        self.ai.gone = True
        site = self.env["HCEventSite"]()
        site.Id = "module-retention"; site.WorldName = "synthetic_world"
        site.Reviewed = True; site.ItemClass = "SyntheticSupply"
        site.ContainerClass = "SyntheticContainer"; site.AnchorClass = "SyntheticSite"
        self.helper.cfg.Sites = EArray([site])
        last_id = 1
        for boot in range(100):
            self.module.OnStart(N())
            runtime = self.module.Runtime()
            self.assertIs(self.module, self.cls.Get(), boot)
            self.assertTrue(runtime.Allowed(self.module.Context()), boot)
            self.assertEqual(1, len(self.callbacks))
            records = runtime.m_State.Director.Records
            current = [r for r in records if r.Session == self.module.m_Session]
            self.assertEqual(7, len(current), boot)
            self.assertGreater(current[0].Id, last_id)
            last_id = current[-1].Id
            self.assertLessEqual(len(records), 32)
            self.assertLessEqual(len(runtime.m_State.Director.Sessions), 33)
        self.assertEqual(701, last_id)

    def test_observer_release_refusal_is_retained_like_ai_absence(self):
        self.ai.gone = True
        self.module.OnStop()
        self.module.OnStart(N())
        r = self.module.Runtime()
        self.helper.mission.Family = 1
        self.helper.mission.ActorBudget = 0
        self.helper.mission.Id = "synthetic-recovery"
        self.assertEqual(0, r.Announce(self.helper.mission, self.module.Context()))
        self.helper.observer.Release = lambda lease: False
        self.module.OnStop()
        self.assertIs(r, self.module.Runtime())
        self.assertFalse(r.Allowed(self.module.Context()))
        self.assertNotEqual(3, r.m_State.Runs[-1].Phase)
        self.helper.observer.Release = lambda lease: True
        self.module.OnStop()
        self.assertIsNone(self.module.Runtime())
        self.assertEqual(3, self.store.image.Runs[-1].Phase)

if __name__ == "__main__":
    unittest.main()
