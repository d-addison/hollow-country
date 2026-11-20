"""HC-27 / effective presentation controls: synthetic Given/When/Then checks.

Executes authored Enforce lifecycle/settings bodies through existing restricted
ports; DTO/native handles, profile IO, notifications and RPC context are explicit
synthetic fixtures. No engine, audio, lighting or network acceptance evidence.
Trace: HC-27 brief -> versioned mask/local veto -> off cleanup/no idle work.
Required spec paths are absent in this checkout; lead retains central trace.
Actual RED/GREEN (2026-11-18):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_client_controls -v
RED: AssertionError: <object ...> is not None : off state retains scheduled sound/hint work
RED (same scenario extended): presentation off discarded the server snapshot needed by local re-enable
GREEN: Ran 1 test; OK (authored lifecycle only). Runtime=PENDING.
Native follow-up: exact-source DayZDiag then signed PBO/server, two clients with
opposite masks; join/off/on/death/reconnect/stop-restart, radio/cellar separation,
no stuck handles/errors; capture exact source/PBO/mission/config/dependency hashes.
Grep [HC Plan] HC-27 presentation=off handles=0 off_callbacks=0 and runtime=PENDING;
observe unknown_setting/unknown_or_conflicting_settings/hint_cancel_unsupported.
Round 1 left settings distribution and mission wiring to the lead. No
new distances. HCUnitBudget/HCWorkBudget bound the deferred lanes; native scans and
synchronous existing hint saves cannot be preempted or claimed measured here.

Round 2 trace (2026-11-18): active HC-27 integration/review brief supersedes
the round-1 lead handoff. Spec input: .banso-writer/inputs/task-r2.md, shared
brief, RUNTIME_IMPLEMENTATION_CONTRACT.md; central spec/plan/tasks paths absent.
Plan/tasks: optional mask admission -> static cached sender -> mission lifecycle
-> effective GRADE lighting owner -> native-safe counts/offline/grade/hint fixes.
Given explicit settings, identities, frame clocks and presentation handles,
When join/ready/reconnect, flags change, the core owner restarts, grade is vetoed,
the lane budget expires or eleven hints have been shown,
Then serialize VERSION/revision/mask to the intended identity, cap broadcasts
at 90, keep revisions monotonic, stop/recreate lighting, sample grade every live
frame and continue hints until the derived fourteen-hint mask is complete.
The final revision 2e9 is reserved for a permanent off snapshot, never a wrap.

Actual RED/GREEN, same exact command:
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_client_controls test_runtime_settings -v
RED: Ran 20 tests; FAILED (failures=25), including 16 mask subtests:
  Unknown field ClientPresentationMask; shipped default 15 != None;
  missing presentation mission lifecycle / missing presentation server sender;
  GRADE off still created lighting at mission init;
  offline DayZDiag was mistaken for a dedicated server;
  foreach matched member m_Lit; grade ['grade'] != [] at exhausted budget;
  11 shown hints incorrectly suppress the remaining 3.
GREEN: Ran 20 tests; OK. Syntax/locals/identifiers/formula/hygiene: 56 tests OK;
enforce_lint --no-native: pass findings=126 new=0 stale=0.
Additional boundary RED: same command restricted to
test_hc_client_controls.ClientControls.test_server_gates_each_bit_and_serializes_targeted_version_revision_mask
failed 1 != 2: lazy first send must restart the five-second poll interval.
GREEN with the full 20-test command after resetting elapsed on the lazy read.
Reuse: HCPerfPlayers snapshot + HCUnitBudget/HCWorkBudget + operational status
and HCV2Admission. No core/config.cpp edits or distances needed.
Remaining tasks: central trace reconciliation by lead; exact-source DayZDiag,
normal PBO/server and two clients; target-load timing and native notification
expiry. Production/runtime acceptance PENDING, never inferred from these ports.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re
import itertools

from tests.legacy.test_event_runtime import translate
from tests.legacy.test_group_server import EArray
from tests.legacy.test_refusal_report import MethodsTranslator

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'
COORD = ROOT / '5_Mission/Operations/HCClientPresentation.c'
SETTINGS = ROOT / '3_Game/HCClientPresentationSettings.c'
SOUND = ROOT / '5_Mission/Atmosphere/HCEnvSound.c'
HINTS = ROOT / '5_Mission/Polish/HCHints.c'
MISSION = ROOT / '5_Mission/Operations/HCClientPresentationMission.c'
SERVER = ROOT / '4_World/Operations/HCClientPresentationServer.c'
LIGHTING = ROOT / '5_Mission/Atmosphere/HCLightingClient.c'


def install(path, env, owner, methods):
    # HC-51 moved lighting/cache ownership into this coordinator. These are
    # explicit synthetic presentation/native handles; the season test executes
    # the real cache validation and lighting handler separately.
    if owner == 'HCClientPresentation':
        methods = tuple(methods) + ('HCStartSeasonPresentation', 'HCReceiveSeason')
        class SyntheticSeason:
            @staticmethod
            def HCReset(): pass
            def HCStart(self): pass
            def HCStop(self): pass
            def HCRejectSnapshot(self): pass
        env.setdefault('HCSeasonVisualClient', SyntheticSeason)
        env.setdefault('make_lighting', lambda handle: N(Start=lambda: None, Stop=lambda: None))
        env.setdefault('synthetic_mission', lambda: N(GetWorldLighting=lambda: 'synthetic lighting'))
    env.setdefault('HCSeasonSnapshotRPC', N(RPC_SEASON=4853913))
    source = path.read_text().replace('float milliseconds = 4', 'float milliseconds')
    # Explicit constructor seam for the synthetic native WorldLighting handle.
    source = source.replace('new HCLightingClient(', 'make_lighting(')
    if owner == 'HCClientPresentation':
        source = source.replace('GetGame().GetMission()', 'synthetic_mission()')
    # Inherited native method, absent from this modded link's member list.
    source = source.replace('!IsControlDisabled()', '!this.IsControlDisabled()')
    source = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', source)
    source = source.replace('Remove(HCReceiveHoldouts)', 'Remove(this.HCReceiveHoldouts)')
    # Native out-parameter binding only; acceptance decisions stay authored.
    source = source.replace('GetGame().GetProfileString(PROFILE_KEY, saved)',
        '((profile_value := profile_read(PROFILE_KEY))[0] && ((saved := profile_value[1]) != null))')
    source = re.sub(r'ctx.Read\((version|revision|mask|phaseCode)\)',
        r'((wire_value := ctx.ReadValue())[0] && ((\1 := wire_value[1]) != null))', source)
    for code in MethodsTranslator(source, owner, methods).classes():
        exec(compile(code, str(path) + '(synthetic ports)', 'exec'), env)
    return env[owner]


class ClientControls(unittest.TestCase):
    def server(self):
        self.assertTrue(SERVER.is_file(), 'missing presentation server sender')
        packets, reads, logs = [], [], []
        settings = N(ClientPresentationMask=15, EnableGrade=True,
                     EnableSignsOfLife=True, EnableAmbientLife=True)
        owner = [N(GetSettings=lambda: reads.append('settings') or settings)]
        players = EArray(N(GetIdentity=lambda i=i: 'synthetic-' + str(i)) for i in range(95))
        class RPC:
            def __init__(self): self.values = []
            def Write(self, value): self.values.append(value)
            def Send(self, *args): packets.append((tuple(self.values), args))
        env = dict(EArray=EArray, ScriptRPC=RPC, Print=logs.append, tostr=str,
                   GetGame=lambda: N(IsServer=lambda: True),
                   HCServer=N(Get=lambda: owner[0]),
                   HCPerfPlayers=N(HCGet=lambda: players),
                   PlayerBase=N(Cast=lambda player: player), Math=N(Min=min))
        install(SETTINGS, env, 'HCClientPresentationSettings', ('HCValidMask',))
        sender = install(SERVER, env, 'HCClientPresentationServer',
                         ('HCComputeMask', 'HCRefresh', 'SendTo', 'HCTick', 'HCBroadcast'))
        return sender, settings, owner, reads, packets, logs

    def test_server_gates_each_bit_and_serializes_targeted_version_revision_mask(self):
        sender, settings, owner, reads, packets, logs = self.server()
        for mask, grade, signs, ambient in itertools.product(range(16), (False, True), (False, True), (False, True)):
            settings.ClientPresentationMask = mask
            settings.EnableGrade, settings.EnableSignsOfLife, settings.EnableAmbientLife = grade, signs, ambient
            expected = mask & (1 | (2 if grade else 0) | (4 if signs else 0) | (8 if ambient else 0))
            self.assertEqual(expected, sender.HCComputeMask(settings))
        self.assertEqual(0, sender.HCComputeMask(None))
        settings.ClientPresentationMask = 16
        self.assertEqual(0, sender.HCComputeMask(settings))
        settings.ClientPresentationMask = 15
        sender.HCTick(4)  # First join can occur after several mission frames.
        sender.SendTo(None)
        self.assertEqual([], packets)
        sender.SendTo('synthetic identity')
        sender.SendTo('other identity')
        self.assertEqual(1, len(reads), 'join resend must reuse the cached snapshot')
        self.assertEqual(((1, 1, 15), (None, 4854001, True, 'synthetic identity')), packets[0])
        sender.HCTick(1)
        self.assertEqual(1, len(reads), 'lazy first send must restart the five-second poll interval')

    def test_server_polls_at_five_seconds_broadcasts_90_and_never_resets_revision_with_core(self):
        sender, settings, owner, reads, packets, logs = self.server()
        sender.SendTo('synthetic identity')
        packets.clear()
        settings.EnableGrade = False
        for _ in range(49): sender.HCTick(.1)
        self.assertEqual(1, len(reads))
        self.assertEqual([], packets)
        sender.HCTick(.11)
        self.assertEqual(90, len(packets))
        self.assertTrue(all(p[0] == (1, 2, 13) for p in packets))
        self.assertEqual(['synthetic-' + str(i) for i in range(90)], [p[1][-1] for p in packets])
        packets.clear()
        # Explicit HCServer Stop/Start boundary: replace its settings owner,
        # retaining the sender class exactly as a script VM does.
        owner[0] = N(GetSettings=lambda: None)
        sender.HCTick(5)
        owner[0] = N(GetSettings=lambda: settings)
        sender.HCTick(5)
        self.assertEqual([(1, 3, 0), (1, 4, 13)], [packets[i][0] for i in (0, 90)])
        packets.clear()
        sender.HCTick(5)
        self.assertEqual([], packets, 'unchanged settings must not broadcast')
        sender.s_Revision = 1999999999
        settings.EnableGrade = True
        sender.HCTick(5)
        self.assertEqual((1, 2000000000, 0), packets[-1][0])
        settings.EnableGrade = False
        sender.HCTick(5)
        self.assertEqual(2000000000, sender.s_Revision)
        self.assertTrue(any('revision_exhausted' in line for line in logs))

    def test_mission_starts_only_clients_and_resends_after_each_server_connection_hook(self):
        self.assertTrue(MISSION.is_file(), 'missing presentation mission lifecycle')
        calls, dedicated, blocked, menu = [], [False], [False], [None]
        class Base:
            def OnInit(self): calls.append('super init')
            def OnUpdate(self, dt): calls.append(('super update', dt))
            def OnMissionFinish(self): calls.append('super finish')
            def IsControlDisabled(self): return blocked[0]
            def OnClientNewEvent(self, identity, pos, ctx): calls.append('super new'); return 'player'
            def OnClientReadyEvent(self, identity, player): calls.append('super ready')
            def OnClientReconnectEvent(self, identity, player): calls.append('super reconnect')
        def coordinator():
            return N(HCStart=lambda: calls.append('start'), HCStop=lambda: calls.append('stop'),
                     HCUpdate=lambda *args: calls.append(('update', *args)))
        env = dict(_Base_MissionGameplay=Base, _Base_MissionServer=Base,
                   HCClientPresentation=coordinator,
                   HCClientPresentationServer=N(SendTo=lambda identity: calls.append(('send', identity)),
                                                HCTick=lambda dt: calls.append(('tick', dt))),
                   HCSeasonSnapshotRPC=N(SendTo=lambda identity: calls.append(('season send', identity)),
                                         HCTick=lambda dt: calls.append(('season tick', dt))),
                   GetGame=lambda: N(IsDedicatedServer=lambda: dedicated[0],
                       GetUIManager=lambda: N(GetMenu=lambda: menu[0])))
        gameplay = install(MISSION, env, 'MissionGameplay', ('OnInit', 'OnUpdate', 'OnMissionFinish'))()
        dedicated[0] = True
        gameplay.OnInit()
        self.assertIsNone(gameplay.m_HCClientPresentation)
        dedicated[0] = False
        gameplay.OnInit()
        self.assertEqual(['super init', 'super init', 'start'], calls)
        for value, in_menu, allowed in ((False, None, True), (True, None, False), (False, object(), False)):
            blocked[0], menu[0] = value, in_menu
            gameplay.OnUpdate(.1)
            self.assertEqual([('super update', .1), ('update', .1, allowed)], calls[-2:])
        gameplay.OnMissionFinish()
        self.assertEqual(['stop', 'super finish'], calls[-2:])
        self.assertIsNone(gameplay.m_HCClientPresentation)
        server = install(MISSION, env, 'MissionServer',
                         ('OnUpdate', 'OnClientNewEvent', 'OnClientReadyEvent', 'OnClientReconnectEvent'))()
        self.assertEqual('player', server.OnClientNewEvent('identity', None, None))
        server.OnClientReadyEvent('identity', 'player')
        server.OnClientReconnectEvent('identity', 'player')
        self.assertEqual(['super new', ('send', 'identity'), ('season send', 'identity'),
                          'super ready', ('send', 'identity'), ('season send', 'identity'),
                          'super reconnect', ('send', 'identity'), ('season send', 'identity')], calls[-9:])
        server.OnUpdate(.2)
        self.assertEqual([('super update', .2), ('tick', .2), ('season tick', .2)], calls[-3:])

    def test_lighting_is_allocated_only_for_effective_grade_and_recreated_after_off(self):
        calls, mask, dedicated = [], [0], [False]
        def lighting(handle):
            self.assertEqual('synthetic lighting', handle)
            return N(Start=lambda: calls.append('start'), Stop=lambda: calls.append('stop'))
        env = dict(make_lighting=lighting, Print=lambda line: None, tostr=str,
                   HCOperationalStatus=lambda: N(HCPublish=lambda *a: None),
                   HCUnitBudget=lambda: N(), HCWorkBudget=lambda: N(),
                   HCGradeSettingsClient=lambda: N(Start=lambda: None, Stop=lambda: None, HCHandleCount=lambda: 0),
                   GetGame=lambda: N(IsDedicatedServer=lambda: dedicated[0]))
        install(SETTINGS, env, 'HCClientPresentationSettings', ('HCValidMask',))
        c = install(COORD, env, 'HCClientPresentation',
                    ('HCReconcile', 'HCReport', 'HCHandleCount'))()
        c.m_Settings = N(HCEffective=lambda local: mask[0])
        c.m_Stopped = False
        c.HCReconcile()
        self.assertIsNone(c.m_Lighting)
        self.assertIsNone(c.m_Seasons)
        mask[0] = 2
        dedicated[0] = True
        c.HCReconcile()
        self.assertIsNone(c.m_Lighting, 'dedicated server created client lighting')
        self.assertIsNone(c.m_Seasons, 'dedicated server created client season cache')
        dedicated[0] = False
        c.HCReconcile()
        first, first_cache = c.m_Lighting, c.m_Seasons
        self.assertIsNotNone(first)
        self.assertIsNotNone(first_cache)
        c.HCReconcile()
        self.assertEqual(['start'], calls)
        mask[0] = 0
        c.HCReconcile()
        self.assertIsNone(c.m_Lighting)
        self.assertIsNone(c.m_Seasons)
        mask[0] = 2
        c.HCReconcile()
        self.assertIsNot(first, c.m_Lighting)
        self.assertIsNot(first_cache, c.m_Seasons)
        c.m_Stopped = True
        c.HCReconcile()
        self.assertEqual(['start', 'stop', 'start', 'stop'], calls)

    def test_offline_diag_applies_full_mask_but_dedicated_never_starts(self):
        dedicated, multiplayer = [True], [False]
        starts, stops, callbacks = [], [], []
        def producer():
            return N(Start=lambda: starts.append('start'), Stop=lambda: stops.append('stop'), HCHandleCount=lambda: 0)
        game = N(IsServer=lambda: True, IsDedicatedServer=lambda: dedicated[0],
                 IsMultiplayer=lambda: multiplayer[0], GetProfileString=lambda key, saved: False)
        env = dict(GetGame=lambda: game, Print=lambda line: None, tostr=str,
                   HCOperationalStatus=lambda: N(HCPublish=lambda *args: None),
                   HCUnitBudget=lambda: N(), HCWorkBudget=lambda: N(),
                   HCSignsOfLifeSnapshotClient=producer, HCHints=producer, HCEnvSound=producer,
                   HCGradeSettingsClient=producer, HCSignsOfLifeClient=producer,
                   HCV2Admission=N(Line=lambda *args: 'runtime=PENDING'), profile_read=lambda key: (False, ''),
                   DayZGame=N(Event_OnRPC=N(Insert=callbacks.append, Remove=callbacks.remove)))
        install(SETTINGS, env, 'HCClientPresentationSettings', ('HCValidMask', 'HCAccept', 'HCEffective'))
        c = install(COORD, env, 'HCClientPresentation',
                    ('HCStart', 'HCApplyServer', 'HCReconcile', 'HCReport', 'HCHandleCount', 'HCRefuse', 'HCReceive'))()
        c.HCStart()
        self.assertTrue(c.m_Stopped)
        dedicated[0] = False
        c.HCStart()
        self.assertFalse(c.m_Stopped, 'offline DayZDiag was mistaken for a dedicated server')
        self.assertEqual(15, c.m_EffectiveMask)
        self.assertEqual(1, len(callbacks))

    def test_owned_effect_counts_use_named_local_arrays_for_native_foreach(self):
        source = (ROOT / '5_Mission/Atmosphere/HCSignsOfLifeClient.c').read_text()
        method = source.split('int HCHandleCount()')[-1].split('void Clear()')[0]
        for member in ('m_Lit', 'm_Smoke', 'm_Flies'):
            self.assertNotRegex(method, r'foreach\s*\([^)]*:\s*' + member + r'\s*\)')
            self.assertRegex(method, r'array<ref HCSignsOfLifeEffect>\s+\w+\s*=\s*' + member)

    def test_hints_keep_running_after_old_eleven_hint_mask_until_all_fourteen_are_shown(self):
        checks, saves = [], []
        player = N(IsAlive=lambda: True, IsUnconscious=lambda: False)
        env = dict(GetGame=lambda: N(GetPlayer=lambda: player, GetUIManager=lambda: N(GetMenu=lambda: None)),
                   GetDayZGame=lambda: N(GetDatabaseID=lambda: 'synthetic-character'),
                   PlayerBase=N(Cast=lambda value: value), NotificationSystem=N(GetInstance=lambda: object()),
                   Check=checks.append, Save=lambda: saves.append('save') or True)
        hints = install(HINTS, env, 'HCHints', ('Update', 'HCAllShownMask'))()
        hints.m_State = N(CharacterId='synthetic-character', ShownBits=2047, PlayedSeconds=30, NextHintSecond=30)
        hints.Update(5)
        self.assertEqual([player], checks, '11 shown hints incorrectly suppress the remaining 3')
        count = len(set(re.findall(r'Offer\((\d+),', HINTS.read_text())))
        self.assertEqual(14, count)
        self.assertEqual((1 << count) - 1, hints.HCAllShownMask())
        hints.m_State.ShownBits = hints.HCAllShownMask()
        hints.Update(60)
        self.assertEqual([], saves)
        self.assertEqual([player], checks)

    def test_effective_off_cleans_scheduled_work_refuses_unknown_and_resumes_only_allowed(self):
        logs, destroyed, saves, updates, profile = [], [], [], [], {}
        alive = [True]
        subscriptions = []
        viewer = N(IsAlive=lambda: alive[0], IsUnconscious=lambda: False)
        game = N(GetTickTime=lambda: 100., GetPlayer=lambda: viewer,
                 IsServer=lambda: False, IsDedicatedServer=lambda: False,
                 IsMultiplayer=lambda: True, SetProfileString=profile.__setitem__,
                 SaveProfile=lambda: saves.append('profile'))
        env = dict(GetGame=lambda: game, Print=logs.append, tostr=str,
                   PlayerBase=N(Cast=lambda p: p),
                   SEffectManager=N(DestroyEffect=destroyed.append),
                   DayZGame=N(Event_OnRPC=N(Insert=subscriptions.append,
                       Remove=lambda fn: subscriptions.remove(fn) if fn in subscriptions else None)),
                   profile_read=lambda key: (key in profile, profile.get(key, '')),
                   HCV2Admission=N(Line=lambda *args: 'synthetic admission runtime=PENDING'),
                   EArray=EArray, HCSignsOfLife=N(ForceLit=None), HCGradeParameters=lambda: N())
        sound = N(m_Sound=object(), m_Stopped=False, m_Check=0., m_StopAt=200.,
                  m_Wind=True, m_Logged=False)
        sound.StopSound = lambda: translate(SOUND.read_text(), 'StopSound', env, 'HCEnvSound', True)(sound)
        sound.LogLayer = lambda layer: None
        sound.Stop = lambda: translate(SOUND.read_text(), 'Stop', env, 'HCEnvSound', True)(sound)
        sound.HCHandleCount = lambda: int(sound.m_Sound is not None)
        if not COORD.exists():
            # Pre-change behavior: an operator off decision has no consumer;
            # the existing scheduled sound remains alive between samples.
            baseline = install(SOUND, env, 'HCEnvSound', ('Update',))()
            baseline.__dict__.update(sound.__dict__)
            baseline.Update(.1)
            self.assertIsNone(baseline.m_Sound, 'off state retains scheduled sound/hint work')
            return
        settings_type = install(SETTINGS, env, 'HCClientPresentationSettings',
                                ('HCValidMask', 'HCBit', 'HCEffective', 'HCAccept', 'HCInvalidate'))
        for owner, relative in (('HCUnitBudget', '4_World/Core/HCUnitBudget.c'),
                                ('HCWorkBudget', '4_World/World/HCWorkBudget.c'),
                                ('HCOperationalStatus', '3_Game/HCOperationalStatus.c')):
            install(ROOT / relative, env, owner,
                    ('HCReset', 'HCTake', 'HCContinue', 'HCMayContinue', 'HCPublish', 'HCState', 'HCReason'))
        hints = N(m_Stopped=False, m_State=N(NextHintSecond=30), m_Fault=False,
                  m_Shown=1, Save=lambda: saves.append('hint') or True)
        hints.Stop = lambda: translate(HINTS.read_text(), 'Stop', env, 'HCHints', True)(hints)
        hints.Update = lambda dt: updates.append('hints')
        sound.Update = lambda dt: updates.append('sound')
        grade_path = ROOT / '5_Mission/Atmosphere/HCGradeSettingsClient.c'
        grade = install(grade_path, env, 'HCGradeSettingsClient', ('Stop', 'HCHandleCount', 'Report'))()
        running = [True]
        grade.m_Requester = N(IsRequesterRunning=lambda: running[0],
                              Stop=lambda: running.__setitem__(0, False))
        grade.Start = lambda: None
        grade.Update = lambda dt, allow: updates.append('grade')
        signs_path = ROOT / '5_Mission/Atmosphere/HCSignsOfLifeClient.c'
        effect = install(signs_path, env, 'HCSignsOfLifeEffect', ('Stop', 'HCHandleCount'))()
        effect.Lamp = N(Destroy=lambda: destroyed.append('lamp'))
        effect.Smoke = N(Stop=lambda: destroyed.append('smoke'))
        effect.Flies, effect.Buzz = object(), object()
        signs = install(signs_path, env, 'HCSignsOfLifeClient',
                        ('Stop', 'Clear', 'ClearHandles', 'HCHandleCount', 'Report'))()
        signs.HCReceiveHoldouts = lambda *args: None
        signs.m_Lit.Insert(effect)  # Explicit synthetic slot exercising all four native handles.
        signs.HCTickEffects = lambda dt: updates.append('signs')
        env['HCSignsOfLife'].SCAN_SECONDS = 10
        env.update(HCSignsOfLifeSnapshotClient=lambda: N(Stop=lambda: None),
                   HCHints=lambda: hints, HCEnvSound=lambda: sound,
                   HCGradeSettingsClient=lambda: grade, HCSignsOfLifeClient=lambda: signs)
        controller_type = install(COORD, env, 'HCClientPresentation',
            ('HCStart', 'HCApplyServer', 'HCSetPreference', 'HCReconcile', 'HCUpdate', 'HCStop',
             'HCHandleCount', 'HCReport', 'HCRefuse', 'HCGetOperationalStatus', 'HCReceive'))
        c = controller_type()
        # Explicit live synthetic state from before an operator changes settings.
        c.m_Stopped = False
        c.m_Hints, c.m_Sound, c.m_Grade, c.m_Signs = hints, sound, grade, signs
        c.m_Settings.HCAccept(1, 1, settings_type.ALL)
        c.m_EffectiveMask = settings_type.ALL
        snapshot = EArray([[1., 0., 1.]])  # Explicit synthetic server snapshot, no world evidence.
        env['HCSignsOfLife'].ForceLit = snapshot
        self.assertEqual(6, c.HCHandleCount())
        c.HCApplyServer(1, 2, 0)
        self.assertIsNone(sound.m_Sound, 'off state retains scheduled sound/hint work')
        self.assertTrue(hints.m_Stopped)
        self.assertFalse(running[0])
        self.assertIs(snapshot, env['HCSignsOfLife'].ForceLit,
                      'presentation off discarded the server snapshot needed by local re-enable')
        self.assertEqual(0, effect.HCHandleCount())
        self.assertEqual(5, len(destroyed))
        self.assertEqual(['hint'], saves)
        self.assertEqual(0, c.HCHandleCount())
        game.GetPlayer = lambda: self.fail('off state queried player/scanned world')
        for _ in range(20):
            c.HCUpdate(.1, True)
        self.assertEqual([], updates)
        self.assertEqual(['hint'], saves, 'disabled hints must not save on idle callbacks')
        self.assertTrue(any('presentation=off handles=0 off_callbacks=0' in row for row in logs))
        self.assertTrue(any('hint_cancel_unsupported' in row for row in logs))
        self.assertFalse(c.HCSetPreference('inventory', True))
        self.assertTrue(any('unknown_setting' in row for row in logs))
        self.assertTrue(c.HCSetPreference('ambient', False))
        c.HCApplyServer(1, 3, settings_type.ALL)
        self.assertIsNone(c.m_Sound, 'server enable must respect client veto')
        game.GetPlayer = lambda: viewer
        c.HCUpdate(.1, True)
        self.assertEqual({'grade', 'hints', 'signs'}, set(updates))
        self.assertEqual('ready', c.HCGetOperationalStatus().HCState())
        # Yield on the real clock guard, then resume the retained slot next frame.
        updates.clear()
        clock = iter([100., 100.005])
        game.GetTickTime = lambda: next(clock)
        c.HCUpdate(.2, True)
        self.assertEqual(['grade'], updates, 'grade LocalPress sampling must survive an exhausted lane budget')
        self.assertEqual(0, c.m_Next)
        self.assertAlmostEqual(.2, c.m_HintElapsed)
        game.GetTickTime = lambda: 100.
        c.HCUpdate(.1, True)
        self.assertEqual({'grade', 'hints', 'signs'}, set(updates))
        self.assertEqual(0, c.m_HintElapsed)
        # Unknown wire bits/schema close all lanes; stale packets cannot revive.
        c.HCApplyServer(1, 4, 16)
        self.assertEqual(0, c.m_EffectiveMask)
        c.HCApplyServer(1, 4, 16)
        self.assertEqual('refused', c.HCGetOperationalStatus().HCState())
        c.HCApplyServer(1, 3, settings_type.ALL)
        self.assertEqual(0, c.m_EffectiveMask)
        c.HCApplyServer(9, 5, settings_type.ALL)
        self.assertEqual(0, c.m_EffectiveMask)
        c.HCApplyServer(1, 6, settings_type.GRADE)
        self.assertEqual(settings_type.GRADE, c.m_EffectiveMask)
        # Foreign sender/target and unrelated RPCs never mutate effective state.
        for sender, target, rpc in ((object(), None, settings_type.RPC_SETTINGS),
                                    (None, object(), settings_type.RPC_SETTINGS),
                                    (None, None, 123)):
            c.HCReceive(sender, target, rpc, None)
            self.assertEqual(settings_type.GRADE, c.m_EffectiveMask)
        c.HCReceive(None, None, settings_type.RPC_SETTINGS, None)
        self.assertEqual(0, c.m_EffectiveMask)
        c.HCApplyServer(1, 5, settings_type.ALL)
        self.assertEqual(0, c.m_EffectiveMask, 'malformed packet retains revision barrier')
        packet = iter([1, 7, settings_type.GRADE])
        c.HCReceive(None, None, settings_type.RPC_SETTINGS,
                    N(ReadValue=lambda: (True, next(packet))))
        self.assertEqual(settings_type.GRADE, c.m_EffectiveMask)
        alive[0] = False
        updates.clear()
        c.HCUpdate(.1, True)
        self.assertEqual([], updates, 'death cannot run presentation producers')
        c.HCStop()
        c.HCStop()
        self.assertEqual(0, c.HCHandleCount())
        c.HCApplyServer(1, 8, settings_type.ALL)
        self.assertEqual(0, c.m_EffectiveMask, 'late RPC cannot revive a finished mission')
        self.assertNotIn('inventory', profile)
        # Reconnect reloads the local veto, never the prior server snapshot.
        c.HCStart()
        c.HCStart()
        self.assertEqual(1, len(subscriptions))
        self.assertEqual(0, c.m_EffectiveMask)
        self.assertEqual(settings_type.ALL - settings_type.AMBIENT, c.m_LocalMask)
        c.HCApplyServer(1, 1, settings_type.ALL)
        self.assertIsNone(c.m_Sound)
        c.HCStop()
        self.assertEqual([], subscriptions)
        profile[controller_type.PROFILE_KEY] = 'unknown'
        c.HCStart()
        c.HCApplyServer(1, 1, settings_type.ALL)
        self.assertEqual(0, c.m_EffectiveMask, 'corrupt local preference must fail closed')
        self.assertTrue(any('invalid_local_mask' in row for row in logs))
        c.HCStop()


if __name__ == '__main__':
    unittest.main()
