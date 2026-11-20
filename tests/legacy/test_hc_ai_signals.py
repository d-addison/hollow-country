"""HC-5/#148/#139: explicit synthetic native/provider/storage ports.

Executes authored decisions through the existing restricted Enforce translator.
No Python gameplay model and no claim of observed DayZ emote/cease-fire behavior.
Banso trace: HC-5 observed signals + remembered betrayal, Wave 1; HC-11 owns docs.
The named spec/plan documents are absent in this portable checkout; the assigned
HC-5 contract supplies the behavior slice. No runtime experiment is accepted.

Actual review RED/GREEN record (2026-11-18):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals -v
Initial RED: Ran 15 tests; FAILED (failures=15), source methods/files absent.
Draft RED: Ran 15 tests; FAILED (failures=5, errors=2), including actual assertions:
  "betrayal must expire at its TTL even without a write"
  "full capacity must evict instead of quarantining"
  "living startup must install the concrete provider"
Additional RED after adding budget regression: Ran 18 tests; FAILED
(failures=1, errors=1), "idle wave must not consume work slots" (plus a
synthetic translator default-null binding error subsequently corrected).
Event-budget RED:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals.Signals.test_betrayal_event_work_is_bounded_without_quarantining_the_store -v
Ran 1 test; FAILED (failures=1): "exhausted event budget must not write another snapshot".
Required GREEN:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals tests.legacy.test_hcx_self_defence tests.legacy.test_v2_xai_living tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.unit.test_hygiene -v
Ran 91 tests; OK. Includes 21 HC-5 tests. Runtime acceptance remains PENDING.
Round 2 uses a separate minute event cap; gesture work never rejects betrayal.
All fixtures below are synthetic; native acceptance remains PENDING.
Spec/plan/tasks: HC-5/#148/#139 observed gestures and finite betrayal memory;
review tasks: expiry/eviction, provider lifecycle/escalation parity, legitimate
self-defence, empty keys and interrupted publication recovery. Runtime PENDING.

Round 2 RED (2026-11-18), before source edits:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals -v
Ran 28 tests; FAILED (failures=19). Actual behavioral RED lines:
  P2-1 AssertionError: 0 != 1 : hostile-faction self-defence must not write betrayal
  P2-2 AssertionError: 0.6 != 0 : live hit/kill defence must survive surrender
  P2-4 AssertionError: 1 != 0 : a warning must not spend betrayal event capacity
  P2-5 AssertionError: False is not true : transient clock failure must not close signals
  P2-6 AssertionError: False is not true : first-boot staging file was never committed
       AssertionError: [] is not true : Open refusal must explain manual recovery: load
  P3   AssertionError: 2 != 1 : a later betrayal refreshes retention
P2-3 exact sequence RED after correcting synthetic release-event filtering:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals.Signals.test_wave_reply_then_weapon_warning_and_second_actor_escalate_within_30s -v
Ran 1 test; FAILED (failures=1).
  AssertionError: 2000 != -1 : reply cooldown must not defer Warn
Round 2 plan/tasks: relation gates at both hit/kill Remember sites; bounded
hit/kill defence wins over surrender; actor warnings use their existing interval;
32 new betrayal events/minute via HCUnitBudget, duplicate Has before budget;
transient clock refusal stays healthy and logs once/open; discard uncommitted
first-boot staging; explain every Open refusal; refresh changed AtUtc only.
Round 2 GREEN:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_hc_ai_signals tests.legacy.test_hcx_self_defence tests.legacy.test_v2_xai_living tests.slow.test_script_syntax tests.unit.test_enforce_locals tests.slow.test_script_identifiers tests.unit.test_hygiene -v
Ran 98 tests in 24.365s; OK (28 HC-5 tests).
rg -l 'HCXBetrayalStore|HCXEmoteObservation|HCXStance|HCStancePolicy' tests/unit
Readers: test_hc_ai_signals.py, test_hcx_self_defence.py, test_v2_xai_living.py.
python3 -B -m tools.validate.enforce_lint --no-native
  enforce_lint: pass findings=133 new=0 stale=0 native=no
Deferred review P2-5 callback feasibility: no fallback implemented. Runtime
PENDING. In DayZDiag RPT, the exact "Stance warning: gesture; lower weapon to
de-escalate; runtime=PENDING" line means the synchronous provider serial/gesture
check returned true. Expect "Stance hostile: raised weapon persisted after 8s
warning" after continuous LOS and raised weapon. "signals=refused:emote_failed"
with no warning means no confirmed warning; provider admission alone proves no
callback. Inspect CreateEmoteCallback: new callback, playing=true, serial
increments, executed ID=HOLD, before Emote returns. Then repeat with two clients
on normal PBO/server. If never confirmed, proposed fallback (not implemented):
start existing per-actor warning.Started at the first eligible observed raised
weapon warning attempt; request HOLD best-effort, log callback unconfirmed,
keep the same 8s continuous observation/lowering resets and NextWarning bound.
No new timer, polling, target discovery or wave success assumption is needed.
"""
import copy
import math
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.legacy.test_expansion_ai_adapter import A, Authored
from tests.legacy.test_group_server import EArray

ROOT = Path(__file__).resolve().parents[2]
HCX = ROOT / "mods/HollowCountryExpansionAI/scripts/4_World"
POLICY = ROOT / "mods/HollowCountry/scripts/4_World/World/HCStancePolicy.c"


class Signals(unittest.TestCase):
    def policy(self):
        text = POLICY.read_text()
        owner = N(WATCH=0, WARN=1)
        authored = Authored(text, {"HCStancePolicy": owner})
        return lambda name, *args: authored.call(name, owner, *args)

    def test_unseen_replayed_and_hostile_waves_never_reply(self):
        call = self.policy()
        # Synthetic server, LOS, neutral, raised, grudge, serial, consumed, now, next.
        valid = [True, True, True, False, False, 7, 6, 1000, 900]
        self.assertTrue(call("ReplyWave", *valid))
        for index, value in ((0, False), (1, False), (2, False), (3, True),
                             (4, True), (5, 0), (6, 7), (8, 1001)):
            trial = list(valid); trial[index] = value
            self.assertFalse(call("ReplyWave", *trial), (index, value))
        self.assertFalse(call("ReplyWave", True, True, True, False, False, 8, 7, -1, 0))

    def test_surrender_stops_only_observed_authoritative_combat(self):
        call = self.policy()
        self.assertTrue(call("CeaseForSurrender", True, True, True))
        for args in ((False, True, True), (True, False, True), (True, True, False)):
            self.assertFalse(call("CeaseForSurrender", *args))
        self.assertFalse(call("WarningDue", 500, 501))
        self.assertTrue(call("WarningDue", 501, 501))
        self.assertFalse(call("WarningDue", -1, 0))

    def store(self, image=None):
        path = HCX / "HCXBetrayalStore.c"
        self.assertTrue(path.exists(), "missing authored durable betrayal store")
        text = path.read_text()
        self.utc = 100
        self.disk = N(image=copy.deepcopy(image), writes=0, blocked=False, fail=False)
        self.logs = []
        def save(data):
            self.disk.writes += 1
            if self.disk.fail: return False
            self.disk.image = copy.deepcopy(data); return True
        io = N(Blocked=lambda:self.disk.blocked, Exists=lambda:self.disk.image is not None,
               Load=lambda:copy.deepcopy(self.disk.image), Save=save, Recover=lambda:not self.disk.blocked)
        env = dict(Print=self.logs.append, A=A, HCGroupClock=N(Utc=lambda:self.utc), HCXAIBetrayalRow=lambda:N(GroupKey="", UID="", AtUtc=0),
                   HCXAIBetrayalData=lambda:N(SchemaVersion=1, LastUtc=0, Rows=A()))
        authored = Authored(text, env)
        owner = N(m_IO=io, m_Data=None, m_Healthy=False, m_Validated=False, m_MaxRows=128, m_TtlSeconds=172800, m_ClockRefused=False)
        for name in ("Open", "Remember", "Has", "Healthy", "Count", "ValidKey", "Prune", "Persist", "Validate", "Configure", "RefuseClock"):
            def invoke(*args, n=name):
                if n in ("Open", "Remember"): self.utc = args[-1]
                return authored.call(n, owner, *args)
            setattr(owner, name, invoke)
        return owner

    def test_saved_grudge_survives_surrender_rejoin_and_restart(self):
        store = self.store()
        self.assertTrue(store.Open(100))
        self.assertTrue(store.Remember("synthetic-site-group", "synthetic-player", 100))
        self.assertEqual(1, self.disk.writes)
        # Surrender is a separate combat decision, never a ledger mutation.
        self.assertTrue(self.policy()("CeaseForSurrender", True, True, True))
        self.assertTrue(store.Has("synthetic-site-group", "synthetic-player"))
        self.assertTrue(store.Remember("synthetic-site-group", "synthetic-player", 101))
        self.assertEqual(2, self.disk.writes, "a later betrayal refreshes retention")
        self.assertEqual(101, self.disk.image.Rows[0].AtUtc)
        self.assertTrue(store.Remember("synthetic-site-group", "synthetic-player", 101))
        self.assertEqual(2, self.disk.writes, "same timestamp must not make a save loop")
        saved = copy.deepcopy(self.disk.image)
        restarted = self.store(saved)
        self.assertTrue(restarted.Open(200))
        self.assertTrue(restarted.Has("synthetic-site-group", "synthetic-player"))
        self.assertFalse(restarted.Has("another-group", "synthetic-player"))
        self.assertFalse(restarted.Has("synthetic-site-group", "another-player"))
        self.assertEqual(0, self.disk.writes)

    def test_expiry_prunes_on_open_and_remember_and_saves_only_changes(self):
        store = self.store(); self.assertTrue(store.Open(100))
        store.m_TtlSeconds = 10
        self.assertTrue(store.Remember("g", "p", 100))
        self.utc = 110
        self.assertFalse(store.Has("g", "p"), "betrayal must expire at its TTL even without a write")
        saved = copy.deepcopy(self.disk.image)
        restarted = self.store(saved); restarted.m_TtlSeconds = 10
        self.assertTrue(restarted.Open(110))
        self.assertEqual(0, restarted.Count(), "Open must prune expired rows")
        self.assertEqual(1, self.disk.writes)
        saved = copy.deepcopy(self.disk.image)
        restarted = self.store(saved); restarted.m_TtlSeconds = 10
        self.assertTrue(restarted.Open(111)); self.assertEqual(0, self.disk.writes)
        self.assertTrue(restarted.Remember("g", "p", 111))
        self.assertTrue(restarted.Remember("g", "q", 121))
        self.assertEqual(1, restarted.Count(), "Remember must prune expired rows")

    def test_capacity_evicts_oldest_and_invalid_keys_do_not_close_signals(self):
        store = self.store(); self.assertTrue(store.Open(100)); store.m_MaxRows = 2
        self.assertTrue(store.Remember("g", "p", 100))
        self.assertTrue(store.Remember("g", "q", 101))
        self.assertTrue(store.Remember("g", "r", 102), "full capacity must evict instead of quarantining")
        self.assertFalse(store.Has("g", "p")); self.assertTrue(store.Has("g", "q"))
        self.assertTrue(store.Healthy()); self.assertEqual(2, store.Count())
        self.assertFalse(store.Remember("", "s", 103)); self.assertTrue(store.Healthy())
        self.assertTrue(store.Remember("g", "r", 103)); self.assertEqual(4, self.disk.writes)
        saved = copy.deepcopy(self.disk.image)
        store = self.store(saved); store.m_MaxRows = 1
        self.assertTrue(store.Open(104)); self.assertEqual(1, store.Count())
        self.assertTrue(store.Has("g", "r")); self.assertEqual(1, self.disk.writes)

    def test_uncertain_store_refuses_without_retry(self):
        store = self.store(); self.assertTrue(store.Open(100)); self.disk.fail = True
        self.assertFalse(store.Remember("g", "p", 100)); self.assertFalse(store.Healthy())
        self.assertFalse(store.Remember("g", "p", 101)); self.assertEqual(1, self.disk.writes)
        store = self.store(); self.disk.blocked = True
        self.assertFalse(store.Open(100))

    def test_bad_ledger_and_clock_rollback_refuse(self):
        for data in (N(SchemaVersion=2, LastUtc=1, Rows=A()),
                     N(SchemaVersion=1, LastUtc=101, Rows=A()),
                     N(SchemaVersion=1, LastUtc=100, Rows=A([N(GroupKey="", UID="p", AtUtc=1)])),
                     N(SchemaVersion=1, LastUtc=100, Rows=A([N(GroupKey="g", UID="p", AtUtc=101)])),
                     N(SchemaVersion=1, LastUtc=100, Rows=A([N(GroupKey="g", UID="p", AtUtc=1)] * 2))):
            store = self.store(data); self.assertFalse(store.Open(100))
        store = self.store(); self.assertTrue(store.Open(100))
        self.assertTrue(store.Remember("g", "p", 100))
        self.assertFalse(store.Remember("g", "q", 99))
        self.assertTrue(store.Healthy(), "clock rollback refuses only this event")

    def test_accepted_hit_is_remembered_before_disconnect_and_rescue_stays_excused(self):
        source = (HCX / "HCXStance.c").read_text()
        self.assertIn("HCHitRecorded", source, "hit memory cannot wait for a later threat evaluation")
        text = source.replace("HCXGrudge grudge", "Object grudge")
        record = N(Kind=4, Until=200)
        actor = N(GetGroup=lambda:"synthetic-group")
        env = dict(s_Running=True, HCXDefence=N(Find=lambda *a:record),
                   HCXDefencePolicy=N(KIND_HIT=1, KIND_KILL=0),
                   GetGame=lambda:N(GetTime=lambda:100))
        authored = Authored(text, env)
        self.assertFalse(authored.call("HCHitRecorded", None, actor, N()))
        record.Kind = 1
        self.assertTrue(authored.call("HCHitRecorded", None, actor, N()))
        record.Kind = 0
        self.assertTrue(authored.call("HCHitRecorded", None, actor, N()))
        record.Until = 100
        self.assertFalse(authored.call("HCHitRecorded", None, actor, N()))
        hit = source.split("override void EEHitBy(", 1)[1].split("override void EEKilled", 1)[0]
        self.assertLess(hit.index("super.EEHitBy"), hit.index("HCHitRecorded"))
        self.assertIn("HCXEmoteObservation.Remember", hit)

    def test_wave_serial_only_changes_when_native_callback_is_created(self):
        path = HCX / "HCXEmoteObservation.c"
        self.assertTrue(path.exists())
        text = path.read_text().split("class HCXSignalProvider", 1)[0]
        text = text.replace("EmoteCB previous", "Object previous")  # declaration syntax only
        state = N(m_HCSignalSerial=0, m_HCGreetingSerial=0, m_bEmoteIsPlaying=False, m_CurrentGestureID=9, m_Callback=None)
        def native_create(*args):
            state.m_Callback = object(); state.m_bEmoteIsPlaying = True
        # Synthetic native callback creation, no engine or provider behavior claim.
        env = {"GetGame":lambda:N(IsServer=lambda:True),
               "EmoteConstants":N(ID_EMOTE_GREETING=9),
               "super":N(CreateEmoteCallback=native_create)}
        authored = Authored(text, env)
        self.assertEqual(0, authored.call("HCSignalGesture", state))
        authored.call("CreateEmoteCallback", state, None, 123, 1, False)
        self.assertEqual(1, state.m_HCSignalSerial)
        self.assertEqual(9, authored.call("HCSignalGesture", state))
        self.assertEqual(1, authored.call("HCSignalSerial", state))
        state.m_bEmoteIsPlaying = False
        self.assertEqual(0, authored.call("HCSignalGesture", state))
        self.assertEqual(1, authored.call("HCSignalSerial", state))

    def observation(self):
        path = HCX / "HCXEmoteObservation.c"
        self.assertTrue(path.exists(), "missing authored observed-emote adapter")
        # Static-to-instance variable binding is syntax adaptation only.
        text = re.sub(r"\bs_(\w+)", r"m_\1", path.read_text().split("class HCXEmoteObservation", 1)[1])
        # Enforce int/int truncates; Python '/' does not. Syntax adaptation only.
        text = text.replace("nowMs / 60000", "Math.Floor(nowMs / 60000)")
        self.now = 1000; self.server = True; self.gesture = 9; self.serial = 1
        self.store_healthy = True
        self.raised = False; self.grudge = False; self.neutral = True
        self.defence_recorded = False
        self.surrendered = False; self.provider_ready = True; self.cease_ok = True; self.emote_ok = True
        self.events = []
        self.player = N(GetEmoteManager=lambda:N(HCSignalSerial=lambda:self.serial,
                        HCSignalGesture=lambda:self.gesture),
                        GetIdentity=lambda:N(GetId=lambda:"synthetic-player"),
                        IsSurrendered=lambda:self.surrendered)
        env = dict(A=A, Math=N(Floor=math.floor), HCGroupClock=N(Utc=lambda:100), GetGame=lambda:N(IsServer=lambda:self.server, GetTime=lambda:self.now),
                   EmoteConstants=N(ID_EMOTE_GREETING=9, ID_EMOTE_HOLD=10),
                   HCXDefence=N(HCHitRecorded=lambda *a:self.defence_recorded),
                   HCXStance=N(Relation=lambda *a:0 if self.neutral else -1,
                               RaisedWeapon=lambda p:self.raised))
        provider = N(Ready=lambda:self.provider_ready,
            CeaseFire=lambda *a:self.events.append("cease") or self.cease_ok,
            Release=lambda *a:self.events.append("release"),
            Emote=lambda a,g:self.events.append(g) or self.emote_ok)
        owner = N(m_Provider=provider, m_Store=N(Healthy=lambda:self.store_healthy), m_Running=True,
                  m_ControlRefused=False, m_StoreRefused=False, m_EventMinute=-1)
        from tests.legacy.test_c3_survivalcfg import config_ports
        env.update(config_ports())  # Explicit synthetic default profile.
        env["Print"] = lambda line:self.events.append(line)
        env["HCXEmoteObservation"] = owner
        self.observer_defence = env["HCXDefence"]
        self.observer_clock = env["HCGroupClock"]
        api = Authored(text, env)
        for name in ("Ready", "ControlReady", "Surrender", "Wave", "Warn", "Remember", "RefuseControl", "EventWork"):
            setattr(owner, name, lambda *a,n=name:api.call(n, owner, *a))
        units = N(m_Limit=0, m_Used=0, m_Items=0)
        unit_api = Authored((ROOT / "mods/HollowCountry/scripts/4_World/Core/HCUnitBudget.c").read_text(), {})
        for name in ("HCReset", "HCTake"):
            setattr(units, name, lambda *a,n=name:unit_api.call(n, units, *a))
        owner.m_Events = units
        owner.Work = lambda:self.server and owner.Ready()  # Explicit synthetic budget slot.
        owner.Grudge = lambda *a:self.grudge
        policy_text = POLICY.read_text(); policy = N()
        p = Authored(policy_text, env)
        for name in ("ReplyWave", "CeaseForSurrender", "WarningDue"):
            setattr(policy, name, lambda *a,n=name:p.call(n, policy, *a))
        env["HCStancePolicy"] = policy
        news = (ROOT / "mods/HollowCountry/scripts/4_World/Actions/HCActionAskForNews.c").read_text()
        cooldown = N(m_Notices=EArray())
        news = re.sub(r"\bHCSignalReceipt(?= \w+ =)", "Object", news)  # declaration syntax only
        cd = Authored(re.sub(r"\bs_(\w+)", r"m_\1", news), env)
        cooldown.Allowed = lambda player:cd.call("Allowed", cooldown, player)
        cooldown.Claim = lambda player:cd.call("Claim", cooldown, player)
        env["HCSignalCooldown"] = cooldown
        env["HCSignalReceipt"] = lambda:N(Recipient="", At=0)
        return owner

    def test_authored_observer_consumes_wave_once_and_separates_warning_cooldown(self):
        observer = self.observation(); actor = N()
        self.assertEqual(0, observer.Wave(actor, self.player, False, 0))
        self.assertEqual([], self.events)
        consumed = observer.Wave(actor, self.player, True, 0)
        self.assertEqual(1, consumed); self.assertEqual([9], self.events)
        self.now += 30000
        self.assertEqual(consumed, observer.Wave(actor, self.player, True, consumed))
        self.assertEqual([9], self.events, "same executed wave cannot replay after cooldown")
        self.serial += 1; self.grudge = True
        consumed = observer.Wave(actor, self.player, True, consumed)
        self.assertEqual(2, consumed); self.assertEqual([9], self.events)
        self.grudge = False; self.serial += 1
        consumed = observer.Wave(actor, self.player, True, consumed)
        self.assertEqual([9, 9], self.events)
        self.assertTrue(observer.Warn(actor, self.player), "warnings are independent of reply cooldown")
        self.now += 30000
        self.assertTrue(observer.Warn(actor, self.player)); self.assertEqual([9, 9, 10, 10], self.events)
        self.assertTrue(observer.Warn(N(), self.player), "another actor must also warn")
        self.emote_ok = False; self.now += 30000
        self.assertFalse(observer.Warn(actor, self.player))
        self.assertTrue(any("emote_failed" in str(event) for event in self.events), "failed provider control must refuse explicitly")

    def test_provider_must_confirm_cease_fire_and_client_or_unseen_signals_refuse(self):
        observer = self.observation(); actor = N(); self.surrendered = True
        self.assertFalse(observer.Surrender(actor, self.player, False))
        self.assertEqual([], self.events)
        self.cease_ok = False
        self.assertFalse(observer.Surrender(actor, self.player, True))
        self.cease_ok = True
        self.assertTrue(observer.Surrender(actor, self.player, True))
        self.assertTrue(self.surrendered)
        self.store_healthy = False
        self.assertTrue(observer.Surrender(actor, self.player, True), "store quarantine cannot defeat cease-fire")
        self.store_healthy = True
        self.surrendered = False
        self.assertFalse(observer.Surrender(actor, self.player, True))
        self.assertEqual("release", self.events[-1])
        self.server = False
        self.assertEqual(0, observer.Wave(actor, self.player, True, 0))
        self.provider_ready = False; self.server = True
        self.surrendered = True
        self.assertFalse(observer.Surrender(actor, self.player, True))

    def test_failed_warning_does_not_consume_cooldown_and_unseen_surrender_is_unread(self):
        observer = self.observation(); actor = N()
        self.emote_ok = False
        self.assertFalse(observer.Warn(actor, self.player))
        self.emote_ok = True
        self.assertTrue(observer.Warn(actor, self.player), "failed emote must leave cooldown available")
        self.player.IsSurrendered = lambda: self.fail("unseen surrender state was read")
        self.assertFalse(observer.Surrender(actor, self.player, False))

    def test_concrete_provider_installed_from_living_module_and_warning_escalates(self):
        stance = (HCX / "HCXStance.c").read_text()
        start = stance.split("override void OnStart", 1)[1].split("override void OnTick", 1)[0]
        # Syntax-only declaration adaptation for the restricted translator.
        start = start.replace("HCXNativeSignalProvider provider", "Object provider")
        events = []
        env = dict(Print=lambda *a:None, HCV2Admission=N(Line=lambda *a:""),
                   HCV2Gates=N(Qualified=lambda *a:False),
                   HCXAIQualification=N(SetEncountersEnabled=lambda *a:None),
                   HCAskForNews=N(Configure=lambda *a:None),
                   HCXEmoteObservation=N(Start=lambda:events.append("start"),
                       Install=lambda p:events.append(p), Ready=lambda:True),
                   HCXNativeSignalProvider=lambda:"concrete-provider",
                   HCXCheckpointProps=lambda:N(Start=lambda:None))
        Authored("void OnStart" + start, env).call("OnStart", N(), N())
        self.assertEqual(["start", "concrete-provider"], events, "living startup must install the concrete provider")
        self.assertIn("warning.Started = nowMs", stance)
        self.assertIn("nowMs - warning.Started < 8000", stance)
        self.assertIn("return 0.6;", stance)
        text = (HCX / "HCXEmoteObservation.c").read_text()
        self.assertIn("class HCXNativeSignalProvider : HCXSignalProvider", text)
        provider = text.split("class HCXNativeSignalProvider", 1)[1].split("class HCXEmoteObservation", 1)[0]
        events.clear()
        serial = [0]
        actor = N(GetEmoteManager=lambda:N(CanPlayEmote=lambda g:True, HCSignalSerial=lambda:serial[0], HCSignalGesture=lambda:10),
                  RaiseWeapon=lambda raised:events.append(("raise",raised)),
                  Expansion_SetEmote=lambda *a:events.append(("set",a)),
                  Expansion_PlayEmote=lambda:(events.append("play"), serial.__setitem__(0, serial[0]+1)))
        self.assertTrue(Authored(provider, {}).call("Emote", N(), actor, 10))
        self.assertIn("play", events)

    def test_kill_memory_excludes_legitimate_self_defence(self):
        stance = (HCX / "HCXStance.c").read_text()
        self.assertIn("HCRememberKill", stance)
        env = dict(HCXDefence=N(HCHitRecorded=lambda *a:False),
                   HCXStance=N(Relation=lambda *a:-1))
        api = Authored(stance, env)
        self.assertFalse(api.call("HCRememberKill", None, N(), N()))
        env["HCXStance"].Relation = lambda *a:0
        self.assertTrue(api.call("HCRememberKill", None, N(), N()))
        env["HCXStance"].Relation = lambda *a:-1
        env["HCXDefence"].HCHitRecorded = lambda *a:True
        self.assertFalse(api.call("HCRememberKill", None, N(), N()), "a recorded hostile-faction hit is still self-defence")

    def stance_fixture(self, observer=None):
        # Explicit synthetic current native target, LOS state and native emote.
        # Adapt only map out-parameter binding for the restricted translator.
        text = (HCX / "HCXStance.c").read_text().split("modded class eAIPlayerTargetInformation", 1)[1]
        text = text.replace("HCXWarning warning;", "Object warning = m_HCWarnings.Get(ai);")
        text = text.replace("m_HCWarnings.Find(ai, warning)", "(warning != null)")
        text = text.replace("HCXWarning surrenderedWarning;", "Object surrenderedWarning = m_HCWarnings.Get(ai);")
        text = text.replace("m_HCWarnings.Find(ai, surrenderedWarning)", "(surrenderedWarning != null)")
        text = text.replace("eAITarget current", "Object current").replace("eAIBase priorActor", "Object priorActor")
        self.now = 1000; self.raised = True; self.emote_ok = False
        player = self.player if observer else N()
        player.GetIdentity = lambda:True if not observer else N(GetId=lambda:"synthetic-player")
        player.IsAlive = lambda:True
        player.IsUnconscious = lambda:False
        player.GetPosition = lambda:0
        warning = N(Started=-1, LastSeen=-1, Hostile=False, LastWaveSerial=0, NextWarning=0)
        actor = N(HCXLivingRefused=False, HCXLastGunfire=-1, GetTarget=lambda:N(GetEntity=lambda:player),
                  GetPosition=lambda:0, GetGroup=lambda:"synthetic-group", RaiseWeapon=lambda *a:None, CanRaiseWeapon=lambda:True)
        state = N(m_LOS=True, m_ThreatLevel=0, m_ThreatLevelActive=0, m_AggressionTimeout=0)
        env = dict(null=None, GetEntity=lambda:player, PlayerBase=N(Cast=lambda p:p),
                   GetGame=lambda:N(IsServer=lambda:True, GetTime=lambda:self.now),
                   HCXStance=N(Owns=lambda a:True, Visible=lambda *a:True,
                               Relation=lambda *a:0, RaisedWeapon=lambda p:self.raised),
                   HCXAIQualification=N(ProviderProblem=lambda:""), HCXDefence=N(Hostile=lambda *a:False),
                   HCXDefencePolicy=N(Threat=lambda base,active:max(base, 0.6) if active else base),
                   super=N(CalculateThreat=lambda *a:0.1),
                   HCXEmoteObservation=N(Surrender=lambda *a:False, Grudge=lambda *a:False,
                       Wave=lambda a,p,o,c:c, Warn=lambda *a:self.emote_ok),
                   vector=N(Distance=lambda *a:10), Print=lambda *a:None)
        policy = N(WATCH=0, WARN=1); env["HCStancePolicy"] = policy
        rules = Authored(POLICY.read_text(), env)
        for name in ("Evaluate", "WarningDue"):
            setattr(policy, name, lambda *a,n=name:rules.call(n, policy, *a))
        if observer: env["HCXEmoteObservation"] = observer
        api = Authored(text, env); owner = N(m_HCWarnings=N(Get=lambda a:warning))
        threat = lambda:api.call("CalculateThreat", owner, actor, state)
        return N(threat=threat, warning=warning, actor=actor, player=player, state=state, env=env)

    def test_warning_progresses_after_success_and_resets_when_observation_is_lost(self):
        fixture = self.stance_fixture()
        threat, warning, state = fixture.threat, fixture.warning, fixture.state
        self.assertEqual(0.15, threat()); self.assertEqual(-1, warning.Started)
        self.emote_ok = True
        self.assertEqual(0.15, threat()); self.assertEqual(1000, warning.Started)
        for self.now in (3000, 5000, 7000): self.assertEqual(0.2, threat())
        self.now = 9000
        self.assertEqual(0.6, threat()); self.assertTrue(warning.Hostile)
        state.m_LOS = False
        self.assertEqual(0, threat()); self.assertEqual(-1, warning.Started)
        state.m_LOS = True; self.raised = False
        self.assertEqual(0.1, threat()); self.assertFalse(warning.Hostile)

    def test_wave_reply_then_weapon_warning_and_second_actor_escalate_within_30s(self):
        observer = self.observation()
        first = self.stance_fixture(observer)
        second = self.stance_fixture(observer)
        self.raised = False; self.emote_ok = True
        self.assertEqual(0.1, first.threat())
        self.assertEqual([9], [e for e in self.events if isinstance(e, int)], "AI replies to the observed wave")
        self.now = 2000; self.raised = True
        self.assertEqual(0.15, first.threat())
        self.assertEqual(2000, first.warning.Started, "reply cooldown must not defer Warn")
        self.assertEqual(0.15, second.threat())
        self.assertEqual(2000, second.warning.Started, "adjacent actor must warn independently")
        self.assertEqual([9, 10, 10], [e for e in self.events if isinstance(e, int)])
        for self.now in (4000, 6000, 8000):
            self.assertEqual(0.2, first.threat()); self.assertEqual(0.2, second.threat())
        self.now = 10000
        self.assertEqual(0.6, first.threat()); self.assertEqual(0.6, second.threat())

    def test_kill_then_observed_surrender_preserves_defence_until_expiry(self):
        observer = self.observation(); fixture = self.stance_fixture(observer)
        record = N(Kind=2, Until=301000)  # Synthetic native kill record, bounded 300s.
        source = (HCX / "HCXStance.c").read_text()
        env = dict(fixture.env, s_Running=True)
        defence = env["HCXDefence"]
        defence.Find = lambda *a:record
        env["HCXDefencePolicy"] = N(KIND_HIT=1, KIND_KILL=2)
        rules = Authored(source.replace("HCXGrudge grudge", "Object grudge"), env)
        defence.HCHitRecorded = lambda *a:rules.call("HCHitRecorded", None, *a)
        defence.Hostile = lambda *a:defence.HCHitRecorded(*a[:2])
        self.observer_defence.HCHitRecorded = defence.HCHitRecorded
        # Simulate a member's native kill callback creating the record via super.
        record.Until = 0
        hooks = source.split("modded class eAIBase", 1)[1].split("modded class eAIPlayerTargetInformation", 1)[0]
        hook_env = dict(fixture.env, HCXAISiteDirector=N(Active=lambda:None),
            EntityAI=N(Cast=lambda a:a), super=N(EEKilled=lambda *a:setattr(record, "Until", 301000)))
        hook_env["HCXDefence"].AttackerOf = lambda *a:fixture.player
        fixture.env["HCXStance"].HCRememberKill = lambda *a:False  # Storage is orthogonal to finite defence.
        Authored(hooks, hook_env).call("EEKilled", fixture.actor, fixture.player)
        self.surrendered = True
        for kind in (1, 2):
            record.Kind = kind
            for self.now in (1000, 300999):
                self.assertEqual(0.6, fixture.threat(), "live hit/kill defence must survive surrender")
                self.assertNotIn("cease", self.events)
        self.now = 301000
        self.assertEqual(0, fixture.threat(), "surrender may cease fire after finite defence expires")
        self.assertIn("cease", self.events)

    def test_recovery_only_removes_guard_after_validating_committed_path(self):
        good = N(SchemaVersion=1, LastUtc=100, Rows=A([N(GroupKey="g", UID="p", AtUtc=100)]))
        store = self.store(good); self.disk.blocked = True
        recovered = []
        store.m_IO.Recover = lambda:recovered.append(True) or True
        self.assertTrue(store.Open(101)); self.assertEqual([True], recovered)
        good.Rows[0].GroupKey = ""
        store = self.store(good); store.m_IO.Recover = lambda:self.fail("invalid committed state must retain pending guard")
        self.assertFalse(store.Open(101))
        text = (HCX / "HCXBetrayalStore.c").read_text()
        io = text.split("class HCXBetrayalIO", 1)[1].split("class HCXBetrayalStore", 1)[0]
        files = {"pending", "path"}; deleted = []
        env = dict(FileExist=lambda p:p in files,
                   DeleteFile=lambda p:deleted.append(p) or files.remove(p) or True)
        api = Authored(io, dict(env, PATH="path", PENDING="pending"))
        io_owner = N()
        io_owner.Blocked = lambda:api.call("Blocked", io_owner)
        self.assertTrue(api.call("Recover", io_owner))
        self.assertEqual(["pending"], deleted); self.assertIn("path", files)

    def test_idle_wave_checks_cannot_spend_the_warning_work_budget(self):
        observer = self.observation(); self.gesture = 0
        observer.Work = lambda:self.fail("idle wave must not consume work slots")
        self.assertEqual(0, observer.Wave(N(), self.player, True, 0))

    def test_native_surrender_latch_blocks_queued_fire_and_later_raise_without_polling(self):
        text = (HCX / "HCXEmoteObservation.c").read_text().split("modded class eAIBase", 1)[1].split("modded class EmoteManager", 1)[0]
        text = text.replace("eAITarget target", "Object target")
        self.now = 1000; events = []; player = N(uid="synthetic-surrendered"); other = N(uid="synthetic-other")
        current = [player]
        actor = N(m_HCXCeaseTarget=None, m_HCXCeaseUntil=0,
                  GetTarget=lambda:N(GetEntity=lambda:current[0]))
        env = dict(null=None, GetTarget=actor.GetTarget,
                   HCXSignalBlocked=lambda *a:actor.HCXSignalBlocked(*a),
                   RaiseWeapon=lambda *a:actor.RaiseWeapon(*a),
                   GetGame=lambda:N(IsServer=lambda:True, GetTime=lambda:self.now),
                   super=N(RaiseWeapon=lambda up:events.append(up), CanRaiseWeapon=lambda:True,
                           eAI_CanFire=lambda w:True))
        api = Authored(text, env)
        for name in ("HCXSignalBlocked", "HCXSignalCease", "HCXSignalRelease", "RaiseWeapon", "CanRaiseWeapon", "eAI_CanFire"):
            setattr(actor, name, lambda *a,n=name:api.call(n, actor, *a))
        self.assertTrue(actor.HCXSignalCease(player)); self.assertEqual([False], events)
        self.assertFalse(actor.CanRaiseWeapon()); actor.RaiseWeapon(True)
        self.assertFalse(events[-1]); self.assertFalse(actor.eAI_CanFire(N()))
        current[0] = other
        self.assertTrue(actor.CanRaiseWeapon(), "surrender must not disable defence against a different target")
        current[0] = player; actor.HCXSignalRelease(player)
        self.assertTrue(actor.CanRaiseWeapon())
        actor.HCXSignalCease(player); self.now += 2000
        self.assertFalse(actor.HCXSignalBlocked(), "unrefreshed observations must expire")

    def test_config_defaults_and_bounds_are_in_the_adapter_policy(self):
        text = (HCX / "HCXEmoteObservation.c").read_text()
        self.assertIn("modded class HCXAISitePolicy", text)
        self.assertIn("BetrayalRetentionSeconds = 172800", text)
        self.assertIn("HCXAISiteDirector.LoadPolicy()", text)
        store = self.store()
        self.assertTrue(store.Configure(16, 3600))
        self.assertEqual((16, 3600), (store.m_MaxRows, store.m_TtlSeconds))
        for rows, ttl in ((0, 3600), (129, 3600), (8, 0), (8, 2592001)):
            self.assertFalse(store.Configure(rows, ttl))
        self.assertEqual((16, 3600), (store.m_MaxRows, store.m_TtlSeconds))

    def test_policy_written_before_hc5_uses_defaults_instead_of_refusing(self):
        # Boot 044: a profile expansion-ai-sites.json without the three HC-5
        # keys loaded them as 0 and quarantined the betrayal store
        # ("HC-5 betrayal config refused"). Absent (0) means default; one
        # line per defaulted key; an out-of-range non-zero value still refuses.
        path = HCX / "HCXEmoteObservation.c"
        text = re.sub(r"\bs_(\w+)", r"m_\1", path.read_text().split("class HCXEmoteObservation", 1)[1])
        events = []
        configured = []
        owner = N(m_MaxWork=0, m_Store=N(Configure=lambda rows, ttl: configured.append((rows, ttl)) or True))
        api = Authored(text, dict(A=A, Print=events.append, HCXEmoteObservation=owner))
        owner.PolicyInt = lambda *a: api.call("PolicyInt", owner, *a)
        old = N(MaxSignalWorkPerSecond=0, MaxBetrayalRows=0, BetrayalRetentionSeconds=0)
        self.assertTrue(api.call("ApplyPolicy", owner, old))
        self.assertEqual(configured, [(128, 172800)])
        self.assertEqual(owner.m_MaxWork, 8)
        self.assertEqual(len([e for e in events if "absent; default" in e]), 3)
        events.clear(); configured.clear()
        tuned = N(MaxSignalWorkPerSecond=4, MaxBetrayalRows=16, BetrayalRetentionSeconds=3600)
        self.assertTrue(api.call("ApplyPolicy", owner, tuned))
        self.assertEqual((configured, owner.m_MaxWork, events), ([(16, 3600)], 4, []))
        configured.clear()
        self.assertFalse(api.call("ApplyPolicy", owner, N(MaxSignalWorkPerSecond=33, MaxBetrayalRows=16,
                                                          BetrayalRetentionSeconds=3600)))
        self.assertEqual(configured, [])
        self.assertFalse(api.call("ApplyPolicy", owner, None))

    def event_fixture(self):
        observer = self.observation()
        store = self.store(); self.assertTrue(store.Open(100))
        observer.m_Store = store
        actor = N(GetGroup=lambda:N(GetName=lambda:"synthetic-group"))
        self.player.GetGroup = lambda:None
        return observer, store, actor

    def test_warn_then_kill_same_second_records_even_when_gesture_work_is_spent(self):
        observer, store, actor = self.event_fixture()
        work = [True]
        observer.Work = lambda:work.pop() if work else False
        self.assertTrue(observer.Warn(actor, self.player))
        observer.Remember(actor, self.player)
        self.assertEqual(1, store.Count(), "a warning must not spend betrayal event capacity")
        self.assertEqual(1, self.disk.writes)
        # An existing row must not consume a minute slot or touch disk.
        observer.EventWork = lambda:self.fail("duplicate EEHitBy must do no event work")
        observer.Remember(actor, self.player)
        self.assertEqual(1, self.disk.writes)

    def test_betrayal_minute_cap_is_independent_bounded_and_resets(self):
        observer, store, actor = self.event_fixture()
        observer.Work = lambda:self.fail("betrayal must never use gesture work")
        uid = ["p0"]
        self.player.GetIdentity = lambda:N(GetId=lambda:uid[0])
        for index in range(32):
            uid[0] = "p" + str(index)
            observer.Remember(actor, self.player)
        self.assertEqual(32, self.disk.writes)
        uid[0] = "over-cap"
        self.now = 59999
        observer.Remember(actor, self.player)
        self.assertEqual(32, self.disk.writes)
        self.assertTrue(store.Healthy())
        self.assertTrue(any("betrayal_event_cap" in str(e) for e in self.events))
        self.now = 60000
        observer.Remember(actor, self.player)
        self.assertEqual(33, self.disk.writes)

    def test_transient_clock_failure_refuses_only_event_and_keeps_ready(self):
        observer, store, actor = self.event_fixture()
        self.assertTrue(observer.Ready())
        self.observer_clock.Utc = lambda:-1
        for _ in range(3):
            observer.Remember(actor, self.player)
            self.assertEqual(0, store.Count(), "bad clock must refuse this event")
            self.assertTrue(observer.Ready(), "transient clock failure must not close signals")
        self.assertEqual(1, len(self.logs), "clock refusal log must be bounded")
        self.assertIn("clock", self.logs[0].lower())
        self.assertFalse(any("quarantined" in str(event) for event in self.events))
        self.observer_clock.Utc = lambda:101
        observer.Remember(actor, self.player)
        self.assertTrue(observer.Ready())
        self.assertEqual(1, self.disk.writes)

    def test_first_boot_discards_uncommitted_pending_and_opens(self):
        source = (HCX / "HCXBetrayalStore.c").read_text()
        io_text = source.split("class HCXBetrayalIO", 1)[1].split("class HCXBetrayalStore", 1)[0]
        files = {"pending"}; deleted = []
        env = dict(PATH="path", PENDING="pending", FileExist=lambda p:p in files,
                   DeleteFile=lambda p:deleted.append(p) or files.remove(p) or True)
        api = Authored(io_text, env)
        store = self.store()
        for name in ("Exists", "Blocked", "Recover"):
            setattr(store.m_IO, name, lambda n=name:api.call(n, store.m_IO))
        self.assertTrue(store.Open(100), "first-boot staging file was never committed")
        self.assertEqual(["pending"], deleted)
        self.assertTrue(store.Healthy()); self.assertEqual(0, self.disk.writes)

    def test_every_open_refusal_names_a_manual_step(self):
        good = N(SchemaVersion=1, LastUtc=100, Rows=A([N(GroupKey="g", UID="p", AtUtc=100)]))
        for case in ("clock", "io", "backup", "load", "validate", "recover", "persist"):
            with self.subTest(case=case):
                store = self.store(good if case in ("load", "validate", "recover", "persist") else None)
                now = 101
                if case == "clock": now = -1
                if case == "io": store.m_IO = None
                if case == "backup": self.disk.blocked = True
                if case == "load": store.m_IO.Load = lambda:None
                if case == "validate": self.disk.image.SchemaVersion = 9
                if case == "recover": store.m_IO.Recover = lambda:False
                if case == "persist": store.m_TtlSeconds = 1; self.disk.fail = True
                self.assertFalse(store.Open(now))
                self.assertTrue(self.logs, "Open refusal must explain manual recovery: " + case)
                self.assertTrue(any(word in self.logs[-1].lower() for word in ("check", "restore", "restart")), self.logs)

    def test_hit_and_kill_hooks_only_write_for_non_hostile_relations(self):
        source = (HCX / "HCXStance.c").read_text()
        hooks = source.split("modded class eAIBase", 1)[1].split("modded class eAIPlayerTargetInformation", 1)[0]
        for hook in ("EEHitBy", "EEKilled"):
            for relation in (-1, 0, 1):
                with self.subTest(hook=hook, relation=relation):
                    store = self.store(); self.assertTrue(store.Open(100))
                    actor, player = N(), N()
                    stance = N(Owns=lambda a:True, Relation=lambda *a:relation)
                    env = dict(GetGame=lambda:N(IsServer=lambda:True),
                        GetGroup=lambda:N(GetFaction=lambda:"Locals"), HCXFactions=N(Id=lambda faction:faction),
                        HCXStance=stance, HCXDefence=N(AttackerOf=lambda a:player, HCHitRecorded=lambda *a:True),
                        HCXEmoteObservation=N(Remember=lambda *a:store.Remember("g", "p", 100)),
                        HCXAISiteDirector=N(Active=lambda:None), EntityAI=N(Cast=lambda a:a),
                        super=N(EEHitBy=lambda *a:None, EEKilled=lambda *a:None))
                    rule = Authored(source, env)
                    stance.HCRememberKill = lambda *a:rule.call("HCRememberKill", None, *a)
                    api = Authored(hooks, env)
                    args = (None, 0, player, 0, "", "", 0, 0) if hook == "EEHitBy" else (player,)
                    api.call(hook, actor, *args)
                    self.assertEqual(int(relation >= 0), store.Count(), "hostile-faction self-defence must not write betrayal")

    def test_native_identity_and_provider_refusal_wiring(self):
        path = HCX / "HCXEmoteObservation.c"
        self.assertTrue(path.exists(), "missing authored observed-emote adapter")
        text = path.read_text()
        self.assertIn("m_CurrentGestureID", text)
        self.assertIn("m_bEmoteIsPlaying", text)
        self.assertNotIn(".GetGesture()", text, "input slot is not executed emote identity")
        self.assertNotIn(".IsEmotePlaying()", text, "pending generic emote is not greeting evidence")
        self.assertIn("HCUnitBudget", text); self.assertIn("HCWorkBudget", text)
        self.assertIn("HCV2Admission.Line", text)
        self.assertIn("[HC Plan] HC-5 signals=", text)
        self.assertIn("runtime=PENDING", text)
        self.assertRegex(text, r"bool Ready\(\)\s*\{ return false; \}")
        stance = (HCX / "HCXStance.c").read_text()
        self.assertIn("HCXEmoteObservation.Surrender", stance)
        self.assertIn("HCXEmoteObservation.Wave", stance)
        self.assertIn("HCXEmoteObservation.Remember", stance)
        self.assertIn("HCXDefence.Hostile(", stance)
        self.assertNotIn("HCAskForNews.Notify", stance)
        self.assertNotIn("ai.Expansion_SetEmote(", stance, "provider control goes through inspected port")
        news = (ROOT / "mods/HollowCountry/scripts/4_World/Actions/HCActionAskForNews.c").read_text()
        self.assertNotIn("SendNotificationToPlayerExtended", news)
        self.assertNotIn("actions.Insert(HCActionAskForNews)", news)
        store = (HCX / "HCXBetrayalStore.c").read_text()
        for seam in ("HCGroupIO.WriteNew", "HCGroupIO.Read", "CopyFile", "DeleteFile", ".bak", "PENDING"):
            self.assertIn(seam, store)


if __name__ == "__main__":
    unittest.main()
