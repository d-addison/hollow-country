"""Audit #121 (worker B): rising-body and conditional custom-pose transitions.

Spec: the shipped sit/get-up pair is admitted (unverified); lying risers, flat
sleepers and feeding stay refused until their original clips and graph states are
shipped; the server adapter is interruption safe and the Variety selector can pick
a posed body. Plan/tasks: executable translated Enforce on explicit synthetic
native ports; no DayZ animation, replication, perception or two-client proof.

Actual RED (before implementation), focused command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_auditpose_riser -v
"""
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from tests.legacy.test_event_runtime import translate as scalar
from tests.legacy.test_infected_admission import Array, translate
from tools.anim import build_anims_addon as addon

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / 'mods/HollowCountry/scripts/4_World/Infected/Variety'
ADMISSION = AREA / 'HCPostureAdmission.c'
POLICY = AREA / 'HCInfectedVarietyPolicy.c'
NATIVE = AREA / 'HCInfectedVarietyNative.c'
VARIETY = AREA / 'HCInfectedVariety.c'
POSE = ROOT / 'mods/HollowCountryAnims/scripts/4_World/HCPoseInfected.c'
GRAPH = ROOT / 'mods/HollowCountryAnims/anims/infected/hc_poses.agf'
DOC = ROOT / 'docs/ANIMATION_PIPELINE.md'

TIER_C = ('sit_wall', 'prone_sleep', 'riser', 'feed_kneel')


def admission():
    policy = N()
    for name in ('HCCanEnter', 'HCPostureRefusal', 'HCPoseMode', 'HCRiseSeconds', 'HCTierCState'):
        setattr(policy, name, scalar(ADMISSION.read_text(), name,
                dict(HCPostureAdmission=policy), 'HCPostureAdmission'))
    return policy


def variety_policy(posture):
    policy = N()
    env = dict(HCPostureAdmission=posture, HCInfectedVarietyPolicy=policy)
    for name in ('HCStandingFresh', 'HCPosePrimary', 'HCPoseFresh', 'HCPoseClass'):
        setattr(policy, name, scalar(POLICY.read_text(), name, env, 'HCInfectedVarietyPolicy'))
    return policy


class PostureAdmissionAssets(unittest.TestCase):
    def test_tier_c_admission_follows_only_shipped_assets(self):
        posture = admission()
        self.assertEqual('sit_wall', posture.HCPoseMode(1))
        self.assertEqual('prone_sleep', posture.HCPoseMode(2))
        self.assertEqual('riser', posture.HCPoseMode(3))
        self.assertEqual('feed_kneel', posture.HCPoseMode(4))
        self.assertEqual('unsupported', posture.HCPoseMode(5))
        self.assertTrue(posture.HCCanEnter('sit_wall'), 'shipped sit pair must be admitted unverified')
        for mode in ('prone_sleep', 'riser', 'feed_kneel', 'invented'):
            self.assertFalse(posture.HCCanEnter(mode), mode + ' has no authored clips')
        self.assertEqual('none_graph_admitted_unverified', posture.HCPostureRefusal('sit_wall'))
        for mode in ('prone_sleep', 'riser', 'feed_kneel'):
            self.assertEqual('ASSET_NOT_AUTHORED_' + mode, posture.HCPostureRefusal(mode))
        self.assertEqual('admitted_unverified', posture.HCTierCState('sit_wall'))
        self.assertEqual('asset_missing', posture.HCTierCState('riser'))

    def test_rise_length_is_a_per_pose_asset_fact(self):
        posture = admission()
        self.assertAlmostEqual(1.7, posture.HCRiseSeconds(1))
        for pose in (2, 3, 4):
            self.assertGreater(posture.HCRiseSeconds(pose), 1.7)
        for pose in (-1, 0, 5):
            self.assertEqual(0, posture.HCRiseSeconds(pose))

    def test_shipped_set_equals_graph_states_equals_clips(self):
        # Gate that forces the next worker to flip admission, graph and build
        # script together: a shipped pose needs an entry transition and two clips,
        # an unshipped pose must have neither (no graph source without a clip).
        posture = admission()
        graph = GRAPH.read_text()
        entered = {int(n) for n in re.findall(r'FromState "Vanilla"\s+ToState "\w+"[^}]*?GetCommandI\(CMD_HC_POSE\) == (\d)', graph)}
        shipped = {pose for pose in (1, 2, 3, 4) if posture.HCCanEnter(posture.HCPoseMode(pose))}
        self.assertEqual(shipped, entered)
        self.assertEqual(2 * len(shipped), len(addon.CLIPS))
        spec = DOC.read_text()
        for pose in (2, 3, 4):
            self.assertIn('CMD_HC_POSE == %d' % pose, spec, 'asset spec missing for pose %d' % pose)


class PoseSelection(unittest.TestCase):
    def test_fresh_pose_is_cadenced_context_fitted_and_falls_back_to_shipped_sit(self):
        policy = variety_policy(admission())
        self.assertEqual('HC_ZmbM_Sitter', policy.HCPoseClass())
        picks = [policy.HCPoseFresh('wreck', i, 3, True) for i in range(3)]
        self.assertEqual([0, 0, 1], picks, 'riser unshipped: wreck falls back to the shipped sit')
        self.assertEqual(1, policy.HCPoseFresh('church', 2, 3, True))
        self.assertEqual(1, policy.HCPoseFresh('gas_station', 2, 3, True))
        self.assertEqual(0, policy.HCPoseFresh('wreck', 2, 0, True), 'cadence 0 is the opt-out')
        self.assertEqual(0, policy.HCPoseFresh('wreck', 2, 3, False), 'addon class absent')
        self.assertEqual(0, policy.HCPoseFresh('invented', 2, 3, True))

    def test_preferred_pose_wins_once_its_assets_are_admitted(self):
        posture = admission()
        posture.HCCanEnter = lambda mode: mode in ('sit_wall', 'riser', 'feed_kneel')
        policy = variety_policy(posture)
        self.assertEqual(3, policy.HCPoseFresh('wreck', 2, 3, True))
        self.assertEqual(4, policy.HCPoseFresh('gas_station', 2, 3, True))
        self.assertEqual(1, policy.HCPoseFresh('roadside', 2, 3, True), 'prone refused: sit fallback')

    def test_config_posed_cadence_is_optional_defaulted_and_bounded(self):
        keys = N(present=True)
        defaults = translate(str(VARIETY), 'void HCApplyOptionalDefaults(', (), fields=('PosedFreshEvery', 'MaxPosed'),
                             HCJsonFields=N(Has=lambda text, key: keys.present),
                             HCInfectedVarietyPolicy=N(DEFAULT_POSED_FRESH_EVERY=3))
        owner = N(PosedFreshEvery=0)
        keys.present = False
        defaults(owner, '{}', False)
        self.assertEqual(3, owner.PosedFreshEvery, 'missing key must default ON, not zero-fill off')
        owner.PosedFreshEvery = 1
        keys.present = True
        defaults(owner, '{"PosedFreshEvery": 1}', False)
        self.assertEqual(1, owner.PosedFreshEvery, 'explicit operator value kept')
        defaults(owner, '{"PosedFreshEvery": 1}', True)
        self.assertEqual(0, owner.PosedFreshEvery, 'acceptance disable marker opts out')
        valid = translate(str(VARIETY), 'bool HCPosedCadenceValid(', (), fields=('PosedFreshEvery', 'MaxFreshBodies'))
        for value, expected in ((0, True), (3, True), (-1, False), (4, False)):
            self.assertEqual(expected, valid(N(PosedFreshEvery=value, MaxFreshBodies=3)), value)


class FreshPosedBody(unittest.TestCase):
    def actor(self, calm=True, pose_ok=True, admitted=True):
        idle, requests, wakes = [], [], []
        posture = N(HCCanEnter=lambda mode: admitted, HCPoseMode=lambda pose: 'riser')
        env = dict(GetGame=lambda: N(IsServer=lambda: True),
                   HCInfectedVarietyModule=N(VarietyActive=lambda: True),
                   HCPostureAdmission=posture,
                   DayZInfectedConstants=N(MINDSTATE_CALM=0))
        actor = N(m_HCVarietyTriedDormant=False, m_HCVarietyDormant=False, m_HCVarietyPosed=False,
                  m_HCVarietySleepUntil=9., IsAlive=lambda: True, IsCrawling=lambda: False,
                  IsBeingBackstabbed=lambda: False,
                  GetInputController=lambda: N(GetMindState=lambda: 0 if calm else 2),
                  GetAIAgent=lambda: N(SetKeepInIdle=idle.append),
                  HCVarietyAssign=lambda *a: None,
                  HCVarietyPoseRequest=lambda pose: requests.append(pose) or pose_ok,
                  HCVarietyPoseWake=lambda: wakes.append(1))
        names = ('HCVarietyAssign', 'HCVarietyPoseRequest', 'HCVarietyPoseWake', 'IsAlive',
                 'IsCrawling', 'IsBeingBackstabbed', 'GetInputController', 'GetAIAgent')
        from types import MethodType
        for name, signature in (('HCVarietyFreshPosed', 'bool HCVarietyFreshPosed('),
                                ('HCVarietyWake', 'bool HCVarietyWake(')):
            fn = translate(str(NATIVE), signature, names, **env)
            setattr(actor, name, MethodType(fn, actor))
        return actor, idle, requests, wakes

    def test_posed_body_latches_idle_once_and_wake_releases_pose_and_idle_once(self):
        actor, idle, requests, wakes = self.actor()
        self.assertTrue(actor.HCVarietyFreshPosed(1., 'site', 1, 3))
        self.assertEqual([3], requests)
        self.assertTrue(actor.m_HCVarietyDormant and actor.m_HCVarietyPosed)
        self.assertFalse(actor.HCVarietyFreshPosed(2., 'site', 1, 3), 'second entry must not re-pose')
        self.assertTrue(actor.HCVarietyWake())
        self.assertFalse(actor.HCVarietyWake())
        self.assertEqual([1], wakes, 'the pose rise is requested exactly once')
        self.assertEqual([True, False], idle)

    def test_refusals_leave_the_body_a_normal_actor(self):
        for kwargs in (dict(calm=False), dict(pose_ok=False), dict(admitted=False)):
            actor, idle, requests, wakes = self.actor(**kwargs)
            self.assertFalse(actor.HCVarietyFreshPosed(1., 'site', 1, 3), str(kwargs))
            self.assertEqual([], idle)
            self.assertFalse(actor.m_HCVarietyDormant or actor.m_HCVarietyPosed)

    def test_dead_or_deleted_posed_body_still_releases_pose_without_resurrecting(self):
        actor, idle, requests, wakes = self.actor()
        self.assertTrue(actor.HCVarietyFreshPosed(1., 'site', 1, 1))
        actor.IsAlive = lambda: False
        self.assertTrue(actor.HCVarietyWake())
        self.assertEqual([True], idle, 'dead actor: native finisher owns the idle latch')
        self.assertEqual([1], wakes, 'adapter must be told so the pose slot is freed')


class SitterAdapter(unittest.TestCase):
    def request(self, sitter, pose, posed=0, budget=12):
        logs = []
        game = N(IsServer=lambda: True)
        posture = admission()
        statics = N(s_HCPosed=posed, s_HCLastRefusal='')
        env = dict(g_Game=game, GetGame=lambda: game, Print=logs.append, STATICS=statics,
                   HCPostureAdmission=posture,
                   HCInfectedVariety=N(HCMaxPosed=lambda: budget))
        refuse = translate(str(POSE), 'bool HCRefusePose(', (), statics=('s_HCLastRefusal',), **env)
        sitter.HCRefusePose = lambda refused: refuse(sitter, refused)
        fn = translate(str(POSE), 'bool HCRequestPose(', ('IsAlive', 'HCRefusePose'),
                       statics=('s_HCPosed', 's_HCLastRefusal'), **env)
        return fn(sitter, pose), logs, statics

    def sitter(self, **kw):
        base = dict(m_HCPose=0, m_HCHolding=False, m_HCStarted=False, m_HCRising=False,
                    IsAlive=lambda: True)
        base.update(kw)
        return N(**base)

    def test_shipped_sit_is_requestable_and_unshipped_poses_refuse_once_per_change(self):
        sitter = self.sitter()
        ok, logs, statics = self.request(sitter, 1)
        self.assertTrue(ok)
        self.assertEqual(1, statics.s_HCPosed)
        self.assertEqual(1, sitter.m_HCPose)
        for pose in (2, 3, 4):
            sitter = self.sitter()
            ok, logs, statics = self.request(sitter, pose)
            self.assertFalse(ok, 'pose %d has no asset' % pose)
            self.assertEqual(0, statics.s_HCPosed)
            self.assertTrue(any('ASSET_NOT_AUTHORED' in line and 'runtime=PENDING' in line for line in logs))

    def test_new_pose_cannot_interrupt_a_rise_but_cleanup_still_can(self):
        sitter = self.sitter(m_HCRising=True, m_HCPose=0, m_HCHolding=True)
        ok, _, statics = self.request(sitter, 1, posed=1)
        self.assertFalse(ok, 'a rising body must finish its get-up before posing again')
        self.assertEqual(1, statics.s_HCPosed)
        ok, _, _ = self.request(sitter, 0, posed=1)
        self.assertTrue(ok)

    def test_budget_refuses_the_thirteenth_pose(self):
        sitter = self.sitter()
        ok, logs, statics = self.request(sitter, 1, posed=12)
        self.assertFalse(ok)
        self.assertEqual(12, statics.s_HCPosed)

    def test_variety_hooks_route_to_the_request_path(self):
        calls = []
        source = POSE.read_text()
        self.assertIn('override bool HCVarietyPoseRequest(int pose)', source)
        self.assertIn('override void HCVarietyPoseWake()', source)
        req = translate(str(POSE), 'override bool HCVarietyPoseRequest(', ('HCRequestPose',))
        wake = translate(str(POSE), 'override void HCVarietyPoseWake(', ('HCRequestPose',))
        owner = N(HCRequestPose=lambda pose: calls.append(pose) or True)
        self.assertTrue(req(owner, 3))
        wake(owner)
        self.assertEqual([3, 0], calls)

    def test_rise_length_follows_the_pose_being_left_and_reports_to_the_owner(self):
        posture = admission()
        noted = []
        sent = []
        owner = N(HCWantedPose=lambda: 0, HCNoteRise=lambda: noted.append(1))
        command = N(m_HCOwner=owner, m_HCSent=2, m_HCRise=-1., m_HCResend=0., m_HCRiseFrom=-1,
                    finished=[], HCSend=None)
        command.HCSend = lambda pose: (sent.append(pose), setattr(command, 'm_HCSent', pose),
                                       setattr(command, 'm_HCResend', 0.))
        fn = translate(str(POSE), 'override void PreAnimUpdate(', ('HCSend',),
                       HCPostureAdmission=posture, SetFlagFinished=lambda f: command.finished.append(f))
        fn(command, 0.1)
        self.assertEqual([0], sent)
        self.assertEqual([1], noted)
        self.assertEqual(2, command.m_HCRiseFrom)
        fn(command, 1.8)
        self.assertEqual([], command.finished, 'pose 2 rises longer than the sit get-up')
        fn(command, 1.0)
        self.assertEqual([True], command.finished)


class StepSelection(unittest.TestCase):
    def run_step(self, context, ordinal_made, class_present=True, every=3, standing_every=2):
        created, entries, refused = [], [], []
        site = N(Id='synthetic-place', Context=context, Position=[1000., 0., 1000.])
        state = N(s_Running=True, s_Pending=True, s_Admin=True, s_NextAutomatic=0.,
                  s_Config=N(MaxFreshBodies=3, GroupMembers=3, StandingRiserEvery=standing_every,
                             PosedFreshEvery=every, Sites=Array([site]), ContextRange=40.,
                             GroupSpacing=4., InterestRange=1000.),
                  s_Bodies=Array(), s_Selected=0, s_Made=ordinal_made,
                  s_Tried=Array(), s_Used=Array(), s_LastRefusal='')
        def spawn(kind, pos):
            created.append(kind)
            return N(HCVarietyFreshCrawler=lambda *a: entries.append('crawler') or True,
                     HCVarietyFreshStanding=lambda *a: entries.append('standing') or True,
                     HCVarietyFreshPosed=lambda now, place, role, pose: entries.append('pose%d' % pose) or True)
        policy = variety_policy(admission())
        policy.HCContextRole = lambda *a: 0
        method = translate(str(VARIETY), 'static void HCStep(', ('HCNearestCandidate', 'HCHidden', 'HCRefuse'),
            statics=tuple(vars(state)), STATICS=state,
            HCInfectedVarietyModule=N(VarietyActive=lambda: True),
            HCInfectedModule=N(Instance=N(HCVarietyFreshRoom=lambda s: True, HCLODMaterialize=spawn)),
            HCServer=N(HCTickWork=lambda: N(HCTakeFor=lambda *a: True)),
            HCUnitBudget=N(HC_WORK_INFECTED=0), HCPerfPlayers=N(HCGet=lambda: Array()),
            GetGame=lambda: N(SurfaceY=lambda *a: 0., ConfigIsExisting=lambda path: class_present),
            HCInfectedLOD=N(NearestDistance=lambda *a: 500.),
            HCAdminPlacement=N(HCClear=lambda p: True),
            HCInfectedVarietyPolicy=policy, Print=lambda *a: None)
        owner = N(HCNearestCandidate=lambda: 0, HCHidden=lambda *a: True, HCRefuse=refused.append)
        method(owner, 1., 1.)
        return created, entries, refused

    def test_third_body_of_a_group_is_posed_through_the_addon_class(self):
        created, entries, _ = self.run_step('church', 2)
        self.assertEqual(['HC_ZmbM_Sitter'], created)
        self.assertEqual(['pose1'], entries)

    def test_other_ordinals_keep_native_crawler_and_standing_variants(self):
        self.assertEqual((['ZmbM_CitizenASkinny_Brown'], ['crawler']), self.run_step('church', 0)[:2])
        self.assertEqual((['ZmbM_CitizenASkinny_Brown'], ['standing']), self.run_step('church', 1)[:2])

    def test_missing_addon_class_or_opt_out_falls_back_to_the_native_variant(self):
        created, entries, _ = self.run_step('church', 2, class_present=False, standing_every=0)
        self.assertEqual((['ZmbM_CitizenASkinny_Brown'], ['crawler']), (created, entries))
        created, entries, _ = self.run_step('church', 2, every=0, standing_every=0)
        self.assertEqual(['crawler'], entries)


if __name__ == '__main__':
    unittest.main()
