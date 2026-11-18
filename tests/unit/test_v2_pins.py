"""One synthetic source smoke; no DayZ, RPC, or persistence acceptance."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_group_server import EArray
from tests.unit.test_map_layers import EStr, translate

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / 'mods/HollowCountry/scripts/4_World/Groups/HCGroupPins.c'


class V2PinsSmoke(unittest.TestCase):
    def test_named_place_lead_and_group_trail_cap(self):
        self.assertTrue(PINS.exists(), 'Map pin implementation is missing')
        source = PINS.read_text()
        named = NS(Name=EStr('Synthetic town'), Position=[100, 0, 200])
        env = {'HCLeadPolicy': NS(Place=lambda key: named if key == 'town' else None),
               'HCGroupRules': NS(PlaceValid=lambda pin: True),
               'HCGroupPlace': lambda: NS(), 'EArray': EArray}
        translate(source, 'HCGroupPinPolicy', env, only=('LeadPin', 'AddTrail'))
        lead = NS(Id=EStr('received'), TargetPlaceId='town', Expires=200,
                  Position=[9999, 0, 9999])  # Poison actor position is ignored.
        pin = env['LeadPin'](lead, 100)
        self.assertEqual(named.Position, pin.Position)
        self.assertEqual('Synthetic town', pin.Name)
        self.assertEqual(200, pin.HCPinExpiresUtc)
        self.assertIsNone(env['LeadPin'](lead, 200))
        lead.TargetPlaceId = 'unknown'
        self.assertIsNone(env['LeadPin'](lead, 100))
        group = NS(HCTrailPlaceIds=EArray())
        other_group = NS(HCTrailPlaceIds=EArray())
        for index in range(60):
            env['AddTrail'](group, EStr('synthetic-shelter-%d' % index))
        self.assertEqual(48, len(group.HCTrailPlaceIds))
        self.assertFalse(env['AddTrail'](group, group.HCTrailPlaceIds[0]))
        self.assertEqual([], other_group.HCTrailPlaceIds)


if __name__ == '__main__':
    unittest.main()
