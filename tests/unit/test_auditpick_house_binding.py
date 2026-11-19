"""#144: picker runs use the shared search-house reservations (source contract)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'
BINDING = WORLD / 'World/auditpick_HouseBinding.c'
PICKERS = WORLD / 'World/HCPickers.c'
RESERVE = WORLD / 'Loot/auditsearch_PickerReservations.c'


class PickerHouseBinding(unittest.TestCase):
    def test_default_port_is_search_backed(self):
        text = PICKERS.read_text()
        self.assertIn('m_Houses = new HCPickSearchHousePort;', text)

    def test_port_calls_only_existing_reservation_api(self):
        binding = BINDING.read_text()
        reserve = RESERVE.read_text()
        for name in ('HCReservePicker', 'HCPickerItem', 'HCReleasePicker'):
            self.assertIn('houses.' + name + '(', binding)
            self.assertRegex(reserve, r'\b' + name + r'\(HC|\b' + name + r'\(Player')
        self.assertIn('houses.HCCommitReservation(session)', binding)

    def test_authority_rechecks_live_lease(self):
        body = re.search(r'bool HCValid\(.*?\n    \}', BINDING.read_text(), re.S).group(0)
        for check in ('io.Actor != actor', 'io.HCLive()', 'io.HCActorKey() == actorId', 'io.HCPartyCurrent(trip.m_State)'):
            self.assertIn(check, body)
        self.assertNotIn('Distance', body)


if __name__ == '__main__':
    unittest.main()
