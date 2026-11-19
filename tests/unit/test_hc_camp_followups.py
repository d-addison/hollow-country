"""#176: execute authored camp handlers on explicit synthetic ports, not DayZ."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as N
import re
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate
from tests.unit.test_hc_ai_camps import authored_camp_api

ROOT = Path(__file__).resolve().parents[2]
ROUTINE = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAICampRoutine.c'


def synthetic_routine(size=3):
    """Provider ports record requests only; no engine motion/emote is simulated."""
    cfg, _ = authored_camp_api()
    requests, logs, reads = [], [], []
    flags = N(now=100, combat=False)
    actors = EArray(N(IsAlive=lambda: True, GetIdentity=lambda: None,
                     GetPosition=lambda: (0, 0, 0),
                     GetEmoteManager=lambda: N(IsEmotePlaying=lambda: False,
                                               CanPlayEmote=lambda value: True),
                     Expansion_SetEmote=lambda *args: requests.append(('rest', args)),
                     OverrideTargetPosition=lambda *args: requests.append(('walk', args)))
                    for _ in range(size))
    group = N(Count=actors.Count, GetMember=lambda index: actors[index],
              IsInCombat=lambda: flags.combat)
    site = N(Transient=True, Completed=False, Qualified=True, Patrol=N(m_Group=group),
             ProposalId='synthetic-lease', PatrolPoints=EArray([(0, 0, 0)]),
             HCCampMemberCursor=0, HCCampRoleEpoch=0, HCCampNextRoleAt=0,
             HCCampRefusal='')
    view = N(Home=N(State='OCCUPIED', Id='synthetic-house', HousePos=(0, 0, 0)),
             Level=3, Supply=9, Population=size)
    homes = N(HCRoutineView=lambda identity: reads.append(identity) or view,
              HCRoutinePolicy=lambda: cfg, HCOwnsOccupant=lambda *args: True)
    director = N(Phase=lambda: 'run', States=lambda: EArray([site]))
    env = dict(GetGame=lambda: N(IsServer=lambda: True),
               HCXAISiteDirector=N(Active=lambda: director), HCHoldouts=N(Get=lambda: homes),
               HCWorldMaterializer=N(HCIdentity=lambda lease: N(HCCampId=lambda: EStr('camp:synthetic-house'))),
               HCPerfPlayers=N(HCGet=lambda: EArray([object()])),
               HCWorldClock=N(UTC=lambda: flags.now), eAIBase=N(Cast=lambda actor: actor),
               EmoteConstants=N(ID_EMOTE_SITA=123),  # Explicit synthetic enum.
               vector=N(DistanceSq=lambda a, b: sum((x-y)**2 for x, y in zip(a, b))),
               Print=logs.append, str=str)
    source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', ROUTINE.read_text())
    source = source.replace('protected ', '')
    source = re.sub(r'array<ref HCXAISiteState>|array<Man>', 'HCArray', source)
    source = source.replace('eAIGroup group', 'HCGroup group').replace('eAIBase actor', 'HCActor actor')
    translate(source, 'HCXAICampRoutine', env, only=('Step', 'Close', 'HCRefuse'))
    worker = N(m_Enabled=True, m_Closed=False, m_Cursor=0,
               m_Units=N(HCReset=lambda n: None, HCTake=lambda n: True),
               m_Work=N(HCReset=lambda n: None, HCContinue=lambda: True))
    for name in ('Step', 'Close', 'HCRefuse'):
        setattr(worker, name, lambda *args, name=name: env[name](worker, *args))
    return worker, flags, site, view, requests, logs, reads, cfg


class CampFollowups(unittest.TestCase):
    def test_unclearable_movement_is_refused_across_release_threat_and_close(self):
        worker, flags, site, view, requests, logs, reads, cfg = synthetic_routine()
        for _ in range(3): worker.Step()
        self.assertFalse(any(kind == 'walk' for kind, _ in requests),
                         'unclearable camp target override must remain refused')
        self.assertTrue(any('ROUTINE_TARGET_CLEAR_UNAVAILABLE' in line for line in logs))
        self.assertEqual(['rest'], [kind for kind, _ in requests])
        for takeover in ('combat', 'alert', 'release', 'close'):
            with self.subTest(takeover=takeover):
                flags.now += cfg.RoleSeconds
                if takeover == 'combat': flags.combat = True
                if takeover == 'alert': view.Home.State = 'ALERT'
                if takeover == 'release': site.Completed = True
                if takeover == 'close': worker.Close()
                count = len(requests)
                worker.Step()
                self.assertEqual(count, len(requests))
                flags.combat = False
                view.Home.State = 'OCCUPIED'
                site.Completed = False

    def test_solo_keeps_rest_role_and_cooldown_does_not_read_snapshot(self):
        worker, flags, site, view, requests, logs, reads, cfg = synthetic_routine(1)
        worker.Step()
        self.assertEqual(['rest'], [kind for kind, _ in requests],
                         'a solo member must keep a non-sentry role')
        for _ in range(5): worker.Step()
        self.assertEqual(1, len(reads), 'cooldown must not rebuild the JSON view')
        self.assertEqual(1, len(requests))
        flags.now += cfg.RoleSeconds
        worker.Step()  # Relief boundary, no view needed.
        self.assertEqual(1, len(reads))
        worker.Step()
        self.assertEqual(['rest', 'rest'], [kind for kind, _ in requests])
        self.assertEqual(2, len(reads))

    def test_role_cooldown_does_not_read_routine_snapshot(self):
        worker, flags, site, view, requests, logs, reads, cfg = synthetic_routine()
        for _ in range(3): worker.Step()
        count = len(reads)
        for _ in range(5): worker.Step()
        self.assertEqual(count, len(reads), 'cooldown must not rebuild the JSON view')
        flags.now += cfg.RoleSeconds
        worker.Step()
        self.assertEqual(count, len(reads), 'relief boundary needs no JSON view')

    def test_visitor_refusal_logs_once_across_signal_changes_and_failed_commit(self):
        source = (ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCCampVisitors.c').read_text()
        source = re.sub(r'([\w.]+)\.ToString\(\)', r'str(\1)', source)
        logs, writes = [], []
        env = dict(Print=logs.append, str=str)
        translate(source, 'HCCampVisitors', env, only=('Step',))
        camp = N(Id='synthetic-camp', Tier=1, Signal='', LastSignal=0,
                 VisitorRefusal='')
        module = N(Commit=lambda now: writes.append(deepcopy(camp)) or True)
        for index, signal in enumerate(('quiet', 'signal-fire', 'quiet', 'tripwire')):
            env['Step'](module, camp, N(Signal=lambda burning, signal=signal: signal), True,
                        10000 + index * 1800)
        self.assertEqual(1, len(logs), 'signal changes are not visitor-state transitions')
        self.assertIn('VISITOR_BODY_NOT_OBSERVED', logs[0])
        self.assertEqual('VISITOR_BODY_NOT_OBSERVED', writes[-1].VisitorRefusal)
        camp = deepcopy(writes[-1])  # Synthetic persisted-image restart.
        env['Step'](module, camp, N(Signal=lambda burning: 'megaphone'), True, 18000)
        self.assertEqual(1, len(logs), 'restart must retain the refusal state')
        camp.VisitorRefusal = ''  # Explicit synthetic transition back to pending.
        module.Commit = lambda now: False
        env['Step'](module, camp, N(Signal=lambda burning: 'quiet'), True, 20000)
        self.assertEqual('', camp.VisitorRefusal, 'failed persistence cannot acknowledge refusal')
        module.Commit = lambda now: True
        env['Step'](module, camp, N(Signal=lambda burning: 'quiet'), True, 22000)
        self.assertEqual(2, len(logs))


if __name__ == '__main__':
    unittest.main()
