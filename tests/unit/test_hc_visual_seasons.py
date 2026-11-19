"""HC-6: authored Enforce clock/store bodies, explicit synthetic ports only.

No DayZ clock, filesystem durability, weather or client evidence. The existing
restricted translator changes syntax; every clock decision runs authored code.

Actual TDD receipts (2026-11-18):
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_visual_seasons -v
  RED: Ran 3 tests; FAILED (failures=10), "missing authored HCVisualSeasons.c:
       restart/downtime clock unavailable" (four boundaries and refusal cases).
  Follow-up RED: Ran 4 tests; FAILED (errors=1), AttributeError:
       'NoneType' object has no attribute 'ElapsedSeconds' after a refused open.
  GREEN: same command, Ran 4 tests, OK.

HC-51 TDD receipts (2026-11-18), same focused command throughout:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_visual_seasons -v
  RED: Ran 6 tests; FAILED (failures=1):
       AssertionError: False is not true : HC-51 seasonal forecast policy missing
  Extended handler RED: Ran 6 tests; FAILED (failures=1):
       AssertionError: 0.0 != 0.12 : HC-51 grade remains active after death
  Extended receipt RED: Ran 6 tests; FAILED (failures=1):
       'state=refused reason=WEATHER_OWNER_NOT_ADMITTED count=0' not found
       (foreign owner was incorrectly attributed to HC-6 off).
  GREEN: Ran 6 tests; OK. Synthetic callback references use syntax-only binding.
  Regression GREEN: 118 tests, OK, using the focused modules below:
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_visual_seasons test_v2_weather_days test_v2_lighting test_hc_client_controls test_admin_test_kit test_script_syntax test_enforce_locals test_script_identifiers test_enforce_formula_complexity test_hygiene -v

Prior HC-51 plan/tasks (superseded by Wave 6 below): phase scalar forecasts, closed-table grades, single-slot fade,
bounded version/revision/phase cache and death/off cleanup authored here. Lead
must integrate forecasts/observed diagnostics in the sole weather writer and
carry the three-int snapshot in existing mission control transport (30-second
heartbeat, 90-second expiry). Neither transport nor weather activation is claimed
implemented by this worker. HC-6 clock/store and HC-50 refusal remain unchanged.
docs/SPECIFICATION.md, docs/specs/001-survival-overhaul/spec.md and central Banso
spec/plan/tasks are absent in this checkout; the HC-51 brief is the design input,
and the lead retains central trace reconciliation. New mission/ files: none.
Wave 6 HC-51 trace: active worker brief -> sole weather authority/active HC-6
phase -> phase-change limits/observed receipts -> monotonic three-int RPC on
new/ready/reconnect/change/30.0s heartbeat -> HC-27 GRADE cache + lighting owner
-> range/sender/target rejection, off/mission cleanup, named fog boundary fade.
Framework: HCModule tick/status, HC-6 clock, HCUnitBudget/HCWorkBudget, existing
DayZGame.Event_OnRPC receiver and HC-27 effective mask. No new registry owner,
client requests, gameplay controller, distances or mission/ files. The new
4_World/Weather/HCSeasonSnapshotRPC.c uses checked-unused RPC id 4853913.
Native: scripts-1.30.164289/3_Game/Weather.c:321 inspected exact signature
SetSnowfallThresholds(float tMin, float tMax, float tTime), defaults :309-311;
3_Game/gameplay.c:104-117 ScriptRPC.Send, :747 Mission.GetWorldLighting;
3_Game/DayZGame.c:991,3144 Event_OnRPC; 2_GameLib/tools.c:120,122 Insert/Remove.
Snow keeps stock wetness effects; white terrain remains HC-50's refused track.
Named refusals: WEATHER_OWNER_NOT_ADMITTED, HC6_NOT_ADMITTED, snapshot_bounds,
snapshot_version_revision, snapshot_conflict, malformed_season_rpc and revision_exhausted.
Wave 6 actual TDD, same focused command:
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_visual_seasons -v
  RED: Ran 6 tests; FAILED (failures=1): HC-51 boundary blend missing.
  Extended RED: Ran 6 tests; FAILED (failures=1):
    0.5599999999999999 not less than 0.001: HC-51 dawn fog-day baseline still pops.
  GREEN: Ran 6 tests; OK. The same authored test covers authority/HC-6 gating,
    RPC uniqueness/revision/heartbeat, real registered receiver and cache,
    bounds/refusal deduplication, lighting precedence and off/stop cleanup.
Wave 6 regression command (182 tests, OK; one pre-existing expected failure):
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.:tests/unit python3 -m unittest test_hc_visual_seasons test_v2_weather_days test_v2_lighting test_hc_client_controls test_admin_test_kit test_admin_ui test_runtime_settings test_v1_combined_flags test_script_syntax test_enforce_locals test_script_identifiers test_enforce_formula_complexity test_hygiene -v
  PYTHONDONTWRITEBYTECODE=1 python3 -m tools.validate.enforce_lint --no-native
  pass findings=121 new=0 stale=0 native=no.
Additional small test update: test_hc_client_controls.py's synthetic lifecycle
ports now consume HC-51 join/tick calls and coordinator-owned cache/lighting.
Lead: no HCModule.c/config.cpp edits, registration unchanged; reconcile the
central Banso trace (required central spec/plan/tasks still absent).
Distances added: none. DayZDiag, signed PBO/server, two clients, restart/downtime,
native weather/survival controls and exact package hashes all remain PENDING.
"""
import functools
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import body
from tests.unit.test_hc_unit_budget import unit_budget

ROOT = Path(__file__).resolve().parents[2]
WEATHER = ROOT / 'mods/HollowCountry/scripts/4_World/Weather'
CLOCK = WEATHER / 'HCVisualSeasons.c'
STORE = WEATHER / 'HCVisualSeasonStore.c'
CONFIG = ROOT / 'config/hollow-country-seasons.json'


def bind(path, kind, instance, env):
    """Restrict translation to one class; rename unfamiliar Enforce types only."""
    text = path.read_text()
    # Syntax-only binding of the native method callback used by lighting Stop.
    text = text.replace('Remove(Tick)', 'Remove(this.Tick)')
    match = re.search(r'class ' + kind + r'(?:\s*:\s*\w+)?\s*\{', text)
    text = body(text, match.end())
    renamed = re.sub(r'\bHCVisualSeason\w*\b', lambda m: 'HCEvent' + m[0][2:], text)
    renamed_env = {re.sub(r'^HCVisualSeason', 'HCEventVisualSeason', k): v for k, v in env.items()}
    for name in re.findall(r'\b(?:bool|int|float|string|void) (\w+)\(', renamed):
        function = translate(renamed, name, renamed_env, kind, member=True)
        setattr(instance, name, functools.partial(function, instance))
    return instance


class VisualSeasonBehavior(unittest.TestCase):
    def harness(self, seconds=0, remainder=0., baseline=100.):
        self.assertTrue(CLOCK.is_file(), 'missing authored HCVisualSeasons.c: restart/downtime clock unavailable')
        self.assertTrue(STORE.is_file(), 'missing authored HCVisualSeasonStore.c')
        config = N(**json.loads(CONFIG.read_text()))
        self.logs = []
        self.saved = []
        self.jobs = []
        self.now = baseline
        self.fail_write = False
        self.env = dict(
            str=str, Print=self.logs.append,
            GetGame=lambda: N(GetTickTime=lambda: self.now, IsServer=lambda: True),
            HCSaveJob=N(STEP_DONE=0, STEP_MORE=1, STEP_FAILED=2),
            HCVisualSeasonState=lambda: N(Version=1, WorldName='chernarusplus', ElapsedSeconds=0),
            HCVisualSeasonIO=N(HCSave=self.save),
            HCV2Admission=N(Admitted=lambda enabled: enabled, Line=lambda *args: 'synthetic admission'),
            Math=N(Floor=math.floor),
        )
        # SYNTHETIC scheduler registration; HCStep below executes the real store.
        self.env['HCSaveScheduler'] = N(HCUnregister=lambda job: self.jobs.remove(job), HCFlush=self.flush)
        state = N(Version=1, WorldName='chernarusplus', ElapsedSeconds=seconds, RemainderSeconds=remainder)
        job = N(HCDirty=False, HCInFlight=False, Owner=None)
        store = N(m_State=state, m_Job=job, m_Healthy=True, m_SaveStage=0,
                  m_Snapshot=None, m_PersistedSeconds=seconds)
        bind(STORE, 'HCVisualSeasonStore', store, self.env)
        job.Owner = store
        self.jobs.append(job)
        clock = N(m_Config=config, m_Store=store, m_Running=False, m_Paused=False,
                  m_LastTick=0., m_HitchReported=False, m_Fraction=0., m_LastPhase=-1,
                  m_Units=unit_budget(), m_Work=N(HCReset=lambda *a: None, HCContinue=lambda: True))
        bind(CLOCK, 'HCVisualSeasons', clock, self.env)
        self.assertTrue(clock.HCBeginClock(self.now))
        return clock, store, config

    def save(self, state):
        if self.fail_write:
            return False
        self.saved.append(N(**vars(state)))
        return True

    def flush(self, job):
        if not job.HCDirty and not job.HCInFlight:
            return True
        for _ in range(16):
            result = job.Owner.HCStepCheckpoint()
            job.HCInFlight = result == 1
            if result != 1:
                job.HCDirty = False
                return result == 0
        return False

    def advance(self, clock, seconds):
        self.now += seconds
        clock.HCTick()

    def test_restart_downtime_never_jumps_phase_and_all_four_boundaries(self):
        phase_seconds = 604800
        for boundary, expected in enumerate(('summer', 'autumn', 'winter', 'spring'), 1):
            with self.subTest(boundary=boundary):
                clock, store, config = self.harness(boundary * phase_seconds - 1)
                self.assertEqual(phase_seconds, config.PhaseSeconds)
                self.advance(clock, .4)
                self.advance(clock, .6)
                self.assertEqual(expected, clock.HCSeason())
                self.advance(clock, .25)
                store.m_Job.HCDirty = True
                self.assertTrue(self.flush(store.m_Job))
                persisted = self.saved[-1].ElapsedSeconds
                # SYNTHETIC downtime + reboot: a wholly unrelated new uptime
                # baseline is passed to the same authored HCBeginClock body.
                clock, store, _ = self.harness(persisted, self.saved[-1].RemainderSeconds, baseline=9000000.)
                self.assertEqual(expected, clock.HCSeason())
                self.assertEqual(persisted, clock.HCElapsed())
                self.assertAlmostEqual(.25, store.HCRemainder())
                self.advance(clock, 1)
                self.assertEqual(persisted + 1, clock.HCElapsed())
                self.assertTrue(any('clock=server-uptime' in line and 'runtime=PENDING' in line for line in self.logs))

    def test_rollback_gap_and_checkpoint_lag_pause_without_crediting_time(self):
        # Boot 042: a finite forward gap (server start or save hitch) skips the gap
        # without crediting it and keeps the clock running; only a backwards or
        # non-finite clock pauses it.
        clock, store, _ = self.harness(123)
        self.advance(clock, 1)
        self.advance(clock, 42.)
        self.assertFalse(clock.m_Paused)
        self.assertEqual(124, clock.HCElapsed())
        self.advance(clock, 1)
        self.assertEqual(125, clock.HCElapsed())
        self.advance(clock, 999999.)
        self.assertFalse(clock.m_Paused)
        self.assertEqual(125, clock.HCElapsed())
        self.assertEqual(1, sum('reason=hitch' in line for line in self.logs))
        for delta in (-1., float('nan'), float('inf')):
            with self.subTest(delta=delta):
                clock, store, _ = self.harness(123)
                self.advance(clock, 1)
                self.advance(clock, delta)
                self.assertTrue(clock.m_Paused)
                self.assertEqual(124, clock.HCElapsed())
                self.advance(clock, 1)
                self.assertEqual(124, clock.HCElapsed())
        clock, store, config = self.harness()
        for _ in range(config.MaxUncheckpointedSeconds + 1):
            self.advance(clock, 1)
        self.assertTrue(clock.m_Paused)
        self.assertEqual(config.MaxUncheckpointedSeconds, clock.HCElapsed())
        self.assertTrue(store.m_Job.HCDirty)
        self.assertTrue(any('checkpoint-lag' in line for line in self.logs))

    def test_staged_snapshot_stop_flushes_latest_and_failed_save_refuses_retry(self):
        clock, store, _ = self.harness()
        self.advance(clock, 1)
        store.m_Job.HCDirty = True
        self.assertEqual(1, store.HCStepCheckpoint())
        store.m_Job.HCInFlight = True
        self.advance(clock, 1)
        self.assertEqual([], self.saved)
        # Stop must finish the old snapshot AND flush post-snapshot uptime.
        clock.HCStop()
        self.assertEqual([1, 2], [state.ElapsedSeconds for state in self.saved])
        self.assertEqual([], self.jobs)
        self.assertFalse(clock.m_Running)
        self.advance(clock, 1)
        self.assertEqual(2, clock.HCElapsed())
        clock, store, _ = self.harness()
        self.advance(clock, 1)
        self.fail_write = True
        self.assertEqual(1, store.HCStepCheckpoint())
        self.assertEqual(2, store.HCStepCheckpoint())
        self.assertFalse(store.m_Healthy)
        self.assertEqual(2, store.HCStepCheckpoint())
        self.advance(clock, 1)
        self.assertTrue(clock.m_Paused)
        self.assertEqual(1, clock.HCElapsed())

    def test_owner_refusal_operator_off_and_unopened_store_are_safe_no_ops(self):
        clock, store, config = self.harness()
        clock.m_Running = False
        clock.m_Store = None
        self.jobs.clear()
        self.env['HCVisualSeasonIO'].HCLoadConfig = lambda: config
        config.EnableVisualSeasons = False
        self.assertFalse(clock.HCStart(False))
        self.assertFalse(clock.HCStart(True))
        clock.HCTick()
        clock.HCStop()
        self.assertEqual([], self.jobs)
        self.assertEqual([], self.saved)
        self.assertTrue(any('state=off' in line for line in self.logs))
        # A failed open must also leave read-only consumers safe.
        store.m_State = None
        clock.m_Store = store
        self.assertEqual(0, clock.HCElapsed())


if __name__ == '__main__':
    unittest.main()


class VisualSeasonOwnerWiring(unittest.TestCase):
    """HC-6 runs only inside the existing weather-days owner (no registry slot)."""

    def setUp(self):
        source = (ROOT / 'mods/HollowCountry/scripts/4_World/Weather/HCWeatherDaysModule.c').read_text()
        self.owner = source[source.index('modded class ChernarusPlusData'):]

    def method(self, name):
        start = self.owner.index('{', self.owner.index('void ' + name + '(')) + 1
        return body(self.owner, start)

    def test_weather_owner_starts_ticks_and_stops_visual_seasons(self):
        self.assertRegex(self.owner, r'ref\s+HCVisualSeasons\s+m_HCVisualSeasons')
        begin = self.method('HCBeginWeatherDays')
        self.assertLess(begin.index('m_HCWeatherDaysActive = true'), begin.index('m_HCVisualSeasons.HCStart(true)'))
        self.assertIn('m_HCVisualSeasons.HCTick()', self.method('HCTickWeatherDays'))
        self.assertIn('m_HCVisualSeasons.HCStop()', self.method('HCEndWeatherDays'))
        self.assertNotIn('HCVisualSeasons', (ROOT / 'mods/HollowCountry/scripts/4_World/Core/HCModule.c').read_text())


class VisualSeasonPresentationBehavior(unittest.TestCase):
    """HC-51: explicit synthetic weather/client ports, authored decisions only.

    Trace: #150 / HC-51 brief -> phase forecast + bounded snapshot/cache ->
    existing weather/lighting owners. Central spec/plan/tasks files are absent.
    No engine rendering, native interpolation, transport or survival proof.
    """

    def test_four_forecasts_grade_continuity_and_snapshot_off_cleanup(self):
        scripts = ROOT / 'mods/HollowCountry/scripts'
        policy_path = scripts / '3_Game/Atmosphere/HCSeasonVisualPolicy.c'
        client_path = scripts / '5_Mission/Atmosphere/HCSeasonVisualClient.c'
        self.assertTrue(policy_path.is_file(), 'HC-51 seasonal forecast policy missing')
        self.assertTrue(client_path.is_file(), 'HC-51 bounded phase cache missing')
        env = dict(str=str, Print=lambda line: None)
        policy = N()
        env['HCSeasonVisualPolicy'] = policy
        source = policy_path.read_text()
        for kind, name, value in re.findall(r'static const (int|float) (\w+) = ([\d.]+);', source):
            setattr(policy, name, {'int': int, 'float': float}[kind](value))
            env[name] = getattr(policy, name)  # Enforce class constant lookup
        for name in re.findall(r'static (?:bool|int|float|string) (\w+)\(', source):
            setattr(policy, name, translate(source, name, env, 'HCSeasonVisualPolicy'))
        blend = N()
        env['HCLightingBlend'] = blend
        source = (scripts / '3_Game/Atmosphere/HCLightingBlend.c').read_text()
        for name in re.findall(r'static (?:bool|int|float|string) (\w+)\(', source):
            setattr(blend, name, translate(source, name, env, 'HCLightingBlend'))
        weather = N()
        from tests.unit.test_v1_weather import authored_policy
        env.update(HCWeatherDays=weather, HCAtmospherePolicy=authored_policy(), Math=N(Floor=math.floor))
        source = (WEATHER / 'HCWeatherDays.c').read_text()
        for name in re.findall(r'static (?:bool|int|float|string) (\w+)\(', source):
            setattr(weather, name, translate(source, name, env, 'HCWeatherDays'))

        # Wave 6: named half-hour season-fog envelope is continuous at the
        # weather owner's 05:00 and 20:00 boundaries (synthetic hours only).
        self.assertTrue(hasattr(policy, 'FOG_BLEND_HOURS'), 'HC-51 boundary blend missing')
        for edge in (5., 20.):
            left = weather.HCSeasonFog('autumn', 20701, edge - .0001, 0.)
            right = weather.HCSeasonFog('autumn', 20701, edge + .0001, 0.)
            self.assertLess(abs(left - right), .001)

        fog_day = next(day for day in range(20700, 20800)
                       if weather.Profile(day, 7., 0.) == 'fog')
        self.assertLess(abs(weather.HCSeasonFog('autumn', fog_day, 5.0001, 0.) -
                            weather.HCSeasonFog('autumn', fog_day, 4.9999, 0.)), .001,
                        'HC-51 dawn fog-day baseline still pops')

        # Execute the server authority/HC-6 gate body over synthetic handles.
        owner_source = (WEATHER / 'HCWeatherDaysModule.c').read_text()
        owner = N(m_HCWeatherDaysActive=True, m_Weather=N(
            GetMissionWeather=lambda: False, GetWeatherUpdateFrozen=lambda: False),
            m_HCVisualSeasons=N(HCActive=lambda: True, HCPhase=lambda: 2))
        env['GetGame'] = lambda: N(IsServer=lambda: True)
        for name in ('HCWeatherDaysAuthority', 'HCSeasonPhaseCode'):
            fn = translate(owner_source, name, env, 'ChernarusPlusData', member=True)
            setattr(owner, name, functools.partial(fn, owner))
        self.assertEqual(2, owner.HCSeasonPhaseCode())
        owner.m_HCVisualSeasons.HCActive = lambda: False
        self.assertEqual(-1, owner.HCSeasonPhaseCode())
        owner.m_HCVisualSeasons.HCActive = lambda: True
        owner.m_Weather.GetMissionWeather = lambda: True
        self.assertEqual(-1, owner.HCSeasonPhaseCode())
        owner.m_Weather.GetMissionWeather = lambda: False
        owner.m_Weather.GetWeatherUpdateFrozen = lambda: True
        self.assertEqual(-1, owner.HCSeasonPhaseCode())
        owner.m_Weather.GetWeatherUpdateFrozen = lambda: False
        owner.m_HCWeatherDaysActive = False
        self.assertEqual(-1, owner.HCSeasonPhaseCode())
        for helper in ('HCSeasonCloud', 'HCSeasonRain', 'HCSeasonFog', 'HCSeasonSnow'):
            self.assertIn('HCWeatherDays.' + helper + '(', owner_source)
        self.assertIn('Math.Max(fog, actual)', owner_source)
        self.assertIn('m_Weather.SetSnowfallThresholds(', owner_source)
        self.assertIn('phase != m_HCWeatherPhase', owner_source)

        rpc_path = WEATHER / 'HCSeasonSnapshotRPC.c'
        self.assertTrue(rpc_path.is_file(), 'HC-51 snapshot transport missing')
        rpc_source = rpc_path.read_text()
        rpc_id = int(re.search(r'RPC_SEASON = (\d+)', rpc_source)[1])
        self.assertGreater(rpc_id, 4853912)
        for other in scripts.rglob('*.c'):
            if other != rpc_path:
                self.assertNotRegex(re.sub(r'//[^\n]*', '', other.read_text()), rf'\b{rpc_id}\b')
        # Native broadcast is one bounded send, no per-player scan. Same-revision
        # heartbeat revives the cache; phase changes always advance revision.
        from tests.unit.test_hc_client_controls import install
        packets = []
        class SyntheticRPC:
            def __init__(self): self.values = []
            def Write(self, value): self.values.append(value)
            def Send(self, *args): packets.append((tuple(self.values), args))
        rpc_env = dict(GetGame=lambda: N(IsServer=lambda: True), ScriptRPC=SyntheticRPC,
                       HCSeasonVisualPolicy=policy, Print=lambda line: None,
                       HCUnitBudget=lambda: unit_budget(),
                       HCWorkBudget=lambda: N(HCReset=lambda *a: None, HCContinue=lambda: True))
        sender = install(rpc_path, rpc_env, 'HCSeasonSnapshotRPC',
                         ('HCPublish', 'SendTo', 'HCSend', 'HCTick'))
        sender.SendTo('synthetic identity')
        self.assertEqual(((1, 1, -1), (None, rpc_id, True, 'synthetic identity')), packets[-1])
        sender.HCPublish(2)
        self.assertEqual((1, 2, 2), packets[-1][0])
        before = len(packets)
        sender.HCTick(29.)
        self.assertEqual(before, len(packets))
        sender.HCTick(1.)
        self.assertEqual((1, 2, 2), packets[-1][0])
        self.assertIsNone(packets[-1][1][-1])
        sender.HCPublish(4)
        self.assertEqual((1, 2, 2), packets[-1][0])
        sender.HCPublish(-1)
        self.assertEqual((1, 3, -1), packets[-1][0])
        sender.s_Revision = 1999999999
        sender.HCPublish(3)
        self.assertEqual((1, 2000000000, -1), packets[-1][0])
        sender.HCPublish(2)
        self.assertEqual((1, 2000000000, -1), packets[-1][0])

        coordinator = (scripts / '5_Mission/Operations/HCClientPresentation.c').read_text()
        self.assertIn('DayZGame.Event_OnRPC.Insert(HCReceive)', coordinator)
        self.assertIn('DayZGame.Event_OnRPC.Remove(HCReceive)', coordinator)
        self.assertIn('HCSeasonVisualClient.HCApplyServer(version, revision, phaseCode)', coordinator)
        self.assertIn('m_Seasons = new HCSeasonVisualClient', coordinator)
        self.assertIn('m_Lighting = new HCLightingClient', coordinator)
        mission = (scripts / '5_Mission/Operations/HCClientPresentationMission.c').read_text()
        self.assertEqual(3, mission.count('HCSeasonSnapshotRPC.SendTo(identity)'))
        self.assertIn('HCSeasonSnapshotRPC.HCTick(timeslice)', mission)

        phases = ('spring', 'summer', 'autumn', 'winter')
        self.assertEqual(phases, tuple(policy.HCPhaseName(i) for i in range(4)))
        self.assertEqual('unavailable', policy.HCPhaseName(-1))
        self.assertIn('extra_thermal=0 writer=weather_days state=on', weather.HCSeasonLine('winter', .2, True))
        self.assertIn('state=off reason=HC6_NOT_ADMITTED count=0', weather.HCSeasonLine('unavailable', 0., True))
        self.assertIn('state=refused reason=WEATHER_OWNER_NOT_ADMITTED count=0', weather.HCSeasonLine('winter', .2, False))
        rain = [weather.HCSeasonRain(p, 'plain', .8, 12.) for p in phases]
        fog = [weather.HCSeasonFog(p, 20701, 12., 0.) for p in phases]
        snow = [weather.HCSeasonSnow(p, 'plain', .8, 12.) for p in phases]
        self.assertLess(rain[1], rain[0])
        self.assertGreater(rain[2], rain[0])
        self.assertGreater(fog[2], fog[0])
        self.assertEqual([0., 0., 0., policy.WINTER_SNOWFALL], snow)
        self.assertEqual(0, rain[3])
        self.assertGreaterEqual(weather.HCSeasonCloud('winter', 'plain', 0., 12.), .6)
        for phase in phases + ('unavailable',):
            self.assertEqual(0, weather.HCSeasonSnow(phase, 'calm', .95, 12.))
            self.assertEqual(0, weather.HCSeasonSnow(phase, 'plain', .95, 23.))
            self.assertEqual(0, blend.HCSeasonWeight(phase, 23.))
            self.assertEqual('vanilla', blend.HCSeasonName(phase, 23.))
        self.assertEqual(0, weather.HCSeasonSnow('winter', 'plain', .59, 12.))
        self.assertEqual(weather.RainTarget('bad', .95, 12.),
                         weather.HCSeasonRain('unavailable', 'bad', .95, 12.))
        self.assertEqual(0, policy.HCSnowfall('winter', float('nan'), False, False))
        self.assertEqual(0, policy.HCSnowfall('winter', float('inf'), False, False))
        # Existing owner fades to zero before table swaps; all steps stay bounded.
        current = 0.
        for phase in phases:
            target = blend.HCSeasonWeight(phase, 12.)
            while current > 0:
                previous = current
                current = blend.Step(current, 0., 1.)
                self.assertLessEqual(abs(current - previous), .100001)
            self.assertNotEqual('vanilla', blend.HCSeasonName(phase, 12.))
            for _ in range(3):
                previous = current
                current = blend.Step(current, target, 1.)
                self.assertLessEqual(abs(current - previous), .100001)
        self.assertEqual(0, blend.Step(current, .8, 0.))

        # Synthetic DTO fields/native log sink. Every validation/TTL decision
        # below executes the authored client body; no Python seasonal model.
        receipts, states = [], []
        env['Print'] = receipts.append
        cache = N(m_Revision=0, m_Phase=-1, m_ReceivedAt=0., m_Conflict=False,
                  m_LastReceipt='', m_Status=N(HCPublish=lambda *args: states.append(args)))
        env['HCSeasonVisualClient'] = N(s_Current=None)
        source = re.sub(r'(?<![.\w])s_Current\b', 'HCSeasonVisualClient.s_Current', client_path.read_text())
        start = re.search(r'class HCSeasonVisualClient\s*\{', source).end()
        source = body(source, start)
        for name in ('HCAccept', 'HCPhase', 'HCRefuse', 'HCReport', 'HCStop'):
            function = translate(source, name, env, 'HCSeasonVisualClient', member=True)
            setattr(cache, name, functools.partial(function, cache))
        self.assertEqual('unavailable', cache.HCPhase(100.))
        for invalid in (-2, 4):
            self.assertFalse(cache.HCAccept(1, 1, invalid, 100.))
            self.assertEqual('unavailable', cache.HCPhase(100.))
        self.assertEqual(1, len(receipts), 'bad bounds must log once')
        self.assertTrue(cache.HCAccept(1, 1, 2, 100.))
        self.assertEqual('autumn', cache.HCPhase(101.))
        self.assertFalse(cache.HCAccept(1, 0, 2, 101.))
        self.assertEqual('unavailable', cache.HCPhase(102.))
        self.assertTrue(cache.HCAccept(1, 2, 3, 102.))
        self.assertFalse(cache.HCAccept(1, 1, 2, 103.))
        self.assertEqual('winter', cache.HCPhase(103.))
        self.assertFalse(cache.HCAccept(1, 2, 0, 103.))
        self.assertFalse(cache.HCAccept(1, 2, 3, 104.))
        self.assertEqual('unavailable', cache.HCPhase(104.))
        self.assertTrue(cache.HCAccept(1, 3, 3, 105.))
        self.assertTrue(cache.HCAccept(1, 3, 3, 130.))  # unchanged heartbeat
        self.assertEqual('winter', cache.HCPhase(131.))
        self.assertEqual('unavailable', cache.HCPhase(130. + policy.SNAPSHOT_TTL_SECONDS))
        self.assertTrue(cache.HCAccept(1, 3, 3, 230.))
        self.assertEqual('unavailable', cache.HCPhase(229.))  # clock rollback
        self.assertTrue(cache.HCAccept(1, 4, -1, 231.))  # server off
        self.assertEqual('unavailable', cache.HCPhase(232.))
        self.assertTrue(cache.HCAccept(1, 5, 3, 233.))
        cache.HCStop()
        self.assertEqual('unavailable', cache.HCPhase(234.))
        self.assertEqual(('off', 'mission_stop'), states[-1])
        self.assertTrue(any('snapshot_conflict' in line for line in receipts))
        self.assertTrue(any('snapshot_expired' in line for line in receipts))
        self.assertTrue(all('runtime=PENDING' in line for line in receipts))

        # Run the actual registered coordinator receiver with the actual cache;
        # only native RPC out-parameters, clock and effect handles are synthetic.
        subscriptions, receive_logs, stopped = [], [], []
        dedicated = [True]
        game = N(IsDedicatedServer=lambda: dedicated[0], IsMultiplayer=lambda: True,
                 GetTickTime=lambda: 500.)
        producer = lambda: N(Start=lambda: None, Stop=lambda: stopped.append('effect'),
                             HCHandleCount=lambda: 0)
        receiver_env = dict(GetGame=lambda: game, Print=receive_logs.append, tostr=str,
            HCSeasonVisualPolicy=policy, HCSeasonSnapshotRPC=N(RPC_SEASON=rpc_id),
            HCOperationalStatus=lambda: N(HCPublish=lambda *a: None),
            HCUnitBudget=lambda: unit_budget(), HCWorkBudget=lambda: N(),
            HCSignsOfLifeSnapshotClient=producer, HCGradeSettingsClient=producer,
            HCHints=producer, HCEnvSound=producer, HCSignsOfLifeClient=producer,
            make_lighting=lambda handle: producer(),
            profile_read=lambda key: (False, ''),
            HCV2Admission=N(Line=lambda *a: 'synthetic runtime=PENDING'),
            DayZGame=N(Event_OnRPC=N(Insert=subscriptions.append, Remove=subscriptions.remove)))
        real_cache = install(client_path, receiver_env, 'HCSeasonVisualClient',
            ('HCStart', 'HCApplyServer', 'HCReset', 'HCGetPhase', 'HCAccept',
             'HCPhase', 'HCRefuse', 'HCReport', 'HCRejectSnapshot', 'HCStop'))
        install(scripts / '3_Game/HCClientPresentationSettings.c', receiver_env,
                'HCClientPresentationSettings', ('HCValidMask', 'HCAccept', 'HCEffective'))
        c = install(scripts / '5_Mission/Operations/HCClientPresentation.c', receiver_env,
                'HCClientPresentation', ('HCStart', 'HCApplyServer', 'HCReceive',
                    'HCReconcile', 'HCStop', 'HCReport', 'HCHandleCount', 'HCRefuse'))()
        c.HCStart()
        self.assertEqual([], subscriptions, 'dedicated process registered a client receiver')
        dedicated[0] = False
        c.HCStart()
        c.HCStart()
        self.assertEqual(1, len(subscriptions))
        self.assertIsNone(c.m_Seasons, 'server presentation settings not admitted yet')
        c.HCApplyServer(1, 1, 2)  # effective GRADE only
        self.assertIsNotNone(c.m_Seasons)
        def receive(values, sender=None, target=None):
            packet = iter(values)
            subscriptions[0](sender, target, rpc_id, N(ReadValue=lambda: (True, next(packet))))
        receive((1, 1, 4))
        receive((1, 1, 4))
        self.assertEqual(1, sum('reason=snapshot_bounds' in line for line in receive_logs))
        self.assertEqual('unavailable', real_cache.HCGetPhase())
        receive((1, 1, 2), sender=object())
        receive((1, 1, 2), target=object())
        self.assertEqual('unavailable', real_cache.HCGetPhase())
        receive((1, 1, 2))
        self.assertEqual('autumn', real_cache.HCGetPhase())
        c.HCReceive(None, None, rpc_id, None)
        self.assertEqual('unavailable', real_cache.HCGetPhase())
        self.assertTrue(any('reason=malformed_season_rpc' in line for line in receive_logs))
        receive((1, 2, 3))
        self.assertEqual('winter', real_cache.HCGetPhase())
        c.HCStop()
        self.assertEqual([], subscriptions)
        self.assertIsNone(c.m_Seasons)
        self.assertIsNone(c.m_Lighting)
        self.assertEqual('unavailable', real_cache.HCGetPhase())
        c.HCReceive(None, None, rpc_id, None)  # finished mission cannot revive

        # Exercise the actual lighting handler through synthetic native handles.
        # Its one slot, night/underground veto and cleanup remain authoritative.
        lerps, loaded, removed = [], [], []
        phase, alive, underground, cellars, night = ['autumn'], [True], [False], [False], [False]
        world = N(SetUserLightingLerp=lerps.append, GetSunOrMoon=lambda: 1.,
                  GetSunOrMoonDirection=lambda: [0., -1., 0.], IsNight=lambda: night[0])
        phenomena = N(GetActual=lambda: .1)
        native_weather = N(GetOvercast=lambda: phenomena, GetRain=lambda: N(GetActual=lambda: 0.),
                           GetFog=lambda: N(GetActual=lambda: .04))
        viewer = N(IsAlive=lambda: alive[0], IsUnconscious=lambda: False,
                   GetUndergroundPresence=lambda: int(underground[0]))
        env.update(GetGame=lambda: N(GetWorld=lambda: world, GetPlayer=lambda: viewer,
                   GetWeather=lambda: native_weather, GetDayTime=lambda: 12.,
                   GetCallQueue=lambda category: N(Remove=removed.append)),
                   HCSeasonVisualClient=N(HCGetPhase=lambda: phase[0]),
                   HCCellarsClient=N(HCVisualActive=lambda: cellars[0]),
                   PlayerBase=N(Cast=lambda value: value),
                   PPERequesterBank=N(REQ_UNDERGROUND=1, IsRequesterRunning=lambda key: underground[0]),
                   EUndergroundPresence=N(NONE=0), CALL_CATEGORY_SYSTEM=0,
                   Math=N(Clamp=lambda value, low, high: max(low, min(high, value))))
        lighting = N(m_HCRunning=True, m_HCOwnsSlot=False, m_HCLoaded='', m_HCWeight=0.,
                     m_HCLogSeconds=60., m_HCLoggedName='', m_HCLoggedWeight=-1.,
                     m_HCLighting=N(HCLoadLightingTable=loaded.append),
                     m_HCSeasonUnits=unit_budget(),
                     m_HCSeasonWork=N(HCReset=lambda *args: None, HCContinue=lambda: True))
        bind(scripts / '5_Mission/Atmosphere/HCLightingClient.c', 'HCLightingClient', lighting, env)
        lighting.Tick()
        self.assertEqual(['dusk_warm'], loaded)
        self.assertAlmostEqual(.1, lerps[-1])
        phase[0] = 'winter'
        lighting.Tick()
        self.assertEqual(['dusk_warm'], loaded)  # fade out before switching
        self.assertEqual(0., lerps[-1])
        lighting.Tick()
        self.assertEqual(['dusk_warm', 'dusk_cold'], loaded)
        alive[0] = False
        lighting.Tick()
        self.assertEqual(0., lerps[-1], 'HC-51 grade remains active after death')
        alive[0] = True
        lighting.Tick()
        night[0] = True
        lighting.Tick()
        self.assertEqual(0., lerps[-1])
        night[0] = False
        underground[0] = True
        previous = len(lerps)
        lighting.Tick()
        self.assertEqual(previous, len(lerps), 'HC grade wrote the native underground slot')
        underground[0] = False
        lighting.Tick()
        lighting.Stop()
        self.assertEqual(0., lerps[-1])
        self.assertEqual([lighting.Tick], removed)
        previous = len(lerps)
        lighting.Tick()
        self.assertEqual(previous, len(lerps), 'off lighting still writes native lerp')

        # Survival hooks stay absent from this feature; HC-2 already retired
        # meal warmth. Stock same-weather survival controls still need DayZ.
        seasonal_sources = policy_path.read_text() + client_path.read_text()
        for forbidden in ('modded class Environment', 'modded class PlayerBase',
                          'AddToEnvironmentTemperature(', 'SetHeatComfort(', 'AddWet(', 'SetDate('):
            self.assertNotIn(forbidden, seasonal_sources)
