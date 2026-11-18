"""One synthetic policy smoke test; this does not establish native DayZ behaviour."""
from pathlib import Path
import unittest
from tests.unit.test_horde_stimulus import compile_method

ROOT = Path(__file__).resolve().parents[2]


class CampsSmoke(unittest.TestCase):
    def test_w5_respawn_requires_established_quiet_camp_and_full_cooldown(self):
        # Synthetic scalars execute the authored gate, never engine spawn safety.
        gate = compile_method('../Camps/HCCampTiers.c', 'static bool HCRespawnEligible(',
                              'tier, threat, now, last', {})
        self.assertTrue(gate(None, 1, False, 2000, 0))
        self.assertTrue(gate(None, 3, False, 3800, 2000))
        for args in ((0, False, 3800, 0), (1, True, 3800, 0),
                     (1, False, 3799, 2000), (1, False, 1999, 2000),
                     (1, False, 0, 0)):
            self.assertFalse(gate(None, *args))

    def test_tiers_only_classify_and_probes_refuse_before_day_fourteen(self):
        tier = compile_method('../Camps/HCCampTiers.c', 'static int Evaluate(',
                              'hearth, shelter, storage, flag, food, kitchen, walls, lights, radio', {})
        self.assertEqual([0, 1, 2, 3], [
            tier(None, True, False, False, False, False, False, 0, 0, False),
            tier(None, True, True, True, False, False, False, 0, 0, False),
            tier(None, True, True, True, True, True, True, 0, 0, False),
            tier(None, True, True, True, True, True, True, 3, 2, True)])
        source = (ROOT / 'mods/HollowCountry/scripts/4_World/Camps/HCCampTiers.c').read_text()
        self.assertNotRegex(source, r'\b(?:Create\w*|Transfer|SetHealth|SetAllowDamage|SetQuantity|SetGodMode)\s*\(')
        probe = compile_method('../Camps/HCCampProbes.c', 'static bool Eligible(',
                               'tier, day, now, last, hidden', {})
        for day in range(14):
            self.assertFalse(probe(None, 3, day, 2000000, 0, False))
        self.assertTrue(probe(None, 3, 14, 2000000, 0, False))
        self.assertFalse(probe(None, 2, 14, 2000000, 0, False))
        self.assertFalse(probe(None, 3, 14, 2000000, 1999999, False))
        self.assertFalse(probe(None, 3, 14, 2000000, 0, True))


if __name__ == '__main__':
    unittest.main()
