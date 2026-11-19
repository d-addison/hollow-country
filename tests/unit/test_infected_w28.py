"""Wave 12 w28-infected (#193 / #160): infected variety hold, LOD HerdWorld default, route refusal logs.

Authored Enforce bodies run on explicit synthetic ports (restricted translators);
no fixture here establishes DayZ behaviour. Runtime acceptance stays PENDING.

RED (2026-11-19, before the source edits):
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_w28 -v
Ran 12 tests; FAILED (failures=9, errors=1); e.g.
AssertionError: 220.0 != 700.0 : non-calm hold must use the named setting
AssertionError: 'pack_reason=not_started' not found in '... pack_reason=none ...'
AssertionError: Missing authored method HCRestoreMissingDefaults
GREEN: same command after the edits, see the commit message.
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.unit.json_loader_port import json_fields_port
from tests.unit.test_event_runtime import translate as execute
from tests.unit import test_hc_burn_infected as burn
from tests.unit import test_hc_postures as postures
from tests.unit import test_infected_admission as admission
from tests.unit.test_infected_lod_followups import lod_config

NATIVE = postures.NATIVE
bind = postures.bind
authored = burn.authored
module_call = admission.module_call
Recorder = admission.Recorder

ROOT = Path(__file__).resolve().parents[2]
INFECTED = ROOT / 'mods/HollowCountry/scripts/4_World/Infected'
STORE = INFECTED / 'LOD/HCInfectedLODStore.c'
POLICY = INFECTED / 'Variety/HCInfectedVarietyPolicy.c'


def retry_seconds():
    return float(re.search(r'HC_VARIETY_RETRY_SECONDS = ([0-9.]+);', NATIVE.read_text())[1])


def policy_constants():
    text = POLICY.read_text()
    return N(**{name: float(value) for name, value in re.findall(
        r'static const float (\w+) = ([0-9.]+);', text)})


class NonCalmHold(unittest.TestCase):
    def crawler(self, hold, mind):
        latches = []
        actor = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False,
                  m_HCVarietyNextTry=0., m_HCVarietySleepUntil=0., IsAlive=lambda: True,
                  IsCrawling=lambda: True, IsBeingBackstabbed=lambda: False,
                  GetInputController=lambda: N(GetMindState=lambda: mind[0]),
                  GetAIAgent=lambda: N(SetKeepInIdle=latches.append))
        env = dict(GetGame=lambda: N(IsServer=lambda: True),
                   HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                   HCPostureAdmission=N(HCCanEnter=lambda mode: True),
                   HCInfectedLOD=N(HCVarietyNonCalmHoldSeconds=lambda: hold),
                   DayZInfectedConstants=N(MINDSTATE_CALM=0),
                   STATICS=N(HC_VARIETY_RETRY_SECONDS=retry_seconds()))
        bind(NATIVE, actor, ('HCVarietyCanTry', 'HCVarietySleep'), env,
             statics=('HC_VARIETY_RETRY_SECONDS',),
             bound=('IsAlive', 'IsCrawling', 'IsBeingBackstabbed', 'GetInputController', 'GetAIAgent'))
        return actor, latches

    def test_non_calm_crawler_is_held_for_the_configured_seconds(self):
        mind = [4]
        actor, latches = self.crawler(120., mind)
        self.assertFalse(actor.HCVarietySleep(100., True))
        self.assertEqual(220., actor.m_HCVarietyNextTry, 'non-calm hold must use the named setting')
        self.assertFalse(actor.HCVarietyCanTry(219.))
        mind[0] = 0
        self.assertTrue(actor.HCVarietyCanTry(220.))
        self.assertTrue(actor.HCVarietySleep(220., True))
        self.assertEqual([True], latches)

    def test_default_hold_equals_the_shipped_failed_roll_cooldown(self):
        mind = [4]
        actor, _ = self.crawler(retry_seconds(), mind)
        self.assertFalse(actor.HCVarietySleep(100., True))
        self.assertEqual(100. + 600., actor.m_HCVarietyNextTry, 'default behaviour must stay 600 s')
        constants = policy_constants()
        self.assertEqual(600., constants.DEFAULT_NONCALM_HOLD_SECONDS)
        self.assertEqual(retry_seconds(), constants.DEFAULT_NONCALM_HOLD_SECONDS)
        cfg, _ = lod_config()
        self.assertEqual(600, cfg.VarietyNonCalmHoldSeconds)

    def test_failed_roll_and_missing_agent_keep_the_failed_roll_cooldown(self):
        mind = [0]
        actor, _ = self.crawler(30., mind)
        self.assertFalse(actor.HCVarietySleep(100., False))
        self.assertEqual(700., actor.m_HCVarietyNextTry, 'permitted=false stays on HC_VARIETY_RETRY_SECONDS')

    def accessor(self, active, config):
        env = dict(HCInfectedLOD=N(Active=lambda: active), s_Config=config,
                   HCInfectedVarietyPolicy=policy_constants())
        text = NATIVE.read_text()
        return execute(text, 'HCVarietyNonCalmHoldSeconds', env)

    def test_inactive_lod_reports_the_default_and_active_lod_the_configured_hold(self):
        self.assertEqual(600., self.accessor(False, N(VarietyNonCalmHoldSeconds=90))())
        self.assertEqual(90, self.accessor(True, N(VarietyNonCalmHoldSeconds=90))())

    def test_hold_range_is_validated_by_named_bounds(self):
        constants = policy_constants()
        valid = execute(POLICY.read_text(), 'ValidNonCalmHold', dict(HCInfectedVarietyPolicy=constants,
                        **vars(constants)))
        self.assertTrue(valid(600.))
        self.assertTrue(valid(constants.MIN_NONCALM_HOLD_SECONDS))
        self.assertTrue(valid(constants.MAX_NONCALM_HOLD_SECONDS))
        self.assertFalse(valid(0.), 'native zero-fill must not be a valid hold')
        self.assertFalse(valid(constants.MIN_NONCALM_HOLD_SECONDS - 1))
        self.assertFalse(valid(constants.MAX_NONCALM_HOLD_SECONDS + 1))
        self.assertIn('ValidNonCalmHold(VarietyNonCalmHoldSeconds)', STORE.read_text())


class MissingKeyDefaults(unittest.TestCase):
    def restore(self):
        printed = []
        fresh, _ = lod_config()
        env = dict(Print=lambda line: printed.append(str(line)), HCJsonFields=json_fields_port(),
                   HCInfectedLODConfig=lambda: fresh_copy(fresh))
        # Translator adapter only: its typed-local list has no HCInfectedLODConfig.
        text = STORE.read_text().replace('HCInfectedLODConfig declared', 'HCEventHandle declared')
        return execute(text, 'HCRestoreMissingDefaults', env), printed

    def zero_filled(self):
        cfg, _ = lod_config()
        cfg.HerdWorld = ''
        cfg.VarietyNonCalmHoldSeconds = 0
        return cfg

    def test_missing_herd_world_restores_the_declared_default_and_names_the_key(self):
        restore, printed = self.restore()
        cfg = self.zero_filled()
        restore(cfg, '{"SchemaVersion":1,"VarietyNonCalmHoldSeconds":600}')
        self.assertEqual('chernarusplus', cfg.HerdWorld)
        self.assertEqual(1, len(printed), printed)
        self.assertIn('HerdWorld', printed[0])
        self.assertIn('runtime=PENDING', printed[0])

    def test_present_keys_are_left_alone_including_an_explicit_empty_world(self):
        restore, printed = self.restore()
        cfg = self.zero_filled()
        cfg.VarietyNonCalmHoldSeconds = 120
        restore(cfg, '{"SchemaVersion":1,"HerdWorld":"","VarietyNonCalmHoldSeconds":120}')
        self.assertEqual('', cfg.HerdWorld, 'explicit empty is an operator choice')
        self.assertEqual(120, cfg.VarietyNonCalmHoldSeconds)
        self.assertEqual([], printed)

    def test_missing_hold_restores_600_so_an_older_lod_json_still_loads(self):
        restore, printed = self.restore()
        cfg = self.zero_filled()
        cfg.HerdWorld = 'chernarusplus'
        restore(cfg, '{"SchemaVersion":1,"HerdWorld":"chernarusplus"}')
        self.assertEqual(600, cfg.VarietyNonCalmHoldSeconds)
        self.assertEqual(1, len(printed), printed)
        self.assertIn('VarietyNonCalmHoldSeconds', printed[0])

    def test_load_no_longer_refuses_a_missing_herd_world(self):
        load = STORE.read_text().split('static HCInfectedLODConfig Load(out string reason)', 1)[1].split('\n    }\n', 1)[0]
        self.assertNotIn('lod.json missing HerdWorld; preserving file', load)
        self.assertIn('HCRestoreMissingDefaults(config, content)', load)
        # Other invalid keys still preserve the file through IsValid.
        self.assertIn('invalid lod.json ranges/caps/classes/herds; preserving file', load)


def fresh_copy(template):
    return N(**vars(template))


class RouteRefusalAndQuarantine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        admission.UnqualifiedPathsPerformNoMutation.setUpClass()

    def helper(self):
        return admission.UnqualifiedPathsPerformNoMutation('test_investigation_positive_control_starts_one_bounded_search')

    def failing_pack(self, started, reason):
        class Pack:
            def __init__(self):
                self.ran = False

            def Start(self, *args):
                self.ran = started
                return False

            def HCStartRan(self):
                return self.ran

            def IsReleasing(self):
                return False

            def HCRefusalReason(self):
                return reason

            def Release(self):
                pass
        return Pack

    def test_failed_pack_start_in_try_investigate_logs_the_refusal_reason_once(self):
        helper = self.helper()
        rec = Recorder()
        ctx, actor = helper.investigate_context(rec, {'Investigation': True})
        printed = []
        ctx.m_LastRouteRefusal = ''
        ctx.HCNoteRouteRefusal = lambda site, reason: module_call(
            'protected void HCNoteRouteRefusal(', ctx, site, reason, Print=lambda line: printed.append(str(line)))
        pack = self.failing_pack(True, 'no_ai_world')
        module_call('protected void TryInvestigate(', ctx, actor, HCInfectedPolicy=helper.policy,
                    HCNativeInfectedPack=pack, DayZInfectedConstants=N(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4),
                    Math=N(Min=min), **helper.stimulus_namespace())
        self.assertEqual(1, actor.SearchAttempts)
        self.assertIsNone(actor.SearchPack, 'a refused Start must not adopt the pack')
        self.assertEqual(0, len(ctx.m_Investigators))
        self.assertEqual(1, len(printed), printed)
        self.assertIn('[HC Infected] investigate pack route refused reason=no_ai_world', printed[0])
        self.assertIn('runtime=PENDING', printed[0])

    def quarantine_line(self, pack_class):
        helper = self.helper()
        rec = Recorder()
        ctx = helper.adopt_context(rec, {'CEAdoption': True, 'NativePackRoutes': True})
        printed = []
        namespace = dict(
            HCInfectedPolicy=helper.policy, Print=lambda message: printed.append(str(message)),
            HCInfectedStore=N(ValidPosition=lambda v: True), HCInfectedClock=N(UtcSeconds=lambda: 10),
            HCHordeStimulus=N(ChooseClue=lambda actor, now, hearing: helper.clue(),
                              PreferClue=lambda a, b, now: a is not None and b is None,
                              PreferHotClue=lambda a, b, now: a is not None and b is None),
            HCHordeRecovery=N(Capture=lambda candidates, record: None),
            HCHordeRecord=lambda: N(RecoveryConflicted=False),
            HCNativeInfectedPack=pack_class, HCHordeSweep=lambda: N(),
            DayZInfectedConstants=N(MINDSTATE_CHASE=3, MINDSTATE_FIGHT=4),
            vector=N(DistanceSq=lambda a, b: sum((x - y) ** 2 for x, y in zip(a, b))))
        module_call('protected void TryAdopt(', ctx, 100, **namespace)
        lines = [line for line in printed if 'cohort quarantined' in line]
        self.assertEqual(1, len(lines), printed)
        return lines[0]

    def test_quarantine_separates_start_never_ran_from_an_empty_reason(self):
        never = self.quarantine_line(self.failing_pack(False, ''))
        self.assertIn('pack_reason=not_started', never)
        empty = self.quarantine_line(self.failing_pack(True, ''))
        self.assertIn('pack_reason=none', empty)
        real = self.quarantine_line(self.failing_pack(True, 'route_unreachable'))
        self.assertIn('pack_reason=route_unreachable', real)

    def test_pack_tracks_that_start_ran_even_when_it_refuses(self):
        fixture = burn.NativePackRefusals('test_every_refusal_reports_its_reason_and_state_is_unchanged')
        pack = fixture.fixture()
        authored('4_World/Infected/HCInfectedNavigation.c', 'HCNativeInfectedPack', ('HCStartRan',), pack, dict())
        pack.m_HCStartRan = False
        self.assertFalse(pack.HCStartRan(), 'before the first Start call')
        fixture.state['release'].append('pending')
        fixture.assert_refused(pack, 'release_pending')
        self.assertTrue(pack.HCStartRan(), 'a refused Start still ran')


if __name__ == '__main__':
    unittest.main()
