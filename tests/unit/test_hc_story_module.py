"""HC-19 round 2: authored module behavior through explicit SYNTHETIC ports.

Uses the existing scenes translator; clocks, stores, leases and cleanup are
synthetic. These receipts establish no native/runtime acceptance.

Spec/plan/task: HC-19 / #147; round-2 task-r2.md supersedes round-1 module
ownership. The local task inputs supply the coverage-plan excerpt; the two
AGENTS.md spec paths are absent in this portable worker checkout.

Actual TDD receipts, 2026-11-18 (commands run from the worktree):
P1-1:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_module.StoryModuleBehavior.test_empty_page_preserves_gap_check_then_returns_without_indexing -v
  RED: IndexError: list index out of range; FAILED (errors=2).
  GREEN: same command, Ran 1 test; OK.
P1-2:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_module.StoryModuleBehavior.test_tick_runs_work_before_story_and_skips_saved_or_stopped_slot tests.unit.test_hc_story_module.StoryModuleBehavior.test_stop_does_not_reenter_when_heartbeat_flush_fails -v
  RED: [('work-gap', 100), ('story', 1000)] != [('work-gap', 100)];
       RecursionError: maximum recursion depth exceeded; FAILED (failures=1, errors=1).
  GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_module -v
       Ran 7 tests; OK (before adding the P2 cases).
P2-1:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_module.StoryModuleBehavior.test_retired_release_reclaims_only_its_bounded_refusal_keys -v
  RED: 'unique-id' unexpectedly found; retired ID must release preflight logging capacity.
  GREEN: same command, Ran 1 test; OK.
P2-2:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_module.StoryModuleBehavior.test_bad_story_inputs_disable_only_stories_with_one_diagnostic -v
  RED: False is not true : invalid story input must preserve valid legacy Scenes;
       FAILED (failures=2), invalid-config and template-catalog.
  GREEN: same command, Ran 1 test; OK.
P2-3:
  PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_hc_story_schedule.StoryScheduleBehavior.test_operator_off_legacy_state_saves_object_then_migrates_once -v
  RED: unexpectedly None : legacy Stories must serialize as an object, never null.
  GREEN: same command, Ran 1 test; OK.
"""
import functools
from pathlib import Path
import re
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import EArray
from tests.unit.test_hc_story_schedule import bind

SCENES = Path(__file__).resolve().parents[2] / 'mods/HollowCountry/scripts/4_World/Scenes'
MODULE = SCENES / 'HCScenesModule.c'


def adapted(value):
    return re.sub(r'\bHC(?:Scene|Story|Save|Work|V2|Group|Ecology|Wildlife)\w*', lambda m: 'HCEvent' + m[0][2:], value)


def module_method(owner, name, env):
    ports = {adapted(key): value for key, value in env.items()}
    ports.setdefault('EArray', EArray)
    ports.setdefault('str', str)
    # Only syntax/type spelling is adapted, as in test_v2_scenes.
    source = adapted(MODULE.read_text())
    source = source.replace('array<vector> positions;', 'HCEventPositions positions;')
    source = source.replace('GetGame().GetWorldName(world);', 'world = GetGame().GetWorldName();')
    method = translate(source, name, ports, 'HCEventScenesModule', member=True)
    setattr(owner, name, functools.partial(method, owner))


class StoryModuleBehavior(unittest.TestCase):
    def owner(self, env=None):
        self.calls = []
        self.job = N(HCDirty=True, HCInFlight=True, HCDue=0)
        self.env = dict(Print=lambda line: self.calls.append(('log', line)),
                        GetGame=lambda: N(IsServer=lambda: True, GetTickTime=lambda: 20.),
                        HCSaveJob=N(STEP_FAILED=-1, STEP_DONE=1),
                        s_CleanupOwner=None)
        self.env.update(env or {})
        owner = N(m_Running=True, m_Stopping=False, m_Stories=None,
                  m_SaveJob=self.job, m_State=N(Revision=4, LastNow=100, Chains=EArray(), Stories=N(NextSequence=1),
                                              Catalog=N(Chains=EArray())),
                  m_Leases=EArray(), m_Cursor=0, m_WorkElapsed=0, m_LogElapsed=0,
                  m_LastNow=100, m_WorkBudget=N(HCReset=lambda value: None),
                  Now=lambda: 1000, Summary=lambda: None,
                  ReleaseRefusals=lambda key: None)
        return owner

    def bind(self, owner, *names):
        for name in names:
            module_method(owner, name, self.env)

    def test_empty_page_preserves_gap_check_then_returns_without_indexing(self):
        calls = []
        for paused in (0, 600):
            with self.subTest(paused=paused):
                owner = N(m_State=N(Chains=EArray(), Catalog=N(Chains=EArray())),
                          m_Cursor=9, Commit=lambda now: calls.append(('save', now)) or True)
                env = {'Print': lambda line: None,
                       'HCSceneChains': N(ResumeAfterGap=lambda state, now: calls.append(('gap', now)) or paused)}
                module_method(owner, 'Work', env)
                owner.Work(1000)
                self.assertEqual(9, owner.m_Cursor, 'empty page must not advance/index a scene cursor')
        self.assertEqual([('gap', 1000), ('gap', 1000), ('save', 1000)], calls)

    def test_tick_runs_work_before_story_and_skips_saved_or_stopped_slot(self):
        for saved, stopped in ((False, False), (True, False), (False, True)):
            with self.subTest(saved=saved, stopped=stopped):
                owner = self.owner()

                def work(now):
                    self.calls.append(('work-gap', owner.m_State.LastNow))
                    if saved:
                        owner.m_State.Revision += 1
                    if stopped:
                        owner.m_Running = False

                owner.Work = work
                owner.StoryStep = lambda now: self.calls.append(('story', now))
                self.bind(owner, 'OnTick')
                owner.OnTick(10)
                expected = [('work-gap', 100)]
                if not saved and not stopped:
                    expected.append(('story', 1000))
                self.assertEqual(expected, self.calls)

    def test_downtime_commit_is_seen_before_story_can_write_last_now(self):
        owner = self.owner()
        chain = N(Id='synthetic-waiting', Cancelled=False, Complete=False, EventId=0,
                  Stage=0, DueAt=200, ExpiresAt=500, BeganAt=0)
        owner.m_State.Chains.Insert(chain)
        owner.m_State.Catalog.Chains.Insert(N(Stages=EArray([N()])))
        owner.Lease = lambda key: None
        resume = translate(adapted((SCENES / 'HCSceneChains.c').read_text()),
                           'ResumeAfterGap', {}, 'HCEventSceneChains')

        def gap(state, now):
            self.calls.append(('gap', state.LastNow))
            return resume(state, now)

        self.env['HCSceneChains'] = N(ResumeAfterGap=gap, CancelExpired=lambda *args: False)
        self.env['HCEventStatus'] = N(ANNOUNCED=1, COMPLETED=4)

        def save(state):
            self.calls.append(('save', state.LastNow))
            state.Revision += 1
            return True

        owner.m_Store = N(Save=save)
        owner.StoryStep = lambda now: self.calls.append(('story', now))
        self.bind(owner, 'OnTick', 'Work', 'Commit', 'SaveBarrierDone')
        owner.OnTick(10)
        self.assertEqual([('gap', 100), ('save', 1000)],
                         [call for call in self.calls if call[0] != 'log'])
        self.assertEqual((False, False, 80.), (self.job.HCDirty, self.job.HCInFlight, self.job.HCDue))
        self.assertEqual((1100, 1400), (chain.DueAt, chain.ExpiresAt))

    def test_story_steps_without_receipts_and_requires_terminal_cleanup(self):
        owner = self.owner()
        candidate = [None]
        cleaned = [False]
        owner.Lease = lambda key: 'synthetic-lease'
        owner.Cleanup = lambda lease: cleaned[0]
        owner.m_Stories = N(HCReady=lambda: True, HCCandidate=lambda: candidate[0],
                             HCStep=lambda now, released: self.calls.append((now, list(released))) or False)
        self.bind(owner, 'StoryStep')
        owner.StoryStep(101)
        candidate[0] = N(Id='unique-id', Complete=False, Cancelled=False)
        owner.StoryStep(102)
        candidate[0].Cancelled = True
        owner.StoryStep(103)
        cleaned[0] = True
        owner.StoryStep(104)
        self.assertEqual([(101, []), (102, []), (103, []), (104, ['unique-id'])], self.calls)
        self.assertEqual((True, True, 0), (self.job.HCDirty, self.job.HCInFlight, self.job.HCDue))

    def test_story_barriers_clear_flags_only_for_success_or_save_failure(self):
        for result, ready, reason in ((True, True, ''), (False, True, ''),
                                      (False, False, 'save-failed'),
                                      (False, False, 'world-clock'),
                                      (False, False, 'sequence-exhausted')):
            with self.subTest(result=result, reason=reason):
                owner = self.owner()
                readiness = [True]

                def step(now, released):
                    readiness[0] = ready
                    return result

                owner.m_Stories = N(HCReady=lambda: readiness[0], HCCandidate=lambda: None,
                                     HCStep=step, HCReason=lambda: reason)
                owner.OnStop = lambda: self.calls.append(('stop',))
                self.bind(owner, 'StoryStep', 'SaveBarrierDone')
                owner.StoryStep(110)
                cleared = result or reason == 'save-failed'
                self.assertEqual((not cleared, not cleared, 80. if cleared else 0),
                                 (self.job.HCDirty, self.job.HCInFlight, self.job.HCDue))
                self.assertEqual(ready, owner.m_Running)
                self.assertEqual([] if ready else [('stop',)], self.calls)

    def test_stop_does_not_reenter_when_heartbeat_flush_fails(self):
        owner = self.owner()
        owner.m_Stories = N(HCStop=lambda: self.calls.append(('story-stop',)))
        owner.m_Store = N(SaveAbandon=lambda: self.calls.append(('abandon',)),
                          SaveInFlight=lambda: False, SaveStep=lambda state: -1)

        def flush(job):
            self.calls.append(('flush',))
            owner.HCStepRoutine()

        self.env['HCSaveScheduler'] = N(HCFlush=flush,
                                          HCUnregister=lambda job: self.calls.append(('unregister',)))
        self.bind(owner, 'OnStop', 'HCStepRoutine')
        owner.OnStop()
        self.assertFalse(owner.m_Running)
        self.assertEqual(1, self.calls.count(('flush',)))
        self.assertEqual(1, self.calls.count(('unregister',)))
        self.assertLess(self.calls.index(('story-stop',)), self.calls.index(('flush',)))

    def test_start_wires_schedule_before_save_job_and_preserves_start_refusal(self):
        for reason in ('', 'operator-off', 'invalid-state'):
            with self.subTest(reason=reason):
                owner = self.owner()
                state = owner.m_State
                owner.m_Running = False
                owner.m_AdmissionPrinted = True
                owner.m_SummaryPrinted = True
                owner.IsEnabled = lambda settings: True
                owner.m_SaveJob = None

                def start(*args):
                    self.calls.append(('start', args[0] is state, owner.m_SaveJob is None))
                    return not reason

                self.env.update(GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus'),
                                HCSceneChainStore=lambda: N(Open=lambda now: state),
                                HCStoryPolicy=N(HCLoadConfig=lambda: N()),
                                HCStorySchedule=lambda: N(HCStart=start, HCReason=lambda: reason),
                                HCSceneSaveJob=lambda: N(),
                                HCSaveScheduler=N(HCRegister=lambda job: self.calls.append(('register',))))
                self.bind(owner, 'OnStart')
                owner.OnStart(N())
                self.assertIn(('start', True, True), self.calls)
                self.assertEqual(reason != 'invalid-state', owner.m_Running)
                self.assertEqual(reason != 'invalid-state', ('register',) in self.calls)

    def test_retired_release_reclaims_only_its_bounded_refusal_keys(self):
        class Reasons(dict):
            def Remove(self, key):
                self.pop(key, None)

        class Refusals(EArray):
            def RemoveItem(self, value):
                if value in self:
                    self.remove(value)

        owner = self.owner()
        owner.m_PreflightReasons = Reasons({'unique-id': 'slope', **{f'other-{i}': 'slope' for i in range(15)}})
        owner.m_AdvertiseRefusals = Refusals(['unique-id:' + str(i) for i in range(3)] +
                                            ['other-id:' + str(i) for i in range(9)])
        candidate = N(Id='unique-id', Complete=True, Cancelled=False)
        cleaned = [False]
        owner.Lease = lambda key: None
        owner.Cleanup = lambda lease: cleaned[0]
        owner.m_Stories = N(HCReady=lambda: True, HCCandidate=lambda: candidate,
                             HCStep=lambda now, released: False)
        self.bind(owner, 'StoryStep', 'ReleaseRefusals')
        owner.StoryStep(101)
        self.assertEqual(16, len(owner.m_PreflightReasons), 'observer-blocked cleanup retains refusal history')
        self.assertEqual(12, len(owner.m_AdvertiseRefusals))
        cleaned[0] = True
        owner.StoryStep(102)
        self.assertNotIn('unique-id', owner.m_PreflightReasons, 'retired ID must release preflight logging capacity')
        self.assertEqual({f'other-{i}' for i in range(15)}, set(owner.m_PreflightReasons))
        self.assertEqual(['other-id:' + str(i) for i in range(9)], owner.m_AdvertiseRefusals)
        self.bind(owner, 'AdvertiseRefused')
        owner.AdvertiseRefused(N(ChainId='fresh-id', Stage=0), 'event-module-unavailable')
        self.assertIn('fresh-id:0', owner.m_AdvertiseRefusals)
        self.assertTrue(any('fresh-id' in line for kind, line in self.calls if kind == 'log'))

    def test_bad_story_inputs_disable_only_stories_with_one_diagnostic(self):
        for cause in ('invalid-config', 'template-catalog'):
            with self.subTest(cause=cause):
                owner = self.owner()
                owner.m_Running = False
                owner.m_AdmissionPrinted = True
                owner.m_SummaryPrinted = True
                owner.IsEnabled = lambda settings: True
                state = owner.m_State
                state.Stories = None
                config = None if cause == 'invalid-config' else N(EnableStories=True)
                schedule = N(m_Ready=False, m_Reason='', m_State=None)
                env = dict(EArray=EArray, str=str,
                           Print=lambda line: self.calls.append(('log', line)),
                           HCEventStoryProgress=lambda: N(NextSequence=1),
                           HCV2Admission=N(Admitted=lambda enabled: enabled),
                           HCEventStoryPolicy=N(HCConfigValid=lambda value: value is not None,
                                                HCValid=lambda value: True),
                           HCEventSceneChains=N(LoadCatalog=lambda: None))
                bind('HCStorySchedule', schedule, env, member=True)
                self.env.update(GetGame=lambda: N(IsServer=lambda: True, GetWorldName=lambda: 'chernarusplus'),
                                HCSceneChainStore=lambda: N(Open=lambda now: state),
                                HCStoryPolicy=N(HCLoadConfig=lambda: config),
                                HCStorySchedule=lambda: schedule, HCSceneSaveJob=lambda: N(),
                                HCSaveScheduler=N(HCRegister=lambda job: self.calls.append(('register',))))
                self.bind(owner, 'OnStart')
                owner.OnStart(N())
                self.assertTrue(owner.m_Running, 'invalid story input must preserve valid legacy Scenes')
                self.assertEqual('operator-off', schedule.HCReason())
                self.assertFalse(schedule.HCReady())
                self.assertIn(('register',), self.calls)
                logs = [call[1] for call in self.calls if call[0] == 'log']
                self.assertEqual(1, len(logs), 'one off diagnostic; no module-wide refusal')
                self.assertIn(cause, logs[0])
                self.assertIn('runtime=PENDING', logs[0])


if __name__ == '__main__':
    unittest.main()
