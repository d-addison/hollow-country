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
        self.assertIn("rpc.Send(player, HCMorseRpc.CLUE, true, identity)", source)
        self.assertIn("radio.IsReceiving()", source)
        self.assertIn("GetQuickBarEntity", source)
        self.assertIn("HCEventDirector.Terminal(record.Status)", source)
        self.assertIn('ledger.AddFact("morse_lead", place, 0)', source)


if __name__ == "__main__":
    unittest.main()
