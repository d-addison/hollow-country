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
                  m_LastTick=0., m_Fraction=0., m_LastPhase=-1,
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
        for delta in (-1., 999999., float('nan'), float('inf')):
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
