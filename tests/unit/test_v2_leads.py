"""One smoke of authored decisions, using explicit synthetic DTOs.

Uses the existing translator unchanged; no engine/replication acceptance.
RED before implementation: AssertionError: False is not true : missing Enforce
lead implementation. Ran 1 test; FAILED (failures=1).
GREEN: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_v2_leads -v
Ran 1 test; OK.
"""
from pathlib import Path
from types import SimpleNamespace as N
import unittest

from tests.unit.test_event_runtime import translate

ROOT = Path(__file__).resolve().parents[2]
LEADS = ROOT / 'mods/HollowCountry/scripts/4_World/Leads/HCLeadModule.c'
NOTES = LEADS.with_name('HCNoteLedger.c')


class LeadsSmoke(unittest.TestCase):
    def test_delayed_place_only_lead_and_world_note_cap(self):
        self.assertTrue(LEADS.is_file(), 'missing Enforce lead implementation')
        env = {'HCLeadPolicy': N(), 'HCWorldLimits': N(NOTES=10)}
        build = translate(LEADS.read_text(), 'Build', env, 'HCLeadPolicy')
        # Position is a synthetic live signal deliberately attached to the fact.
        fact = N(Kind='SHOTS_HEARD', PlaceId='stary-sobor', At=10000,
                 Expires=30000, Position=[6123, 42, 7799])
        lead = N()
        self.assertFalse(build(fact, lead, 'stary-sobor', 'DANGER', 11799))
        self.assertTrue(build(fact, lead, 'stary-sobor', 'DANGER', 11800))
        self.assertEqual('stary-sobor', lead.TargetPlaceId)
        self.assertFalse(hasattr(lead, 'Position'))
        self.assertEqual({'Kind', 'TargetPlaceId', 'Expires', 'TextId'}, set(vars(lead)))
        self.assertFalse(build(fact, N(), '', 'DANGER', 11800))
        self.assertFalse(build(fact, N(), 'stary-sobor', 'DANGER', 30000))
        admit = translate(NOTES.read_text(), 'CanCreate', env, 'HCNoteLedger')
        self.assertTrue(admit(9, 0))
        self.assertFalse(admit(10, 0))
        self.assertFalse(admit(11, 0))
        self.assertFalse(admit(0, 1))


if __name__ == '__main__':
    unittest.main()
