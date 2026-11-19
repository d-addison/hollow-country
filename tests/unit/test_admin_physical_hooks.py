"""Authored physical-hook policy; all engine collaborators are synthetic."""
import unittest
from types import SimpleNamespace as NS
from tests.unit.test_admin_test_kit import ADMIN, SCRIPTS, Cell, base_scope, compile_authored

CAMP = SCRIPTS / '4_World/Camps/HCCampModule.c'
PROBES = SCRIPTS / '4_World/Camps/HCCampProbes.c'

class PhysicalHooks(unittest.TestCase):
    def test_selected_camp_reaches_physical_owner_without_mutating_cooldowns(self):
        for raid in (False, True):
            camp = NS(LastVisit=17, LastProbe=19)
            calls = []
            def request(selected, requested_raid, reason):
                calls.append((selected, requested_raid))
                reason.value = 'physical-request; runtime=PENDING'
                return True
            owner = NS(HCAdminSelectCamp=lambda pos, reason: camp, HCAdminRequestArrival=request)
            fn = compile_authored(ADMIN / 'HCAdminDirectors.c', 'HCCampModule', 'HCAdminArrival',
                                  base_scope(), ('HCAdminSelectCamp', 'HCAdminRequestArrival'))
            reason = Cell()
            self.assertTrue(fn(owner, (0, 0, 0), raid, reason))
            self.assertEqual([(camp, raid)], calls)
            self.assertEqual((17, 19), (camp.LastVisit, camp.LastProbe))

    def test_probe_request_retains_eligibility_and_provider_refusal(self):
        for enabled, eligible, warned, expected in ((False, True, True, False),
                (True, False, True, False), (True, True, False, False), (True, True, True, True)):
            calls = []
            scope = base_scope(HCCampProbes=NS(HCEnabled=lambda: enabled,
                Eligible=lambda *args: eligible), HCEscalationClock=NS(Day=lambda: 20),
                HCBaseRaid=NS(HCWarn=lambda *args: calls.append('warn') or warned,
                              HCRefusal=lambda: 'BASE_RAID_PARTY_NOT_OBSERVED'))
            fn = compile_authored(PROBES, 'HCCampProbes', 'HCRequestRaidParty', scope, modded=False)
            reason = Cell()
            self.assertEqual(expected, fn(None, NS(), NS(Tier=3, LastProbe=5),
                                         NS(Hidden=lambda burning: False), False, 300000, reason))
            self.assertEqual(['warn'] if enabled and eligible else [], calls)
            if enabled and eligible and not warned:
                self.assertIn('BASE_RAID_PARTY_NOT_OBSERVED', reason.value)

    def test_visitor_request_keeps_durable_cooldown_and_reservation(self):
        from tests.unit.test_admin_test_kit import ROOT
        path = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'
        for reserved, saved, expected in ((False, True, False), (True, False, False), (True, True, True)):
            calls = []
            owner = NS(Commit=lambda now: calls.append('save') or saved)
            camp = NS(LastVisit=0)
            service = NS(HCReserve=lambda *args: calls.append('reserve') or reserved,
                         HCCancel=lambda: calls.append('cancel'), m_Due=0, m_Ends=0,
                         m_Config=NS(RaidSeconds=600))
            fn = compile_authored(path, 'HCAdminVisitorParty', 'HCVisit', base_scope(Print=lambda line: calls.append('reserved-log')),
                                  ('HCReserve', 'HCCancel'), modded=False)
            self.assertEqual(expected, fn(service, owner, camp, 300000))
            if reserved:
                self.assertEqual(300000, camp.LastVisit)
                self.assertEqual(['reserve', 'save'] + (['reserved-log'] if saved else ['cancel']), calls)
            else:
                self.assertEqual(0, camp.LastVisit)

class VisitorSafety(unittest.TestCase):
    def test_visit_tick_retains_budget_attendance_combat_and_expiry(self):
        from tests.unit.test_admin_test_kit import ROOT
        path = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'
        for budget, attended, combat, used, now, expected in (
                (False, False, False, False, 100, []),
                (True, True, False, False, 100, ['cancel']),
                (True, False, True, False, 100, ['cancel']),
                (True, False, False, True, 100, ['cancel']),
                (True, False, False, False, 700, ['cancel']),
                (True, False, False, False, 100, ['walk'])):
            calls = []
            scope = base_scope(HCCampProbes=NS(HCVisitorsEnabled=lambda: True, HCEnabled=lambda: True),
                HCBaseRaid=NS(HCEnabled=lambda: True, HCUnattended=lambda *args: not attended),
                HCW38SituationRuntime=NS(HCUsed=lambda lease: used),
                HCUnitBudget=NS(HC_WORK_BASE_RAID=12),
                HCServer=NS(HCTickWork=lambda: NS(HCTakeFor=lambda *args: budget)))
            owner = NS(HCReady=lambda: True, HCLiveParty=lambda: True,
                HCCancel=lambda: calls.append('cancel'), HCSense=lambda: calls.append('sense'),
                HCWalkTo=lambda point: calls.append('walk') or True,
                m_Config=NS(MaxObjects=128, MaxPlayers=32, MaxRouteNodes=32), m_Reserved=True,
                m_Camp=NS(LastVisit=50), m_Ends=650, m_Site=NS(ProposalId='lease'),
                m_Owner=NS(), m_Point=(0, 0, 0), m_Walking=False,
                m_Actor=NS(GetGroup=lambda: NS(IsInCombat=lambda: combat)))
            fn = compile_authored(path, 'HCAdminVisitorParty', 'HCVisitStep', scope,
                ('HCReady', 'HCLiveParty', 'HCCancel', 'HCSense', 'HCWalkTo'), modded=False)
            fn(owner, now)
            self.assertEqual(expected, calls)

    def test_actual_probe_policy_cannot_be_reset_by_admin(self):
        fn = compile_authored(PROBES, 'HCCampProbes', 'Eligible', base_scope(), modded=False)
        for tier, day, now, last, hidden, expected in (
                (3, 14, 300000, 0, False, True), (2, 14, 300000, 0, False, False),
                (3, 13, 300000, 0, False, False), (3, 14, 300000, 0, True, False),
                (3, 14, 300000, 299999, False, False), (3, 14, 300000, 300001, False, False)):
            self.assertEqual(expected, fn(None, tier, day, now, last, hidden))

    def test_visitor_request_cannot_skip_perception_or_observers(self):
        for ready, eligible, seen, unattended, visited in (
                (False, True, True, True, True), (True, False, True, True, True),
                (True, True, False, True, True), (True, True, True, False, True),
                (True, True, True, True, False), (True, True, True, True, True)):
            calls = []
            status = NS(HCState=lambda: 'ready' if ready else 'degraded', HCReason=lambda: 'provider-pending')
            port = NS(HCSeen=lambda *args: calls.append('seen') or seen,
                      HCVisit=lambda *args: calls.append('visit') or visited)
            scope = base_scope(s_Visitor=port,
                HCCampProbes=NS(HCGetOperationalStatus=lambda: status, Eligible=lambda *args: eligible,
                               HCRefuse=lambda reason: calls.append(reason)),
                HCEscalationClock=NS(Day=lambda: 14),
                HCBaseRaid=NS(HCUnattended=lambda *args: calls.append('attendance') or unattended))
            fn = compile_authored(PROBES, 'HCCampProbes', 'HCRequestVisitorParty', scope, modded=False)
            result = fn(None, NS(), NS(Tier=3, LastVisit=0, Position=(0, 0, 0)),
                        NS(Hidden=lambda burning: False), False, 300000, Cell())
            self.assertEqual(ready and eligible and seen and unattended and visited, result)
            if not (ready and eligible and seen and unattended):
                self.assertNotIn('visit', calls)


class VisitorReadiness(unittest.TestCase):
    """Synthetic lifecycle phases; no party or native acceptance is supplied."""
    def test_director_startup_failure_stop_and_adapter_binding_publish_live_status(self):
        from tests.unit.test_admin_test_kit import ROOT
        path = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World/HCXAIBaseRaid.c'
        adapter = NS()
        lifecycle = NS(adapter=adapter, director=None, phase='wait')
        config = NS()
        director = NS(Phase=lambda: lifecycle.phase)
        scope = base_scope(HCXAIService=NS(Adapter=lambda: lifecycle.adapter),
                           HCXAISiteDirector=NS(Active=lambda: lifecycle.director),
                           HCCampProbes=NS(HCVisitorsEnabled=lambda: True),
                           HCBaseRaid=NS(HCEnabled=lambda: True, HCConfig=lambda: config))
        refusal = compile_authored(path, 'HCAdminVisitorParty', 'HCRefusal', scope, modded=False)
        ready = compile_authored(path, 'HCAdminVisitorParty', 'HCReady', scope,
                                 ('HCRefusal',), modded=False)
        open_visitor = compile_authored(path, 'HCAdminVisitorParty', 'HCOpenVisitor',
                                        scope, modded=False)
        lifecycle.director = director
        visitor = NS(m_Healthy=False, m_Config=None, m_HCAdapter=None, m_HCDirector=None)
        open_visitor(visitor, adapter)
        self.assertIs(adapter, visitor.m_HCAdapter)
        self.assertIs(director, visitor.m_HCDirector)
        visitor.HCRefusal = lambda: refusal(visitor)
        visitor.HCReady = lambda: ready(visitor)
        published = NS(state='', reason='')
        def publish(state, reason):
            published.state, published.reason = state, reason
        status = NS(HCPublish=publish)
        probe_scope = base_scope(s_Visitor=visitor, s_VisitorStatus=status,
            HCCampProbes=NS(HCVisitorsEnabled=lambda: True, HCEnabled=lambda: True),
            HCBaseRaid=NS(HCEnabled=lambda: True))
        operational = compile_authored(PROBES, 'HCCampProbes', 'HCGetOperationalStatus',
                                       probe_scope, modded=False)
        for phase in ('missing', 'wait', 'bind', 'qualify', 'create', 'off', 'refused',
                      'run', 'stopped', 'missing', 'run', 'adapter-stopped',
                      'adapter-replaced', 'director-replaced'):
            with self.subTest(phase=phase):
                lifecycle.phase = phase
                lifecycle.director = None if phase == 'missing' else director
                lifecycle.adapter = None if phase == 'adapter-stopped' else adapter
                if phase == 'adapter-replaced':
                    lifecycle.adapter = NS(replacement=True)
                if phase == 'director-replaced':
                    lifecycle.director = NS(Phase=lambda: 'run')
                self.assertIs(status, operational(None))
                self.assertEqual('ready' if phase == 'run' else 'degraded', published.state)
                if phase != 'run':
                    expected = ('CAMP_VISITOR_ADAPTER_UNAVAILABLE' if phase in ('adapter-stopped', 'adapter-replaced')
                                else 'CAMP_VISITOR_DIRECTOR_UNAVAILABLE' if phase in ('missing', 'director-replaced')
                                else 'CAMP_VISITOR_DIRECTOR_' + phase)
                    self.assertEqual(expected, published.reason)
        lifecycle.adapter, lifecycle.director, lifecycle.phase = adapter, director, 'run'
        visitor.m_Config = None
        operational(None)
        self.assertEqual(('degraded', 'CAMP_VISITOR_CONFIG_UNAVAILABLE'),
                         (published.state, published.reason))


if __name__ == '__main__': unittest.main()
