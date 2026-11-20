"""Synthetic materializer smokes; no DayZ evidence.

Uses the existing syntax adapter without extending it. World facts and the
server clock are explicit synthetic ports; no native spawning is simulated.

RED: AssertionError: False is not true : missing HCWorldMaterializer.c
GREEN: python3 -m unittest tests.legacy.test_v2_materializer -v; Ran 1 test; OK.

LC-T402 transient follow-up, one added behavioural smoke (2026-11-18):
RED/GREEN command:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.legacy.test_v2_materializer.MaterializerSmoke.test_transient_shared_reservations_refuse_and_bridge_reports_trace -v
RED: AssertionError: missing authored method BudgetProblem
Ran 1 test in 0.002s; FAILED (failures=1).
GREEN: Ran 1 test in 0.004s; OK.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.legacy.test_event_runtime import translate
from tests.legacy.test_expansion_ai_adapter import A, Authored

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'


class MaterializerSmoke(unittest.TestCase):
    def test_transient_shared_reservations_refuse_and_bridge_reports_trace(self):
        # Explicit synthetic director groups/policy; executes authored decisions,
        # never a native spawn, navmesh, observer or provider simulation.
        scripts = ROOT / 'mods/HollowCountryExpansionAI/scripts/4_World'
        sites = (scripts / 'HCXAISites.c').read_text()
        bridge = (scripts / 'HCXMaterializerBridge.c').read_text()
        results = []
        env = dict(A=A, len=len, str=str,
                   HCXAIQualification=N(EncountersEnabled=lambda: True,
                                         ProviderProblem=lambda: ''),
                   HCWorldMaterializer=N(Result=lambda *args: results.append(args)))
        authored = Authored(sites, env)
        director = N(m_Phase='run', m_Policy=N(MaxActiveAI=24, MaxActiveSites=8),
                     m_States=A())
        from tests.legacy.ai_limits_fixture import install
        install(env, MaxLiveGroups=2, MaxLiveAI=8)
        director.BudgetProblem = lambda cap, exclude: authored.call(
            'BudgetProblem', director, cap, exclude)
        director.AdmitTransient = lambda *args: authored.call(
            'AdmitTransient', director, *args)
        env['HCXAISiteDirector'] = N(Active=lambda: director)
        def live(cap):
            return N(Transient=False, Completed=False,
                     Site=N(NumberOfAIMax=cap),
                     Patrol=N(m_Group=N(Count=lambda: 1)))
        director.m_States = A([live(4)])
        self.assertEqual('', director.BudgetProblem(4, None))  # exact 8/2 fits
        # Deferred members reserve their full group cap; pending transients
        # reserve both bodies and a site even before a native group exists.
        pending = N(Transient=True, Completed=False, Materialized=False,
                    Site=N(NumberOfAIMax=4), Patrol=None)
        director.m_States.Insert(pending)
        self.assertNotEqual('', director.BudgetProblem(1, None))
        director.m_States = A([live(8)])  # synthetic body-only boundary
        self.assertNotEqual('', director.BudgetProblem(1, None))
        director.m_States = A([live(1), live(1)])  # site-only boundary
        runtime = N(m_Refused=0)
        proposal = N(Id='synthetic-over-budget', FactionId='travellers',
                     Position=(100., 0., 100.), ActorCap=1)
        Authored(bridge, env).call('Offer', runtime, proposal)
        self.assertEqual([('synthetic-over-budget', False, 0)], results)
        self.assertEqual(1, runtime.m_Refused)

    def test_caps_and_unpolled_proposal_becomes_private_place_trace(self):
        self.assertTrue(SOURCE.is_file(), 'missing HCWorldMaterializer.c')
        source = SOURCE.read_text()
        env = dict(len=len, str=str)
        from tests.legacy.ai_limits_fixture import install
        install(env, MaxMaterialized=2, MaxLiveGroups=2, MaxLiveAI=8)
        policy = N(MAX_PROPOSALS=2, MAX_ACTORS=8, MAX_PER_PROPOSAL=4,
                   PROVIDER_TIMEOUT=120)
        env['HCWorldMaterializer'] = policy
        admit = translate(source, 'CanPropose', env, 'HCWorldMaterializer')
        self.assertTrue(admit(0, 0, 4))
        self.assertTrue(admit(1, 4, 4))
        for args in ((2, 8, 1), (2, 2, 1), (1, 7, 2), (0, 0, 13),
                     (0, 0, 0), (0, -1, 1)):
            self.assertFalse(admit(*args), args)

        facts = []
        world = N(AddFact=lambda kind, place, severity:
                  facts.append((kind, place, severity)) or True)
        env['HCWorldModule'] = N(Get=lambda: world)
        timeout = translate(source, 'NoProvider', env, 'HCWorldMaterializer')
        policy.NoProvider = timeout
        self.assertFalse(timeout(False, 119))
        self.assertTrue(timeout(False, 120))
        self.assertFalse(timeout(True, 600))  # never free a live lease by timeout
        fold = translate(source, 'FoldBack', env, 'HCWorldMaterializer')
        proposal = N(Id='synthetic-proposal', FactionId='travellers',
                     PlaceId='synthetic-place', Position=[100., 0., 100.],
                     ActorCap=4, Kind='PATROL')
        lease = N(Proposal=proposal, Claimed=False, Created=0, Finished=False)
        runtime = N(m_Active=A([lease]), m_Clock=119, m_Traces=0,
                    m_Materialized=0)
        # Run the actual timeout loop; only the array and world-fact sink are
        # synthetic. Resolve uses the authored fold-back and removes its lease.
        def resolve(index, materialized, survivors):
            self.assertTrue(fold(world, runtime.m_Active[index].Proposal,
                                 materialized, survivors))
            runtime.m_Traces += 1
            runtime.m_Active.RemoveOrdered(index)
        runtime.Resolve = resolve
        expire = translate(source, 'Expire', env, 'HCWorldMaterializer', member=True)
        expire(runtime)
        self.assertEqual([], facts)
        runtime.m_Clock = 120
        expire(runtime)
        self.assertEqual([('party_passed', 'synthetic-place', 0)], facts)
        self.assertEqual(0, runtime.m_Active.Count())
        expire(runtime)
        self.assertEqual(1, len(facts))
        self.assertFalse(fold(world, proposal, True, 5))
        self.assertTrue(fold(world, proposal, True, 2))
        self.assertEqual(('travellers_survivors_2_of_4', 'synthetic-place', 1), facts[-1])
        # The only vector in the provider DTO is the ledger place anchor.
        dto = source.split('class HCWorldProposal\n{', 1)[1].split('\n}', 1)[0]
        self.assertEqual(1, dto.count('vector '))
        self.assertNotIn('Player', dto)
        self.assertNotIn('GetPosition', dto)


if __name__ == '__main__':
    unittest.main()
