"""#203 reservation exclusion; every native/provider collaborator is synthetic."""
import unittest
from types import SimpleNamespace as NS

from tests.legacy.test_admin_test_kit import (
    ROOT, base_scope, compile_authored,
)
from tests.legacy.test_group_server import EArray
from tests.legacy.test_map_layers import translate

WORLD = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
HOOK = WORLD / 'HCXAIBaseRaid.c'
CORE = ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCBaseRaid.c'
PROBES = CORE.with_name('HCCampProbes.c')


class PartyOwnership(unittest.TestCase):
    def fixture(self, adapter_name, reservation):
        calls = []
        group = NS(route=['visitor-route'], mode=7, Count=lambda: 1,
                   GetMember=lambda index: NS(IsAlive=lambda: True))
        group.GetWaypoints = lambda: EArray(group.route)
        group.GetWaypointBehaviour = lambda: group.mode
        visitor = NS(m_Reserved=False, m_Site=NS(ProposalId='party-lease'),
                     m_Config=NS(RaidSeconds=600), m_Due=0, m_Ends=0)
        owns = compile_authored(HOOK, 'HCXAIBaseRaid', 'HCOwns', base_scope(), modded=False)
        visitor.HCOwns = lambda lease: owns(visitor, lease)
        visitor_owns = compile_authored(PROBES, 'HCCampProbes', 'HCVisitorOwns',
                                       base_scope(s_Visitor=visitor), modded=False)
        raid = NS(HCOwns=lambda lease: reservation == 'warned-raid' and visitor.HCOwns(lease))
        base_owns = compile_authored(CORE, 'HCBaseRaid', 'HCOwns',
            base_scope(s_Port=raid, HCCampProbes=NS(HCVisitorOwns=lambda lease:
                reservation == 'visitor' and visitor_owns(None, lease))), modded=False)
        def reserve(*args):
            visitor.m_Reserved = True
            return True
        visitor.HCReserve = reserve
        visitor.HCCancel = lambda: setattr(visitor, 'm_Reserved', False)
        visit = compile_authored(HOOK, 'HCAdminVisitorParty', 'HCVisit',
            base_scope(Print=lambda line: None), ('HCReserve', 'HCCancel'), modded=False)
        self.assertTrue(visit(visitor, NS(Commit=lambda now: True), NS(LastVisit=0), 100))
        self.assertTrue(base_owns(None, 'party-lease'))

        # Execute the authored common start body; only engine collaborators and
        # threat/hold/signal effects are synthetic. No DayZ behavior is implied.
        runtime = NS(active=None)
        def hold(binding):
            calls.append('hold')
            group.route = ['situation-route']
            group.mode = 'HALT'
        env = dict(EArray=EArray, runtime=runtime, s_Policy=NS(MaxRouteNodes=32),
            HCProfileOn=lambda profile: True, HCReady=lambda: True,
            HCFind=lambda lease: NS(Patrol=NS(m_Group=group)),
            HCProfileFits=lambda party, profile: True,
            HCW38SituationBinding=lambda: NS(Members=EArray(), Original=EArray()),
            eAIBase=NS(Cast=lambda actor: actor),
            HCThreaten=lambda party, binding: calls.append('threats') or True,
            HCHold=hold, HCSignals=lambda binding: calls.append('signals'),
            HCRaid=lambda party, binding: calls.append('threats') or True,
            HCXConvoyRuntime=NS(HCOffer=lambda binding: None),
            Print=lambda line: None)
        source = (WORLD / 'HCW38SituationRuntime.c').read_text()
        source = source.replace('array<vector> ', 'EArray ').replace(
            'eAIBase member', 'HCActor member').replace('s_Active', 'runtime.active')
        translate(source, 'HCW38SituationRuntime', env, only=('HCBegin',))
        runtime.HCBegin = env['HCBegin']
        runtime.HCSelect = lambda opportunity: 'party-lease'
        scope = base_scope(HCW38SituationRuntime=runtime,
                           HCBaseRaid=NS(HCOwns=lambda lease: base_owns(None, lease)))
        methods = {}
        for method in ('HCSelect', 'HCBegin'):
            base = compile_authored(WORLD / (adapter_name + '.c'), adapter_name,
                                    method, scope, modded=False)
            # Resolve the actual authored class chain, including its pre-fix
            # absence, so RED exercises unguarded behavior rather than parsing.
            if 'modded class ' + adapter_name in HOOK.read_text():
                methods[method] = compile_authored(HOOK, adapter_name, method,
                    dict(scope, super=NS(**{method: lambda row, fn=base: fn(None, row)})))
            else:
                methods[method] = base
        return visitor, group, calls, methods

    def test_reserved_party_is_excluded_from_selection_and_start_until_release(self):
        for adapter in ('HCXAISituationAdapter', 'HCXAITransitAdapter'):
            for reservation in ('visitor', 'warned-raid'):
                for profile in ('survivor', 'threatened-exodus'):
                    with self.subTest(adapter=adapter, reservation=reservation, profile=profile):
                        visitor, group, calls, methods = self.fixture(adapter, reservation)
                        row = NS(Profile=profile, Phase='intent', Lease='party-lease', Id='intent')
                        self.assertEqual('', methods['HCSelect'](None, row))
                        # Direct start must also refuse a lease selected before
                        # the reservation appeared, before any physical effect.
                        self.assertFalse(methods['HCBegin'](None, row))
                        self.assertEqual([], calls)
                        self.assertEqual((['visitor-route'], 7), (group.route, group.mode))
                        visitor.HCCancel()
                        self.assertEqual('party-lease', methods['HCSelect'](None, row))
                        self.assertTrue(methods['HCBegin'](None, row))
                        self.assertEqual(['threats', 'hold', 'signals'], calls)
                        self.assertEqual((['situation-route'], 'HALT'), (group.route, group.mode))

    def test_start_rechecks_reservation_after_successful_selection(self):
        for adapter in ('HCXAISituationAdapter', 'HCXAITransitAdapter'):
            with self.subTest(adapter=adapter):
                visitor, group, calls, methods = self.fixture(adapter, 'visitor')
                row = NS(Profile='survivor', Phase='intent', Lease='party-lease', Id='intent')
                visitor.HCCancel()
                self.assertEqual('party-lease', methods['HCSelect'](None, row))
                visitor.HCReserve()
                self.assertFalse(methods['HCBegin'](None, row))
                self.assertEqual([], calls)
                self.assertEqual((['visitor-route'], 7), (group.route, group.mode))
