"""One synthetic smoke of authored materializer decisions; no DayZ evidence.

Uses the existing syntax adapter without extending it. World facts and the
server clock are explicit synthetic ports; no native spawning is simulated.

RED: AssertionError: False is not true : missing HCWorldMaterializer.c
GREEN: python3 -m unittest tests.unit.test_v2_materializer -v; Ran 1 test; OK.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate
from tests.unit.test_expansion_ai_adapter import A

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCWorldMaterializer.c'


class MaterializerSmoke(unittest.TestCase):
    def test_caps_and_unpolled_proposal_becomes_private_place_trace(self):
        self.assertTrue(SOURCE.is_file(), 'missing HCWorldMaterializer.c')
        source = SOURCE.read_text()
        env = dict(len=len, str=str)
        policy = N(MAX_PROPOSALS=2, MAX_ACTORS=8, MAX_PER_PROPOSAL=4,
                   PROVIDER_TIMEOUT=120)
        env['HCWorldMaterializer'] = policy
        admit = translate(source, 'CanPropose', env, 'HCWorldMaterializer')
        self.assertTrue(admit(0, 0, 4))
        self.assertTrue(admit(1, 4, 4))
        for args in ((2, 8, 1), (2, 2, 1), (1, 7, 2), (0, 0, 5),
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
