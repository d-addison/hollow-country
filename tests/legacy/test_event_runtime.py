"""Execute authored event bodies with explicit synthetic engine/storage ports.

The translator supplies language syntax, DTOs, native handles and JSON seams;
it implements no event decisions. These tests establish no DayZ qualification.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from tests.legacy.test_group_server import EArray, body

ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"


def translate(text, name, env, owner=None, member=False):
    pattern = r"\b(?:static )?(?:bool|int|float|string|void|vector|HCEvent\w+|array<[^>]+>) " + name + r"\(([^)]*)\)\s*\{"
    match = re.search(pattern, text)
    if not match:
        raise AssertionError("Missing authored method " + name)
    args = [a.split("=")[0].strip().split()[-1] for a in match[1].split(",") if a.strip()]
    code = re.sub(r"//[^\n]*", "", body(text, match.end()))
    def literal(match):
        key = "_event_literal_" + str(len(env))
        env[key] = json.loads(match[0])
        return key
    code = re.sub(r'"(?:\\.|[^"\\])*"', literal, code)
    # Native RemoveOrdered retains order; EArray.Remove is ordered list.pop.
    code = code.replace(".RemoveOrdered(", ".Remove(")
    cursor = 0
    while True:
        guard = re.search(r"\bif \(", code[cursor:])
        if not guard: break
        end = cursor + guard.end(); depth = 1
        while depth:
            depth += (code[end] == "(") - (code[end] == ")"); end += 1
        start = end
        while code[start].isspace(): start += 1
        if code[start] != "{":
            finish = code.index(";", start) + 1
            code = code[:end] + " {" + code[end:finish] + " }" + code[finish:]
        cursor = end + 2
    lines = ["def executed(" + ",".join((["self"] if member else []) + args) + "):"]
    indent = 1
    method_names = re.findall(r"\b(?:static )?(?:bool|int|float|string|void|vector|HCEvent\w+|array<[^>]+>) (\w+)\(", text)
    for token in re.split(r"([{};])", code):
        token = token.strip()
        if not token or token == ";": continue
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        lowered = re.fullmatch(r"(\w+)\.ToLower\(\)", token)
        if lowered: token = lowered[1] + " = " + lowered[1] + ".lower()"  # Enforce mutates in place
        token = re.sub(r"new array<[^;]+?>(?:\(\))?", "EArray()", token)
        token = re.sub(r"new (\w+)(?:\(\))?", r"\1()", token)
        token = re.sub(r"\b(?:ref )?(?:array<[^;]+>|HCEvent\w+|HCW38SituationPolicy|CargoBase|PlayerBase|PlayerIdentity|ItemBase|EntityAI|Object|ZombieBase|typename|Class|int|float|bool|string|vector)\s+(?=\w+\s*=)", "", token)
        bare = re.fullmatch(r"(?:ref )?(int|float|bool|string|vector|HCEvent\w+|HCW38SituationPolicy|CargoBase|PlayerBase|PlayerIdentity|ItemBase|Object|ZombieBase|typename|Class) (\w+)", token)
        if bare:
            token = bare[2] + " = " + {"int": "0", "float": "0.0", "bool": "False", "string": "''", "vector": "[0.,0.,0.]"}.get(bare[1], "None")
        token = token.replace("&&", " and ").replace("||", " or ")
        token = re.sub(r"!(?!=)", "not ", token)
        for a, b in (("true", "True"), ("false", "False"), ("null", "None")):
            token = re.sub(r"\b" + a + r"\b", b, token)
        if member:
            token = re.sub(r"\bm_\w+\b", lambda m: "self." + m[0], token)
            token = re.sub(r"\bthis\b", "self", token)
        if owner:
            for method in method_names:
                token = re.sub(r"(?<![\w.])" + method + r"\(", ("self." if member else owner + ".") + method + "(", token)
        if token.startswith("foreach ("):
            loop = re.fullmatch(r"foreach \((?:ref )?(?:\w+) (\w+) : (.+)\)", token)
            token = "for " + loop[1] + " in " + loop[2] + ":"
        elif token.startswith(("if (", "while (")):
            prefix, expr = token.split(" (", 1); token = prefix + " " + expr[:-1] + ":"
        elif token == "else": token += ":"
        token = re.sub(r"([\w.]+)\.Trim\(\)\.Length\(\)", r"len(\1.strip())", token)
        token = re.sub(r"([\w.]+)\.Length\(\)", r"len(\1)", token)
        token = re.sub(r"([\w.]+)\.Contains\(([^)]+)\)", r"(\2 in \1)", token)
        token = re.sub(r"([\w.]+)\.ToString\(\)", r"str(\1)", token)
        token = re.sub(r"([\w.]+)\.ToInt\(\)", r"native_int(\1)", token)
        token = re.sub(r"([\w.]+)\.IndexOf\(([^)]+)\)", r"\1.find(\2)", token)
        token = re.sub(r"([\w.]+)\.LastIndexOf\(([^)]+)\)", r"\1.rfind(\2)", token)
        token = re.sub(r"([\w.]+)\.Substring\(0, (.+)\)", r"\1[:\2]", token)
        token = re.sub(r"([\w.]+)\.Substring\((\w+), (.+)\)", r"\1[\2:\2 + (\3)]", token)
        lines.append("    " * indent + token)
    if len(lines) == 1:
        lines.append("    pass")
    try:
        exec(compile("\n".join(lines), "authored-event:" + name, "exec"), env)
    except SyntaxError as exc:
        raise AssertionError("\n".join(lines)) from exc
    return env["executed"]


def environment():
    data = "\n".join(p.read_text() for p in sorted((ROOT / "3_Game/Events").glob("*.c")))
    env = dict(EArray=EArray, len=len, str=str, Print=lambda text: None)
    # Synthetic budget boundary; actual guard control flow is covered by the W5 world smoke.
    env["HCWorkBudget"] = lambda: SimpleNamespace(HCReset=lambda *args: None,
        HCContinue=lambda: True, HCDeferred=lambda *args: None)
    env["HCEventQualification"] = SimpleNamespace(Admitted=lambda: True) # explicit synthetic admission
    env["HCEventSitesGate"] = SimpleNamespace(Admitted=lambda: False) # synthetic: reviewed sites stay closed unless a test opens them
    env["Vector"] = lambda x, y, z: [x, y, z]
    env["PlayerBase"] = SimpleNamespace(Cast=lambda value: value)
    env["Math"] = SimpleNamespace(AbsFloat=abs, Min=min, Max=max, Floor=math.floor, Sqrt=math.sqrt)
    env["vector"] = SimpleNamespace(DistanceSq=lambda a, b: sum((a[i]-b[i])**2 for i in range(3)), Zero=[0.0, 0.0, 0.0])
    for match in re.finditer(r"enum (\w+)\s*\{([^}]+)\}", data):
        env[match[1]] = SimpleNamespace(**{k: int(v) for k, v in re.findall(r"(\w+)\s*=\s*(\d+)", match[2])})
    for match in re.finditer(r"class (\w+)\s*\{", data):
        fields = re.findall(r"^\s*(?:ref )?([\w<> ]+?) (\w+)(?:\s*=\s*([^;]+))?;", body(data, match.end()), re.M)
        def factory(fields=fields):
            result = SimpleNamespace()
            for typ, name, value in fields:
                if "array<" in typ: default = EArray()
                elif typ == "vector": default = [0., 0., 0.]
                elif value: default = json.loads(value)
                else: default = {"string": "", "bool": False, "int": 0, "float": 0.}.get(typ)
                setattr(result, name, default)
            return result
        env[match[1]] = factory
    for match in re.finditer(r"class (\w+)\s*\{", data):
        consts = re.findall(r"static const int (\w+)\s*=\s*(\d+);", body(data, match.end()))
        if consts: env[match[1]] = SimpleNamespace(**{k: int(v) for k, v in consts})
    for name in ("HCEventDirector", "HCEventRuntimePolicy", "HCEventRoster", "HCEventSites", "HCEventBriefing"):
        text = (ROOT / ("4_World/Events/" + name + ".c")).read_text()
        env[name] = SimpleNamespace()
        for method in re.findall(r"static (?:void|bool|int|float|string|HCEvent\w+|array<[^>]+>) (\w+)\(", text):
            setattr(env[name], method, translate(text, method, env, name))
    env['HCMenuInput'] = SimpleNamespace(Lock=lambda: None, Unlock=lambda: None, BackPressed=lambda: False)
    return env


class Handle:
    def __init__(self, identity="alice", position=None, kind="SyntheticSupply"):
        self.identity = identity; self.position = position or [10., 0., 20.]
        self.parent = None
        self.kind = kind; self.owner = None; self.alive = True; self.deleted = False; self.ruined = False
    def GetIdentity(self): return self if self.identity else None
    def GetId(self): return self.identity
    def GetPosition(self): return self.position
    def GetType(self): return self.kind
    def IsAlive(self): return self.alive
    def GetInventory(self): return None  # Synthetic EntityAI without cargo.
    def IsPendingDeletion(self): return self.deleted
    def GetHierarchyRootPlayer(self): return self.owner
    def IsRuined(self): return self.ruined
    def GetHierarchyParent(self): return self.parent


class EventRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.e = environment(); self.p = self.e["HCEventRuntimePolicy"]
        self.code = self.e["HCEventCode"]; self.family = self.e["HCEventFamily"]
        self.ctx = self.e["HCEventContext"](); self.ctx.Server = True
        self.ctx.WorldName = "synthetic_world"; self.ctx.Session = "session-a"; self.ctx.Now = 100
        self.cfg = self.e["HCEventSettings"]()
        self.mission = self.e["HCEventMission"]()
        self.mission.Id = "supplies"; self.mission.SiteId = "synthetic-site"
        self.mission.WorldName = self.ctx.WorldName; self.mission.Reviewed = True
        self.mission.Family = self.family.RECOVERY; self.mission.ItemClass = "SyntheticSupply"
        self.mission.ContainerClass = "SyntheticContainer"; self.mission.AnchorClass = "SyntheticSite"
        self.mission.Source = [10., 0., 20.]; self.mission.Destination = [30., 0., 40.]

    def state(self):
        s = self.e["HCEventRuntimeState"](); s.Director = self.e["HCEventDirector"].Initialize(self.ctx.WorldName, self.ctx.Session)
        return s

    def runtime(self):
        env = self.e; test = self
        class Store:
            def __init__(self): self.image = None; self.calls = 0; self.fail_at = 0; self.invalid = False
            def Load(self, world): return None if self.invalid else copy.deepcopy(self.image or test.state())
            def Clone(self, state): return copy.deepcopy(state)
            def Save(self, state):
                self.calls += 1
                if self.calls == self.fail_at: return False
                self.image = copy.deepcopy(state); return True
        class Observer:
            def __init__(self): self.ready = True; self.evidence = None; self.released = []; self.prepared = []
            def Ready(self, mission): return self.ready
            def Prepare(self, lease, mission): self.prepared.append(lease); return True
            def Observe(self, run, player, now): return copy.deepcopy(self.evidence)
            def Release(self, lease): self.released.append(lease); return True
            def Forget(self, lease, participant): pass
        class AI:
            def __init__(self): self.ready = False; self.starts = []; self.stops = []; self.gone = False; self.start_ok = True
            def Ready(self, world): return self.ready
            def Start(self, lease, session, missionId, anchor, cap): self.starts.append(lease); return self.start_ok
            def Stop(self, lease): self.stops.append(lease); return True
            def Gone(self, lease): return self.gone
            def Observe(self, lease, participant): return None
        self.store = Store(); self.observer = Observer(); self.ai = AI()
        self.player = Handle()
        env["GetGame"] = lambda: SimpleNamespace(IsServer=lambda: True)
        env["HCEventSubscription"] = lambda: SimpleNamespace(EventId=0, ParticipantId="", Player=None)
        native = (ROOT / "4_World/Events/HCEventNativeObserver.c").read_text()
        env["HCEventNativeObserver"] = SimpleNamespace()
        env["HCEventNativeObserver"].Identity = translate(native, "Identity", env, "HCEventNativeObserver")
        source = (ROOT / "4_World/Events/HCEventRuntime.c").read_text()
        runtime_type = type("AuthoredRuntime", (), {})
        for name in re.findall(r"^    (?:bool|int|void|HCEvent\w+) (\w+)\(", source, re.M):
            setattr(runtime_type, name, translate(source, name, env, "HCEventRuntime", True))
        r = runtime_type(); r.m_State = None; r.m_Ready = False; r.m_LastNow = 0
        r.m_Subscriptions = EArray(); r.m_Cursor = 0
        self.assertTrue(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        return r

    def active(self, family=None):
        r = self.runtime()
        if family is not None: self.mission.Family = family
        self.assertEqual(self.code.OK, r.Announce(self.mission, self.ctx))
        self.assertEqual(self.code.OK, r.Join(1, self.player, self.ctx))
        return r

    def evidence(self, r, token="owned-object-1"):
        o = self.e["HCEventObjectiveEvidence"](); o.Observed = True
        o.Lease = r.m_State.Runs[0].Lease; o.Session = self.ctx.Session
        o.ParticipantId = "alice"; o.Sequence = 1; o.Token = token
        return o

    def test_enabled_preference_and_invalid_settings_fail_closed(self):
        self.assertTrue(self.cfg.Enabled)
        self.assertTrue(self.p.SettingsValid(self.cfg))
        for key, value in (("WorkPerTick", 0), ("MaxRuns", 33), ("MaxSubscriptions", 2881), ("MaxStoreBytes", 0)):
            cfg = copy.deepcopy(self.cfg); setattr(cfg, key, value)
            self.assertFalse(self.p.SettingsValid(cfg))

    def test_malformed_or_duplicate_site_configuration_refused(self):
        self.cfg.Sites.Insert(None); self.assertFalse(self.p.SettingsValid(self.cfg))
        site = self.e["HCEventSite"](); self.cfg.Sites = EArray([site])
        self.assertFalse(self.p.SettingsValid(self.cfg))
        site.Id = "site"; site.WorldName = self.ctx.WorldName
        self.assertTrue(self.p.SettingsValid(self.cfg))
        self.cfg.Sites.Insert(copy.deepcopy(site)); self.assertFalse(self.p.SettingsValid(self.cfg))

    def test_roster_contains_all_four_noncombat_families_and_optional_ai(self):
        site = self.e["HCEventSite"](); site.Id = "reviewed"; site.WorldName = self.ctx.WorldName
        site.Reviewed = True; site.Position = self.mission.Source; site.Destination = self.mission.Destination
        site.ItemClass = "SyntheticSupply"; site.ContainerClass = "SyntheticContainer"; site.AnchorClass = "SyntheticSite"
        result = self.e["HCEventRoster"].Build(site, True)
        self.assertEqual({m.Family for m in result}, {1, 2, 3, 4, 5, 6, 7})
        self.assertTrue(all(self.p.MissionValid(m, self.ctx.WorldName) for m in result))
        self.assertTrue(all(m.RewardUnits == 0 for m in result))
        site.Reviewed = False
        self.assertEqual([], self.e["HCEventRoster"].Build(site, True))

    def test_mission_world_numbers_and_rewards_are_validated(self):
        self.assertTrue(self.p.MissionValid(self.mission, self.ctx.WorldName))
        for key, value in (("Reviewed", False), ("WorldName", "wrong"), ("Family", 99),
                           ("RewardUnits", 1), ("Radius", float("nan")), ("Radius", 1001.),
                           ("DwellSeconds", 0), ("ItemClass", ""), ("Source", [float("inf"), 0, 0])):
            m = copy.deepcopy(self.mission); setattr(m, key, value)
            self.assertFalse(self.p.MissionValid(m, self.ctx.WorldName))

    def test_missing_observer_or_ai_disables_without_event_or_spawn(self):
        r = self.runtime(); self.observer.ready = False
        self.assertEqual(self.code.BLOCKED, r.Announce(self.mission, self.ctx))
        self.assertEqual([], r.m_State.Runs)
        self.mission.Family = self.family.AI_ENCOUNTER; self.mission.ActorBudget = 2
        self.observer.ready = True
        self.assertEqual(self.code.BLOCKED, r.Announce(self.mission, self.ctx))
        self.assertEqual([], self.ai.starts)

    def test_participation_requires_native_identity_not_client_id(self):
        r = self.runtime(); self.assertEqual(0, r.Announce(self.mission, self.ctx))
        for player in (None, Handle(identity=""), Handle(identity=" ")):
            self.assertNotEqual(0, r.Join(1, player, self.ctx))
        self.assertEqual([], r.m_State.Director.Records[0].Participants)
        self.assertEqual(0, r.Join(1, self.player, self.ctx))
        self.assertEqual(["alice"], r.m_State.Director.Records[0].Participants)

    def test_observation_completes_once_with_no_rewards_or_spawning(self):
        r = self.active(); self.observer.evidence = self.evidence(r)
        r.Tick(self.ctx)
        self.assertEqual(self.e["HCEventStatus"].COMPLETED, r.m_State.Director.Records[0].Status)
        self.assertEqual(1, r.m_State.Director.Records[0].Progress)
        r.Tick(self.ctx)
        self.assertEqual(1, r.m_State.Director.Records[0].Progress)
        self.assertEqual([], self.ai.starts)

    def test_wrong_session_lease_participant_and_replay_do_not_progress(self):
        r = self.active(); baseline = copy.deepcopy(r.m_State)
        for key, value in (("Observed", False), ("Session", "old"), ("Lease", "other"),
                           ("ParticipantId", "outsider"), ("Sequence", 2), ("Token", "")):
            o = self.evidence(r); setattr(o, key, value); self.observer.evidence = o
            r.Tick(self.ctx)
            self.assertEqual(0, r.m_State.Director.Records[0].Progress)
        self.assertEqual(baseline.Runs[0].Tokens, r.m_State.Runs[0].Tokens)

    def test_opt_out_disconnect_and_new_connection_need_explicit_join(self):
        r = self.active(); r.Disconnect(self.player, self.ctx)
        self.assertEqual([], r.m_State.Director.Records[0].Participants)
        self.observer.evidence = self.evidence(r); r.Tick(self.ctx)
        self.assertEqual(0, r.m_State.Director.Records[0].Progress)
        replacement = Handle()
        self.assertEqual(0, r.Join(1, replacement, self.ctx))
        self.assertNotEqual(0, r.Leave(1, self.player, self.ctx))

    def test_expiry_cancel_and_cleanup_are_idempotent(self):
        r = self.active(); self.ctx.Now = r.m_State.Director.Records[0].Expires
        r.Tick(self.ctx)
        self.assertEqual(self.e["HCEventStatus"].EXPIRED, r.m_State.Director.Records[0].Status)
        self.assertEqual(self.e["HCEventRunPhase"].CLOSED, r.m_State.Runs[0].Phase)
        self.assertNotEqual(0, r.Join(1, self.player, self.ctx))
        before = self.store.calls; r.Tick(self.ctx); self.assertEqual(before, self.store.calls)

    def test_persistence_failure_prevents_publication_and_provider_start(self):
        r = self.runtime(); self.mission.Family = self.family.AI_ENCOUNTER; self.mission.ActorBudget = 2
        self.ai.ready = True; self.store.fail_at = self.store.calls + 1
        self.assertNotEqual(0, r.Announce(self.mission, self.ctx))
        self.assertFalse(r.m_Ready); self.assertEqual([], self.ai.starts)

    def test_ai_start_intent_is_durable_and_failure_never_claims_cleanup(self):
        r = self.runtime(); self.mission.Family = self.family.AI_ENCOUNTER; self.mission.ActorBudget = 2
        self.ai.ready = True; self.ai.start_ok = False
        self.assertNotEqual(0, r.Announce(self.mission, self.ctx))
        self.assertTrue(self.store.image.Runs[0].ProviderIntent)
        self.assertEqual(1, len(self.ai.starts)); self.assertGreaterEqual(len(self.ai.stops), 1)
        self.assertNotEqual(self.e["HCEventRunPhase"].CLOSED, r.m_State.Runs[0].Phase)

    def test_restart_cancels_without_respawn_and_requires_cleanup_confirmation(self):
        r = self.runtime(); self.mission.Family = self.family.AI_ENCOUNTER; self.mission.ActorBudget = 2
        self.ai.ready = True; self.assertEqual(0, r.Announce(self.mission, self.ctx))
        starts = len(self.ai.starts); self.ctx.Session = "session-b"; self.ctx.Now = 0
        r.m_Subscriptions = EArray()
        self.assertTrue(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        self.assertEqual(starts, len(self.ai.starts))
        self.assertEqual(self.e["HCEventStatus"].CANCELLED, r.m_State.Director.Records[0].Status)
        self.assertNotEqual(self.e["HCEventRunPhase"].CLOSED, r.m_State.Runs[0].Phase)
        self.ai.gone = True; r.Tick(self.ctx)
        self.assertEqual(self.e["HCEventRunPhase"].CLOSED, r.m_State.Runs[0].Phase)

    def test_100_restarts_with_full_roster_keep_monotonic_bounded_journal(self):
        r = self.runtime()
        site = self.e["HCEventSite"]()
        site.Id = "retention"; site.WorldName = self.ctx.WorldName; site.Reviewed = True
        site.Position = self.mission.Source; site.Destination = self.mission.Destination
        site.ItemClass = "SyntheticSupply"; site.ContainerClass = "SyntheticContainer"; site.AnchorClass = "SyntheticSite"
        self.ai.ready = True; self.ai.gone = True
        roster = self.e["HCEventRoster"].Build(site, True)
        last_id = 0
        for boot in range(100):
            self.ctx.Session = "boot-" + str(boot); self.ctx.Now = 0
            self.assertTrue(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai), boot)
            r.Tick(self.ctx)  # Confirm prior provider cleanup before retention.
            for mission in roster:
                self.assertEqual(0, r.Announce(mission, self.ctx), (boot, mission.Id))
                current = r.m_State.Director.Records[-1].Id
                self.assertGreater(current, last_id); last_id = current
            self.assertLessEqual(len(r.m_State.Runs), 32)
            self.assertLessEqual(len(r.m_State.Director.Sessions), 33)
            self.assertTrue(self.p.StateValid(self.store.image))
        self.assertEqual(700, last_id)
        self.assertGreater(r.m_State.Director.PrunedThrough, 0)
        # All operations must use durable IDs, rather than array offsets.
        self.assertEqual(0, r.Join(last_id, self.player, self.ctx))
        self.assertEqual(0, r.Leave(last_id, self.player, self.ctx))
        self.assertEqual(0, r.Cancel(last_id, self.ctx))
        self.assertNotEqual(0, r.Join(1, self.player, self.ctx))

    def test_restart_closes_full_retention_before_first_announcement(self):
        # Explicit synthetic journal/provider; no Tick between restart and Announce.
        r = self.runtime()
        for index in range(32):
            self.mission.Id = "synthetic-retained-" + str(index)
            self.assertEqual(self.code.OK, r.Announce(self.mission, self.ctx))
        release = self.observer.Release
        self.observer.Release = lambda lease: False
        self.assertEqual(self.code.OK, r.Cancel(1, self.ctx))
        self.assertEqual(self.e["HCEventRunPhase"].CLEANUP, self.store.image.Runs[0].Phase)
        self.observer.Release = release
        self.ctx.Session = "synthetic-restart"; self.ctx.Now = 0
        self.assertTrue(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        self.mission.Id = "synthetic-first-roster-mission"
        self.assertEqual(self.code.OK, r.Announce(self.mission, self.ctx))
        self.assertEqual(33, r.m_State.Runs[-1].EventId)
        self.assertEqual(32, len(r.m_State.Runs))

    def test_retention_never_discards_unclosed_native_intent(self):
        self.cfg.MaxRuns = 1
        r = self.runtime(); self.ai.ready = True
        self.mission.Family = 5; self.mission.ActorBudget = 2
        self.assertEqual(0, r.Announce(self.mission, self.ctx))
        self.ctx.Session = "next"; self.ctx.Now = 0
        self.assertTrue(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        before = copy.deepcopy(r.m_State); logs = []; self.e["Print"] = logs.append
        self.assertEqual(self.code.LIMIT, r.Announce(self.mission, self.ctx))
        self.assertEqual(before, r.m_State)
        # The refusal names the blocking run instead of a bare limit code.
        blocking = [line for line in logs if "retention blocked" in line]
        self.assertEqual(1, len(blocking))
        self.assertIn(before.Runs[0].Lease, blocking[0])
        self.ai.gone = True; r.Tick(self.ctx)
        self.assertEqual(0, r.Announce(self.mission, self.ctx))
        self.assertEqual([2], [run.EventId for run in r.m_State.Runs])
        self.assertEqual(0, r.Cancel(2, self.ctx))
        # Current-session tombstones protect against proposal replay.
        self.assertNotEqual(0, r.Announce(self.mission, self.ctx))

    def test_failed_restart_uses_loaded_session_for_confirmed_cleanup(self):
        r = self.runtime(); self.ai.ready = True
        self.mission.Family = 5; self.mission.ActorBudget = 2
        self.assertEqual(0, r.Announce(self.mission, self.ctx))
        self.ctx.Session = "x" * 97
        self.assertFalse(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        self.assertFalse(r.Stop(self.ctx))
        self.ai.gone = True
        self.assertTrue(r.Stop(self.ctx))
        self.assertTrue(r.CleanupComplete())

    def test_clock_rollback_world_session_and_disabled_preference_refuse(self):
        r = self.active(); before = copy.deepcopy(r.m_State)
        for key, value in (("Now", 99), ("Session", "old"), ("WorldName", "wrong"), ("Server", False)):
            context = copy.deepcopy(self.ctx); setattr(context, key, value)
            self.assertNotEqual(0, r.Join(1, Handle(identity="bob"), context))
            r.Tick(context); self.assertEqual(before, r.m_State)
        r.m_Settings.Enabled = False
        self.assertNotEqual(0, r.Join(1, Handle(identity="bob"), self.ctx))

    def test_corrupt_store_blocks_start_and_cannot_fall_back_to_fresh_state(self):
        r = self.runtime(); self.store.invalid = True
        self.assertFalse(r.Start(self.cfg, self.ctx, self.store, self.observer, self.ai))
        self.assertFalse(r.m_Ready); self.assertEqual([], self.ai.starts)

    def test_state_and_roster_snapshots_are_immutable_to_callers(self):
        r = self.active(); self.mission.Goal = 99
        self.assertEqual(1, r.m_State.Runs[0].Objective.Goal)
        snapshot = r.Snapshot(); snapshot.Runs[0].Objective.Goal = 99
        self.assertEqual(1, r.m_State.Runs[0].Objective.Goal)

    def test_provider_reentrant_mutation_is_rejected(self):
        r = self.runtime(); results = []
        def ready(mission):
            results.append(r.Announce(mission, self.ctx)); return True
        self.observer.Ready = ready
        self.assertEqual(0, r.Announce(self.mission, self.ctx))
        self.assertEqual([self.code.DENIED], results)
        self.assertEqual(1, len(r.m_State.Runs))

    def test_terminal_cleanup_reclaims_subscription_capacity(self):
        self.cfg.MaxSubscriptions = 1
        r = self.active(); self.observer.evidence = self.evidence(r); r.Tick(self.ctx)
        self.assertEqual([], r.m_Subscriptions)
        self.mission.Id = "second"; self.assertEqual(0, r.Announce(self.mission, self.ctx))
        self.assertEqual(0, r.Join(2, self.player, self.ctx))

    def test_provider_cannot_mutate_owned_runtime_record(self):
        r = self.active()
        def malicious(run, player, now):
            run.Objective.Goal = 99; run.Tokens.Insert("forged"); return None
        self.observer.Observe = malicious
        r.Tick(self.ctx)
        self.assertEqual(1, r.m_State.Runs[0].Objective.Goal)
        self.assertEqual([], r.m_State.Runs[0].Tokens)

    def test_run_definition_mismatch_refused_before_start(self):
        r = self.active(); image = copy.deepcopy(r.m_State)
        for key, value in (("ActorBudget", 64), ("MaxParticipants", 90), ("LifetimeSeconds", 700)):
            candidate = copy.deepcopy(image); setattr(candidate.Runs[0].Objective, key, value)
            self.assertFalse(self.p.StateValid(candidate), key)

    def test_optout_resets_provider_dwell_before_rejoin(self):
        r = self.active(); forgotten = []
        self.observer.Forget = lambda lease, player: forgotten.append((lease, player))
        self.assertEqual(0, r.Leave(1, self.player, self.ctx))
        self.assertEqual([(r.m_State.Runs[0].Lease, self.player)], forgotten)

    def test_post_start_save_failure_requests_owned_ai_stop_without_closed_claim(self):
        r = self.runtime(); self.ai.ready = True; self.mission.Family = 5; self.mission.ActorBudget = 2
        self.store.fail_at = self.store.calls + 2
        self.assertNotEqual(0, r.Announce(self.mission, self.ctx))
        self.assertEqual(self.ai.starts, self.ai.stops)
        self.assertFalse(r.m_Ready)
        self.assertNotEqual(self.e["HCEventRunPhase"].CLOSED, r.m_State.Runs[0].Phase)

    def test_periodic_dead_handle_disconnects_without_rebinding_respawn(self):
        r = self.active(); self.player.alive = False; r.Tick(self.ctx)
        self.assertEqual([], r.m_State.Director.Records[0].Participants)
        self.assertEqual([], r.m_Subscriptions)

    def test_ai_cleanup_reservations_count_until_gone(self):
        r = self.runtime(); self.ai.ready = True; self.mission.Family = 5; self.mission.ActorBudget = 64
        self.assertEqual(0, r.Announce(self.mission, self.ctx)); self.assertEqual(0, r.Cancel(1, self.ctx))
        self.mission.Id = "second"
        self.assertEqual(self.code.LIMIT, r.Announce(self.mission, self.ctx))
        self.ai.gone = True; r.Tick(self.ctx)
        self.assertEqual(0, r.Announce(self.mission, self.ctx))

    def test_shutdown_cancels_durably_even_when_preference_toggled_off(self):
        r = self.active(); r.m_Settings.Enabled = False
        r.Stop(self.ctx)
        self.assertFalse(r.m_Ready); self.assertEqual([], r.m_Subscriptions)
        self.assertEqual(self.e["HCEventStatus"].CANCELLED, self.store.image.Director.Records[0].Status)
        self.assertEqual(self.e["HCEventRunPhase"].CLOSED, self.store.image.Runs[0].Phase)


class NativeObservationTests(unittest.TestCase):
    def setUp(self):
        helper = EventRuntimeTests(); helper.setUp()
        self.e = helper.e; self.mission = helper.mission
        self.e["GetGame"] = lambda: SimpleNamespace(IsServer=lambda: True)
        for name, fields in (("HCEventTarget", dict(MissionId="", Item=None, DeliveryContainer=None, Presence=None, Infected=None)),
                             ("HCEventNativeLease", dict(Lease="", Objective=None, Item=None, DeliveryContainer=None, Presence=None, Infected=None, DeliveredBy=None, KillerId="")),
                             ("HCEventDwell", dict(Lease="", Player=None, Since=0, Last=0))):
            self.e[name] = lambda fields=fields: SimpleNamespace(**fields)
        source = (ROOT / "4_World/Events/HCEventNativeObserver.c").read_text()
        cls = type("AuthoredNativeObserver", (), {})
        for name in re.findall(r"^    (?:override )?(?:bool|int|void|HCEvent\w+) (\w+)\(", source, re.M):
            setattr(cls, name, translate(source, name, self.e, "HCEventNativeObserver", True))
        cls.Identity = staticmethod(translate(source, "Identity", self.e, "HCEventNativeObserver"))
        self.e["HCEventNativeObserver"] = cls
        self.o = cls(); self.o.m_Targets = EArray(); self.o.m_Leases = EArray(); self.o.m_Dwells = EArray()
        self.player = Handle(); self.item = Handle(identity="")
        self.run = self.e["HCEventRun"](); self.run.EventId = 1
        self.run.Lease = "session-a:1"; self.run.Objective = self.mission

    def bind(self):
        self.assertTrue(self.o.RegisterTarget(self.mission.Id, self.item))
        self.assertTrue(self.o.Ready(self.mission)); self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))

    def test_exact_existing_handle_and_custody_required(self):
        self.bind(); self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.item.owner = Handle(identity="outsider")
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.item.owner = self.player; result = self.o.Observe(self.run, self.player, 100)
        self.assertTrue(result.Observed); self.assertEqual("alice", result.ParticipantId)
        self.assertEqual("session-a", result.Session)

    def test_lease_without_session_separator_is_not_observed(self):
        # Substring(0, -1) raises Wrong parameter value in Enforce (checks WP-3, HC-E006).
        self.run.Lease = "nosession"
        self.bind(); self.item.owner = self.player
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))

    def test_delivery_and_static_salvage_use_distinct_locations(self):
        self.mission.Family = 2
        self.assertTrue(self.o.RegisterTarget(self.mission.Id, self.item))
        container = Handle(identity="", position=[30.,0.,40.], kind="SyntheticContainer")
        self.assertTrue(self.o.RegisterContainer(self.mission.Id, container))
        self.assertTrue(self.o.Prepare(self.run.Lease, self.mission)); self.item.owner = self.player
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.player.position = [30.,0.,40.]
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.item.owner = None; self.item.parent = container
        self.o.RecordDelivery(self.run.Lease, self.item, self.player, container)
        self.assertTrue(self.o.Observe(self.run, self.player, 100).Observed)
        self.mission.Family = 4
        self.assertIsNone(self.o.Observe(self.run, self.player, 100))

    def test_invalid_target_kind_ruin_owner_and_source_not_admitted(self):
        for field, value in (("kind", "Wrong"), ("ruined", True), ("deleted", True),
                             ("owner", self.player), ("position", [500.,0.,500.])):
            original = getattr(self.item, field); setattr(self.item, field, value)
            self.o.m_Targets.Clear(); self.assertTrue(self.o.RegisterTarget(self.mission.Id, self.item) or self.item.deleted)
            self.assertFalse(self.o.Ready(self.mission), field); setattr(self.item, field, original)

    def test_dwell_is_continuous_bounded_samples_and_handle_specific(self):
        self.mission.Family = 3; self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        for now in (100, 105): self.assertIsNone(self.o.Observe(self.run, self.player, now))
        self.assertTrue(self.o.Observe(self.run, self.player, 110).Observed)
        self.assertIsNone(self.o.Observe(self.run, self.player, 120)) # missing samples reset
        self.assertIsNone(self.o.Observe(self.run, Handle(), 125)) # reconnect not inherited
        self.player.position = [500.,0.,500.]; self.assertIsNone(self.o.Observe(self.run, self.player, 125))
        self.player.position = [10.,0.,20.]; self.assertIsNone(self.o.Observe(self.run, self.player, 126))

    def test_dead_or_deleted_player_never_observed_and_optout_resets_dwell(self):
        self.mission.Family = 3; self.assertTrue(self.o.Prepare(self.run.Lease, self.mission))
        self.o.Observe(self.run, self.player, 100); self.o.Forget(self.run.Lease, self.player)
        self.assertIsNone(self.o.Observe(self.run, self.player, 105))
        self.player.alive = False; self.assertIsNone(self.o.Observe(self.run, self.player, 110))
        self.player.alive = True; self.assertIsNone(self.o.Observe(self.run, self.player, 111))

    def test_foreign_lease_cannot_observe_and_cleanup_never_deletes_item(self):
        self.bind(); self.item.owner = self.player
        self.run.Lease = "foreign"; self.assertIsNone(self.o.Observe(self.run, self.player, 100))
        self.assertTrue(self.o.Release("foreign")); self.assertEqual(1, len(self.o.m_Leases))
        self.assertTrue(self.o.Release("session-a:1")); self.assertEqual([], self.o.m_Leases)
        self.assertFalse(self.item.deleted); self.assertIs(self.player, self.item.owner)

    def test_same_target_cannot_be_registered_or_leased_twice(self):
        self.bind(); self.assertFalse(self.o.RegisterTarget("second", self.item))
        self.assertFalse(self.o.Prepare("session-a:2", self.mission))


class EventJournalTests(unittest.TestCase):
    def setUp(self):
        self.e = environment(); env = self.e
        source = (ROOT / "4_World/Events/HCEventJournal.c").read_text()
        env["native_int"] = lambda text: int(text) if re.fullmatch(r"[0-9]+", text) else 0
        class Codec:
            # Explicit synthetic native JSON/hash seam, not journal decisions.
            def Encode(self, data):
                return json.dumps(data, default=lambda obj: vars(obj), sort_keys=True, separators=(",", ":"))
            def EncodeReceipt(self, data): return self.Encode(data)
            def Decode(self, text):
                from tests.legacy.json_loader_port import decode_json
                return decode_json(text, 'HCEventRuntimeState', EArray)
            def Receipt(self, text):
                from tests.legacy.json_loader_port import decode_json
                return decode_json(text, 'HCEventJournalReceipt', EArray)
            def Digest(self, text): return int(hashlib.sha256(text.encode()).hexdigest()[:7], 16)
        class IO:
            def __init__(self): self.files = {}; self.writes = 0; self.fail_at = 0; self.fail_remove = False
            def Names(self): return EArray(sorted(self.files))
            def Read(self, name, limit):
                value = self.files.get(name, ""); return value if 0 < len(value) <= limit else ""
            def WriteNew(self, name, text, limit):
                self.writes += 1
                if name in self.files or self.writes == self.fail_at or not 0 < len(text) <= limit: return False
                self.files[name] = text; return True
            def Exists(self, name): return name in self.files
            def Remove(self, name):
                if self.fail_remove: return False
                del self.files[name]; return True
        self.io = IO(); self.codec = Codec(); self.cfg = env["HCEventSettings"]()
        cls = type("AuthoredJournal", (), {})
        source = source[source.index("class HCEventJournal :"):]
        for name in re.findall(r"^    (?:override )?(?:bool|int|string|void|HCEvent\w+) (\w+)\(", source, re.M):
            setattr(cls, name, translate(source, name, env, "HCEventJournal", True))
        self.cls = cls; self.j = self.open()

    def open(self):
        j = self.cls(); j.m_IO = self.io; j.m_Codec = self.codec; j.m_Settings = self.cfg
        j.m_Latest = 0; j.m_Image = ""; j.m_Fault = False; j.m_World = ""
        return j

    def save(self, j, state):
        state.Revision += 1; return j.Save(state)

    def test_empty_roundtrip_and_deep_clone(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        clone = self.j.Clone(state); clone.Director.WorldName = "other"
        self.assertEqual("synthetic_world", state.Director.WorldName)
        self.assertEqual(state, self.open().Load("synthetic_world"))

    def test_each_interrupted_write_refuses_latest_not_fallback(self):
        for stage in (1,2,3):
            self.io.files.clear(); self.io.writes = 0; self.io.fail_at = 0
            j = self.open(); state = j.Load("synthetic_world"); self.assertTrue(self.save(j, state))
            self.io.fail_at = self.io.writes + stage
            self.assertFalse(self.save(j, state))
            if stage == 1: self.assertIsNotNone(self.open().Load("synthetic_world"))
            else: self.assertIsNone(self.open().Load("synthetic_world"))

    def test_corrupt_latest_image_commit_and_missing_intent_refuse(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        original = dict(self.io.files)
        for name in ("image-1.json", "commit-1.json", "intent-1.json"):
            self.io.files = dict(original); self.io.files[name] = "[]"
            self.assertIsNone(self.open().Load("synthetic_world"), name)
        self.io.files = dict(original); del self.io.files["intent-1.json"]
        self.assertIsNone(self.open().Load("synthetic_world"))

    def test_wrong_world_and_noncanonical_or_unrelated_names_refuse(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        self.assertIsNone(self.open().Load("other_world"))
        original = dict(self.io.files)
        for name in ("image-01.json", "../image-1.json", "notes.txt", "image-1000000000.json"):
            self.io.files = dict(original); self.io.files[name] = "unrelated"
            self.assertIsNone(self.open().Load("synthetic_world"), name)
            self.assertEqual("unrelated", self.io.files[name])

    def test_store_quota_checked_before_any_intent(self):
        state = self.j.Load("synthetic_world"); self.cfg.MaxStoreBytes = 16384
        state.Director.Session = "x" * 20000
        self.assertFalse(self.save(self.j, state)); self.assertEqual({}, self.io.files)

    def test_drift_since_load_refuses_write_and_preserves_evidence(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        self.io.files["image-1.json"] += " "
        before = dict(self.io.files); self.assertFalse(self.save(self.j, state))
        self.assertEqual(before, self.io.files)

    def test_commit_drift_since_load_is_not_ignored(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        self.io.files["commit-1.json"] = "[]"; before = dict(self.io.files)
        self.assertFalse(self.save(self.j, state)); self.assertEqual(before, self.io.files)

    def test_revision_replay_and_foreign_future_intent_refused(self):
        state = self.j.Load("synthetic_world"); self.assertTrue(self.save(self.j, state))
        self.assertFalse(self.j.Save(state))
        j = self.open(); self.assertIsNotNone(j.Load("synthetic_world"))
        self.io.files["intent-2.json"] = "foreign"
        before = dict(self.io.files); self.assertFalse(self.save(j, state)); self.assertEqual(before, self.io.files)

    def test_retention_is_bounded_and_deletion_failure_faults(self):
        state = self.j.Load("synthetic_world")
        for _ in range(10): self.assertTrue(self.save(self.j, state))
        self.assertEqual(24, len(self.io.files)); self.assertNotIn("image-1.json", self.io.files)
        self.assertIsNotNone(self.open().Load("synthetic_world"))
        self.io.fail_remove = True; self.assertFalse(self.save(self.j, state))
        self.assertTrue(self.j.m_Fault)

    def test_legacy_image_loads_with_zero_retention_floors_without_reset(self):
        state = self.j.Load("synthetic_world")
        # A full old journal, rather than just an empty DTO, must migrate.
        helper = EventRuntimeTests(); helper.setUp()
        state.Director.Sessions.Clear()
        for index in range(32):
            session = "legacy-" + str(index)
            state.Director.Sessions.Insert(session)
            record = self.e["HCEventRecord"](); record.Id = index + 1
            record.Session = session; record.Status = 6; record.Expires = 1800
            record.Definition = self.e["HCEventRuntimePolicy"].Definition(helper.mission)
            state.Director.Records.Insert(record)
            run = self.e["HCEventRun"](); run.EventId = record.Id
            run.Lease = session + ":" + str(record.Id); run.Objective = copy.deepcopy(helper.mission)
            run.ProviderIntent = True; run.Phase = 3
            state.Runs.Insert(run)
        state.Director.Session = "legacy-31"; state.Director.NextId = 33
        for field in ("PrunedThrough", "SessionGeneration"):
            if hasattr(state.Director, field): delattr(state.Director, field)
        state.Revision = 1
        image = self.codec.Encode(state)
        receipt = SimpleNamespace(Version=1, Revision=1, WorldName="synthetic_world",
                                  Length=len(image), Hash=self.codec.Digest(image))
        intent = self.codec.EncodeReceipt(receipt)
        self.io.files = {"intent-1.json": intent, "image-1.json": image, "commit-1.json": intent}
        restored = self.open().Load("synthetic_world")
        self.assertIsNotNone(restored)
        self.assertEqual(0, restored.Director.PrunedThrough)
        self.assertEqual(0, restored.Director.SessionGeneration)
        self.assertEqual(1, restored.Revision)
        self.assertEqual(image, self.io.files["image-1.json"])
        runtime = helper.runtime()
        helper.ctx.Session = "migrated"
        journal = self.open()
        self.assertTrue(runtime.Start(helper.cfg, helper.ctx, journal, helper.observer, helper.ai))
        self.assertEqual(0, runtime.Announce(helper.mission, helper.ctx))
        self.assertEqual(33, runtime.m_State.Runs[-1].EventId)
        self.assertEqual(1, runtime.m_State.Director.PrunedThrough)

    def test_unsupported_schema_has_explicit_admission_error_and_preserves_bytes(self):
        state = self.j.Load("synthetic_world"); state.Version = 2; state.Revision = 1
        image = self.codec.Encode(state)
        receipt = SimpleNamespace(Version=1, Revision=1, WorldName="synthetic_world",
                                  Length=len(image), Hash=self.codec.Digest(image))
        intent = self.codec.EncodeReceipt(receipt)
        self.io.files = {"intent-1.json": intent, "image-1.json": image, "commit-1.json": intent}
        before = dict(self.io.files); logs = []; self.e["Print"] = logs.append
        self.assertIsNone(self.open().Load("synthetic_world"))
        self.assertEqual(before, self.io.files)
        self.assertTrue(any("schema" in line and "admission" in line for line in logs))


class NativeJournalEnumerationTests(unittest.TestCase):
    def enumerate(self, rows, valid_handle=True):
        source = (ROOT / "4_World/Events/HCEventJournal.c").read_text().split("class HCEventCodec")[0]
        # Native out parameters become tuples; decisions stay in Names().
        source = source.replace("FindFileHandle handle = FindFile(", "handle, name, attributes = FindFile(")
        source = source.replace("more = FindNextFile(", "more, name, attributes = FindNextFile(")
        source = source.replace("FileAttr attributes;", "int attributes;")
        remaining = list(rows); closed = []
        def next_row(*args):
            if remaining:
                name, attr = remaining.pop(0); return True, name, attr
            return False, "", 1
        def first(*args):
            _, name, attr = next_row(); return (1 if valid_handle else 0), name, attr
        env = dict(EArray=EArray, len=len, str=str, FileAttr=SimpleNamespace(DIRECTORY=0),
                   FindFileFlags=SimpleNamespace(ALL=2), FindFile=first, FindNextFile=next_row,
                   CloseFindFile=lambda handle: closed.append(handle))
        method = translate(source, "Names", env, "HCEventJournalIO", True)
        obj = SimpleNamespace(m_Root="synthetic", Ensure=lambda: True)
        return method(obj), closed

    def test_empty_native_enumeration_is_empty_and_closes_handle(self):
        names, closed = self.enumerate([])
        self.assertEqual([], names); self.assertEqual([1], closed)

    def test_native_directory_attribute_is_zero_not_bitmask(self):
        names, closed = self.enumerate([("foreign-directory", 0)])
        self.assertIsNone(names); self.assertEqual([1], closed)

    def test_enumeration_cap_refuses_before_unbounded_growth(self):
        names, closed = self.enumerate([(str(i),1) for i in range(28)])
        self.assertIsNone(names); self.assertEqual([1], closed)


class EventConfigurationTests(unittest.TestCase):
    def loader(self):
        env = environment(); source = (ROOT / "4_World/Events/HCEventConfiguration.c").read_text()
        source = source[source.index("class HCEventConfiguration\n"):]
        cls = type("AuthoredConfiguration", (), {})
        for name in re.findall(r"^    (?:HCEvent\w+|bool) (\w+)\(", source, re.M):
            setattr(cls, name, translate(source, name, env, "HCEventConfiguration", True))
        class IO:
            def __init__(self): self.text = ""; self.exists = False; self.writes = 0
            def Ensure(self): return True
            def Exists(self, name): return self.exists
            def Read(self, name, limit): return self.text if len(self.text) <= limit else ""
            def WriteNew(self, name, text, limit):
                if self.exists: return False
                self.writes += 1; self.text = text; self.exists = True; return True
        class Codec:
            def Encode(self, config): return json.dumps(vars(config), default=lambda value: vars(value))
            def Decode(self, text):
                from tests.legacy.json_loader_port import decode_json
                return decode_json(text, 'HCEventSettings', EArray)
        obj = cls(); obj.m_IO = IO(); obj.m_Codec = Codec()
        return obj, env

    def test_missing_config_generates_enabled_template_once(self):
        loader, env = self.loader(); cfg = loader.Load()
        self.assertTrue(cfg.Enabled); self.assertEqual(2, len(cfg.Sites))
        self.assertEqual(1, loader.m_IO.writes); self.assertTrue(loader.Load().Enabled)
        self.assertEqual(1, loader.m_IO.writes)

    def test_explicit_disable_and_existing_invalid_config_never_overwritten(self):
        loader, env = self.loader(); loader.m_IO.exists = True
        # Explicit complete synthetic config; missing scalar keys native-zero.
        disabled = json.loads(loader.m_Codec.Encode(env['HCEventSettings']()))
        disabled['Enabled'] = False
        loader.m_IO.text = json.dumps(disabled)
        self.assertFalse(loader.Load().Enabled)
        for text in ("not-json", "[]", '{"WorkPerTick":0}', "x" * 16385):
            loader.m_IO.text = text; self.assertIsNone(loader.Load())
            self.assertEqual(text, loader.m_IO.text); self.assertEqual(0, loader.m_IO.writes)


class EventModuleLifecycleTests(unittest.TestCase):
    def module(self):
        env = environment(); self.time = 120.; self.server = True; self.calls = []
        env["GetGame"] = lambda: SimpleNamespace(IsServer=lambda: self.server,
            GetTickTime=lambda: self.time, GetWorldName=lambda: "synthetic_world")
        env["Math"].Floor = math.floor
        source = (ROOT / "4_World/Events/HCEventModule.c").read_text()
        source = re.sub(r"GetGame\(\)\.GetWorldName\((\w[\w.]*)\);", r"\1 = GetGame().GetWorldName();", source)
        source = re.sub(r"\bs_(Instance|CleanupOwner)\b", r"HCEventModule.s_\1", source)
        # Explicit synthetic V2 collaborators: actual situation execution lives
        # in test_hc_situations; this fixture isolates legacy clock/cleanup.
        cls = type("AuthoredModule", (), {"s_Instance": None, "s_CleanupOwner": None,
            "HCStepSituations": lambda self: None, "HCCloseSituations": lambda self: None})
        env["HCEventModule"] = cls
        for name in ("Context", "OnTick", "PlayerDisconnected", "OnStop"):
            setattr(cls, name, translate(source, name, env, "HCEventModule", True))
        obj = cls(); obj.m_StartedAt = 100.; obj.m_Session = "synthetic-session"
        obj.m_EventRPC = None; obj.m_Stopping = False; cls.s_Instance = obj
        obj.m_CleanupAttempts = 0; obj.m_Quarantined = False
        obj.m_Runtime = SimpleNamespace(Tick=lambda ctx:self.calls.append(("tick",ctx)),
            Stop=lambda ctx:(self.calls.append(("stop",ctx)) or True),
            Disconnect=lambda player,ctx:self.calls.append(("disconnect",player,ctx)))
        return obj, env

    def test_clock_context_uses_current_native_world_and_monotonic_session_seconds(self):
        obj, env = self.module(); context = obj.Context()
        self.assertTrue(context.Server); self.assertEqual(20, context.Now)
        self.assertEqual("synthetic_world", context.WorldName)
        self.assertEqual("synthetic-session", context.Session)
        for value in (99., float("nan"), float("inf")):
            self.time = value; self.assertFalse(obj.Context().Server)

    def test_invalid_runtime_clock_stops_module_instead_of_silent_live_status(self):
        obj, env = self.module(); self.time = 99.; obj.OnTick(1.)
        self.assertEqual("stop", self.calls[0][0]); self.assertIsNone(obj.m_Runtime)

    def test_disconnect_hook_preserves_native_chain_and_server_attribution(self):
        obj, env = self.module(); env["HCEventModule"] = SimpleNamespace(Get=lambda:obj)
        env["super_OnDisconnect"] = lambda:self.calls.append(("super",))
        source = (ROOT / "4_World/Events/HCEventPlayerLifecycle.c").read_text()
        source = source.replace("super.OnDisconnect()", "super_OnDisconnect()")
        disconnect = translate(source, "OnDisconnect", env, "PlayerBase", True)
        player = Handle(); disconnect(player)
        self.assertEqual(["disconnect","super"], [row[0] for row in self.calls])
        self.assertIs(player, self.calls[0][1]); self.calls.clear(); self.server = False
        disconnect(player); self.assertEqual([("super",)], self.calls)



if __name__ == "__main__": unittest.main()
