"""#160 HC-S001/HC-S002 burn-down: infected + weather/scenes/lighting refusals say why.

Authored method bodies run through the small EnScript-to-Python adapter in
tests/unit/test_map_layers.py (syntax only). Natives, clocks, stores and the
engine out parameters are explicit synthetic stand-ins; this is never DayZ
evidence. Each test drives one retired refusal and asserts its stable reason.
RED: PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest tests.unit.test_hc_burn_infected -v
2026-11-19 on base cf10c1d: FAILED (failures=13), e.g. "AssertionError: Tuples differ:
('refused', 'MISSION_UNAVAILABLE') != ('refused', 'WEATHER_OWNER_NOT_ADMITTED')".
GREEN: same command, Ran 13 tests, OK. Runtime acceptance pending; nothing observed in DayZ.
"""
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_hc_scavenge import bind

SCRIPTS = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts'


class NativeMap(dict):
    def Contains(self, key): return key in self
    def Get(self, key): return self[key]
    def Set(self, key, value): self[key] = value


def brace_ifs(source):
    """Syntax only: wrap brace-less single-statement ifs so the adapter can split tokens."""
    out, pos = [], 0
    for match in re.finditer(r'\bif \(', source):
        if match.start() < pos:
            continue
        depth, index = 0, match.end() - 1
        while True:
            depth += (source[index] == '(') - (source[index] == ')')
            index += 1
            if depth == 0:
                break
        start = index
        while source[start] in ' \t\n':
            start += 1
        if source[start] == '{':
            continue
        end = source.index(';', start) + 1
        out.append(source[pos:index] + ' { ' + source[start:end] + ' }')
        pos = end
    out.append(source[pos:])
    return ''.join(out)


def authored(path, owner, names, target, env, prep=()):
    """Bind the shipped bodies; prep lists (regex, replacement) syntax adaptations."""
    source = re.sub(r'(?m)(?<=\s)//[^\n]*|^//[^\n]*', '', (SCRIPTS / path).read_text())
    source = re.sub(r'\bnew (\w+)\(', r'\1(', brace_ifs(source))
    source = re.sub(r'(\w+)<\w+>\.', r'\1.', source)
    source = re.sub(r'new array<[^;]*?>;', 'new EArray();', source)
    source = re.sub(r'(?:ref )?array<[^;=]*?> (\w+) = ', r'\1 = ', source)
    for pattern, replacement in prep:
        source = re.sub(pattern, replacement, source)
    env.setdefault('EArray', EArray)
    bind(source, owner, target, names, env)
    return target


def game(**members):
    base = dict(IsServer=lambda: True, IsDedicatedServer=lambda: True, GetTickTime=lambda: 100.0)
    base.update(members)
    return lambda: N(**base)


class NativePackRefusals(unittest.TestCase):
    """HCNativeInfectedPack.Start (11 baselined silent returns) records a stable reason."""

    def fixture(self):
        self.printed = []
        member = N(InfectedEntity=N(IsAlive=lambda: True, GetPosition=lambda: [0, 0, 0],
                                    GetAIAgent=lambda: N(), GetMindStateSynced=lambda: 1),
                   Profile='native_normal', SearchAnchorLimit=0)
        self.actors = EArray([member])
        self.group = N(GetBehaviour=lambda: N())
        self.world = N(SampleNavmeshPosition=lambda *a: True, CreateGroup=lambda name: self.group)
        self.state = dict(server=True, config=True, release=EArray(), reach=True, activate=True)
        pack = N(Group=None, RouteResult=0, RouteEnd=None, m_Filter=None, m_RefusalReason='x',
                 InitFilter=lambda: None, Release=lambda: False,
                 Reachable=lambda *a: self.state['reach'],
                 ActivateWaypoint=lambda now: self.state['activate'],
                 GetAIWorld=lambda: self.world)
        env = dict(Print=lambda text: self.printed.append(str(text)),
                   s_PendingRelease=self.state['release'], s_RefusalSeen=NativeMap(),
                   GetGame=lambda: N(IsServer=lambda: self.state['server'],
                                      ConfigIsExisting=lambda name: self.state['config']),
                   DayZInfectedConstants=N(MINDSTATE_CHASE=4, MINDSTATE_FIGHT=5),
                   Math=N(Min=min), HCInfectedRoomCatalog=N(BuildOrder=lambda *a: None),
                   BehaviourGroupInfectedPack=N(Cast=lambda behaviour: behaviour),
                   BehaviourGroupInfectedPackWaypointParams=lambda *a: N(m_CenterPosition=[1, 0, 1]))
        authored('4_World/Infected/HCInfectedNavigation.c', 'HCNativeInfectedPack', ('Start', 'HCRefuse'), pack, env)
        return pack

    def start(self, pack, actors=None, expires=130.0):
        roster = self.actors if actors is None else actors
        return pack.Start(roster, [10, 0, 10], False, 100.0, expires)

    def assert_refused(self, pack, reason, **start):
        self.assertFalse(self.start(pack, **start))
        self.assertEqual(reason, getattr(pack, 'm_RefusalReason', None))

    def test_every_refusal_reports_its_reason_and_state_is_unchanged(self):
        pack = self.fixture()
        self.state['release'].append('pending')
        self.assert_refused(pack, 'release_pending')
        self.state['release'].clear()
        self.state['server'] = False
        self.assert_refused(pack, 'not_server')
        self.state['server'] = True
        self.assert_refused(pack, 'roster_bounds', actors=EArray())
        self.assert_refused(pack, 'clue_expired', expires=90.0)
        self.state['config'] = False
        self.assert_refused(pack, 'pack_template_missing')
        self.state['config'] = True
        dead = N(InfectedEntity=N(IsAlive=lambda: False), Profile='native_normal', SearchAnchorLimit=0)
        self.assert_refused(pack, 'leader_unavailable', actors=EArray([dead]))
        self.state['reach'] = False
        self.assert_refused(pack, 'route_unreachable')
        self.state['reach'] = True
        chasing = N(InfectedEntity=N(IsAlive=lambda: True, GetPosition=lambda: [0, 0, 0],
                                     GetAIAgent=lambda: N(), GetMindStateSynced=lambda: 4),
                    Profile='native_normal', SearchAnchorLimit=0)
        self.assert_refused(pack, 'member_engaged', actors=EArray([chasing]))
        self.group = None
        self.assert_refused(pack, 'group_create_failed')
        self.assertIsNone(pack.Group, 'a refused Start must not keep a native group')
        self.group = N(GetBehaviour=lambda: None)
        self.assert_refused(pack, 'group_behaviour_missing')
        self.assertIsNone(pack.Group)
        self.group = N(GetBehaviour=lambda: N())
        self.state['activate'] = False
        self.assert_refused(pack, 'waypoint_failed')
        self.assertEqual(6, pack.RouteResult, 'existing RouteResult value is unchanged')

    def test_no_ai_world_is_its_own_reason(self):
        pack = self.fixture()
        pack.GetAIWorld = lambda: None
        self.assert_refused(pack, 'no_ai_world')

    def test_refusal_log_is_bounded_per_reason(self):
        pack = self.fixture()
        self.state['release'].append('pending')
        for _ in range(1100):
            self.assertFalse(self.start(pack))
        lines = [line for line in self.printed if 'release_pending' in line]
        self.assertEqual(3, len(lines), 'first occurrence plus every 512th, never every call')
        self.assertTrue(all('refused reason=release_pending' in line for line in lines))


class DoorsRefusal(unittest.TestCase):
    def test_building_rules_refusal_keeps_a_reason_the_summary_prints(self):
        printed = []
        building = N(CanDoorBeOpened=lambda request: False, PlayDoorSound=lambda index: None)
        module = N(m_Refused=0, m_Opened=0, m_Broken=0, m_Hits=0, m_LastRefusal='', Noise=lambda *a: None)
        env = dict(Print=lambda text: printed.append(str(text)),
                   DoorManipulationParams=lambda: N(),
                   HCInfectedDoorPolicy=N(ACTION_HIT=1, ACTION_BREAK=2, ACTION_OPEN=3, KIND_HEAVY=9))
        authored('4_World/Infected/Doors/HCInfectedDoors.c', 'HCInfectedDoorsModule', ('Apply',), module, env)
        entry = N(m_Building=building, m_Index=4)
        module.Apply(entry, 3, N(), [0, 0, 0])
        self.assertEqual(1, module.m_Refused)
        self.assertEqual('building_rules_refused', getattr(module, 'm_LastRefusal', None))
        source = (SCRIPTS / '4_World/Infected/Doors/HCInfectedDoors.c').read_text()
        self.assertIn('last_refusal=" + m_LastRefusal', source, 'the 10-minute summary reports the reason')


class MemoryRefusal(unittest.TestCase):
    def test_second_start_while_active_says_so(self):
        printed = []
        memory = N(m_State=None, m_Healthy=False, m_Dirty=False)
        env = dict(Print=lambda text: printed.append(str(text)), GetGame=game(), s_Instance=N(),
                   HCGroupClock=N(SampleUtc=lambda: 1000))
        authored('4_World/Infected/HCInfectedMemory.c', 'HCInfectedMemory', ('Start',), memory, env,
                 prep=((r'\bs_Instance = this;', ''),))
        self.assertFalse(memory.Start())
        self.assertEqual(1, len(printed))
        self.assertIn('already_active', printed[0])


class LodRefusal(unittest.TestCase):
    def test_lod_operator_preference_off_logs_its_reason(self):
        printed = []
        config = N(EnableLOD=False, EnableVirtualHerds=True)
        lod = N(m_Running=False, m_Config=None, IsEnabled=lambda settings: True)
        env = dict(Print=lambda text: printed.append(str(text)), GetGame=game(),
                   HCInfectedLODConfig=N(Load=lambda reason: config),
                   HCV2Admission=N(Line=lambda *a: 'admission', Admitted=lambda preference: preference),
                   HCV2Gates=N(Qualified=lambda gate: False))
        authored('4_World/Infected/LOD/HCInfectedLOD.c', 'HCInfectedLODModule', ('OnStart',), lod, env)
        lod.OnStart(N(EnableDebugSnapshot=False))
        self.assertIsNone(lod.m_Config)
        self.assertTrue(any('operator_preference_off' in line for line in printed), printed)


class ScenesRefusal(unittest.TestCase):
    def module(self, utc, opened):
        printed = []
        scenes = N(m_Running=False, m_AdmissionPrinted=False, m_SummaryPrinted=False, m_Leases=EArray(),
                   m_Store=None, m_State=None, IsEnabled=lambda settings: True)
        env = dict(Print=lambda text: printed.append(str(text)), GetGame=game(), s_CleanupOwner=None,
                   HCV2Admission=N(Line=lambda *a: 'admission'), HCV2Gates=N(Qualified=lambda gate: False),
                   HCSceneChainStore=lambda: N(Open=lambda now: opened),
                   HCGroupClock=N(Utc=lambda: utc))
        authored('4_World/Scenes/HCScenesModule.c', 'HCScenesModule', ('OnStart', 'Now'), scenes, env,
                 prep=((r'GetGame\(\)\.GetWorldName\(world\);\s*world\.ToLower\(\);', 'world = "chernarusplus";'),
                       (r'(?<![\w.])m_Leases\b', 'self.m_Leases')))
        scenes.OnStart(N())
        return scenes, printed

    def test_unusable_utc_clock_logs_why_scenes_did_not_start(self):
        scenes, printed = self.module(utc=0, opened=None)
        self.assertFalse(scenes.m_Running)
        self.assertTrue(any('utc_clock_unavailable' in line for line in printed), printed)

    def test_store_that_cannot_open_logs_a_scenes_reason(self):
        scenes, printed = self.module(utc=1577836800 + 500, opened=None)
        self.assertFalse(scenes.m_Running)
        self.assertTrue(any('store_unavailable' in line for line in printed), printed)


class WeatherDaysRefusal(unittest.TestCase):
    def run_start(self, supported, delegated, mission):
        printed, published = [], []
        module = N(m_Data=None, m_Status=N(HCPublish=lambda state, reason: published.append((state, reason))))
        env = dict(Print=lambda text: printed.append(str(text)), GetGame=game(GetMission=lambda: mission),
                   HCV2Admission=N(Line=lambda *a: 'admission'), HCV2Gates=N(Qualified=lambda gate: False),
                   HCAtmosphereQualification=N(SupportedWorld=lambda: supported, DelegatedWeather=lambda: delegated,
                                               Qualified=lambda: True, LocalOptIn=lambda: True))
        authored('4_World/Weather/HCWeatherDaysModule.c', 'HCWeatherDaysModule', ('OnStart',), module, env)
        module.OnStart(N(EnableAtmosphere=True))
        return published, printed

    def test_unsupported_world_publishes_refused_reason(self):
        published, printed = self.run_start(False, True, None)
        self.assertEqual(('refused', 'WORLD_OR_BUILD_UNSUPPORTED'), published[-1])
        self.assertTrue(any('WORLD_OR_BUILD_UNSUPPORTED' in line for line in printed), printed)

    def test_xml_weather_controller_publishes_refused_reason(self):
        published, printed = self.run_start(True, False, None)
        self.assertEqual(('refused', 'XML_WEATHER_CONTROLLER_OWNS'), published[-1])

    def test_missing_mission_publishes_refused_reason(self):
        published, printed = self.run_start(True, True, None)
        self.assertEqual(('refused', 'MISSION_UNAVAILABLE'), published[-1])


class AtmosphereLifecycleRefusal(unittest.TestCase):
    def test_missing_mission_logs_why_atmosphere_did_not_start(self):
        printed = []
        server = N()
        env = dict(Print=lambda text: printed.append(str(text)),
                   GetGame=game(GetMission=lambda: None),
                   HCAtmosphereQualification=N(Enabled=lambda: True),
                   ChernarusPlusData=N(Cast=lambda mission: None))
        authored('4_World/Weather/HCAtmosphereLifecycle.c', 'HCServer', ('Start',), server, env,
                 prep=((r'super\.Start\(\);', ''),
                       (r'GetGame\(\)\.GetWorldName\(atmosphereWorld\);\s*atmosphereWorld\.ToLower\(\);',
                        'atmosphereWorld = "chernarusplus";')))
        server.Start()
        self.assertTrue(any('mission_unavailable' in line for line in printed), printed)


class LightingClientRefusal(unittest.TestCase):
    def test_missing_world_lighting_logs_and_does_not_start(self):
        printed = []
        client = N(m_HCRunning=False, m_HCLighting=None)
        env = dict(Print=lambda text: printed.append(str(text)), GetGame=game(),
                   CALL_CATEGORY_SYSTEM=1)
        authored('5_Mission/Atmosphere/HCLightingClient.c', 'HCLightingClient', ('Start',), client, env)
        client.Start()
        self.assertFalse(client.m_HCRunning)
        self.assertTrue(any('world_lighting_unavailable' in line for line in printed), printed)


class ModuleRouteRefusalLogs(unittest.TestCase):
    """HCInfectedModule surfaces HCNativeInfectedPack.HCRefusalReason() in its own log lines."""
    MODULE = SCRIPTS / '4_World/Infected/HCInfectedModule.c'

    def module(self):
        self.printed = []
        module = N(m_LastRouteRefusal='')
        env = dict(Print=lambda text: self.printed.append(str(text)))
        authored('4_World/Infected/HCInfectedModule.c', 'HCInfectedModule', ('HCNoteRouteRefusal',), module, env)
        return module

    def test_investigate_refusal_reason_is_logged_once_per_change(self):
        module = self.module()
        module.HCNoteRouteRefusal('investigate', 'no_ai_world')
        module.HCNoteRouteRefusal('investigate', 'no_ai_world')
        self.assertEqual(1, len(self.printed), self.printed)
        self.assertIn('reason=no_ai_world', self.printed[0])
        self.assertIn('runtime=PENDING', self.printed[0])
        module.HCNoteRouteRefusal('investigate', 'release_pending')
        self.assertEqual(2, len(self.printed))

    def test_success_or_empty_reason_resets_so_a_repeat_is_logged_again(self):
        module = self.module()
        module.HCNoteRouteRefusal('investigate', 'no_ai_world')
        module.HCNoteRouteRefusal('investigate', '')
        self.assertEqual(1, len(self.printed))
        module.HCNoteRouteRefusal('investigate', 'no_ai_world')
        self.assertEqual(2, len(self.printed))

    def test_call_sites_read_the_pack_reason(self):
        source = self.MODULE.read_text()
        self.assertGreaterEqual(source.count('pack.HCRefusalReason()'), 2, 'investigate and cohort-quarantine lines')
        self.assertIn('HCNoteRouteRefusal("investigate", ', source)
        self.assertIn('reason=adoption_transfer_failed_or_ambiguous pack_reason="', source)


if __name__ == '__main__':
    unittest.main()
