"""Synthetic observable stance smoke; does not establish DayZ behaviour."""
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

from tests.legacy.test_expansion_ai_adapter import Authored

ROOT = Path(__file__).resolve().parents[2]


class LivingStanceSmoke(unittest.TestCase):
    def test_only_observable_facts_and_lowering_deescalates(self):
        path = ROOT / 'mods/HollowCountry/scripts/4_World/World/HCStancePolicy.c'
        self.assertTrue(path.exists(), 'missing authored HCStancePolicy.c')
        source = path.read_text()
        signature = re.search(r'static int Evaluate\(([^)]*)\)', source).group(1)
        self.assertEqual(signature, 'bool weaponRaised, float distance, bool recentGunfire, int relation')
        policy = SimpleNamespace(WATCH=0, WARN=1)
        authored = Authored(source, {'HCStancePolicy': policy})
        self.assertEqual(authored.call('Evaluate', policy, True, 10., False, 0), policy.WARN)
        for relation in (-1, 0, 1):
            self.assertEqual(authored.call('Evaluate', policy, False, 2., True, relation), policy.WATCH)


if __name__ == '__main__':
    unittest.main()
