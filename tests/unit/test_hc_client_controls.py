"""HC-27 / effective presentation controls: one synthetic Given/When/Then scenario.

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
Lead owns spec/plan/tasks trace, settings distribution and mission wiring. No
new distances. HCUnitBudget/HCWorkBudget bound four lanes; native scans and
synchronous existing hint saves cannot be preempted or claimed measured here.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest
import re

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_refusal_report import MethodsTranslator

ROOT = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'
COORD = ROOT / '5_Mission/Operations/HCClientPresentation.c'
SETTINGS = ROOT / '3_Game/HCClientPresentationSettings.c'
SOUND = ROOT / '5_Mission/Atmosphere/HCEnvSound.c'
HINTS = ROOT / '5_Mission/Polish/HCHints.c'


def install(path, env, owner, methods):
    source = path.read_text().replace('float milliseconds = 4', 'float milliseconds')
    source = re.sub(r'([\w.]+)\.Length\(\)', r'len(\1)', source)
    source = source.replace('Remove(HCReceiveHoldouts)', 'Remove(this.HCReceiveHoldouts)')
    # Native out-parameter binding only; acceptance decisions stay authored.
    source = source.replace('GetGame().GetProfileString(PROFILE_KEY, saved)',
        '((profile_value := profile_read(PROFILE_KEY))[0] && ((saved := profile_value[1]) != null))')
    source = re.sub(r'ctx.Read\((version|revision|mask)\)',
        r'((wire_value := ctx.ReadValue())[0] && ((\1 := wire_value[1]) != null))', source)
    for code in MethodsTranslator(source, owner, methods).classes():
        exec(compile(code, str(path) + '(synthetic ports)', 'exec'), env)
    return env[owner]


class ClientControls(unittest.TestCase):
    def test_effective_off_cleans_scheduled_work_refuses_unknown_and_resumes_only_allowed(self):
        logs, destroyed, saves, updates, profile = [], [], [], [], {}
        alive = [True]
        subscriptions = []
        viewer = N(IsAlive=lambda: alive[0], IsUnconscious=lambda: False)
        game = N(GetTickTime=lambda: 100., GetPlayer=lambda: viewer,
                 IsServer=lambda: False, SetProfileString=profile.__setitem__,
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
        self.assertEqual([], updates)
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
