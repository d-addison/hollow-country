"""One synthetic rate-policy smoke check; no native radio/audio evidence."""
from pathlib import Path
import unittest

from tests.unit.test_horde_stimulus import compile_method


class MorseSmoke(unittest.TestCase):
    def test_holder_clues_obey_real_time_caps(self):
        allowed = compile_method("../Leads/HCMorseClues.c", "static bool RateAllowed(",
                                 "now, playerAt, recentCount", {})
        # Explicit synthetic UTC seconds and already-pruned rolling-hour counts.
        for now, last, count, expected in (
            (10000, 0, 0, True), (10000, 8201, 0, False),
            (10000, 8200, 5, True), (10000, 8200, 6, False),
            (10000, 10001, 0, False), (0, 0, 0, False),
        ):
            self.assertEqual(expected, allowed(None, now, last, count))
        root = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"
        source = (root / "4_World/Leads/HCMorseClues.c").read_text()
        # HC-20 folds Morse into environmental radio: no holder RPC, no event
        # director coupling, no module registration, an explicit off status.
        self.assertNotIn("rpc.Send(", source)
        self.assertNotIn("HCEventDirector", source)
        self.assertNotIn("Register(new HCMorseClues)", source)
        self.assertIn('m_Status.HCPublish("off", "folded_into_radio")', source)


if __name__ == "__main__":
    unittest.main()
