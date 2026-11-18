"""Every reviewed event anchor has a Guards patrol whose route reaches it (#36, #33).

Surfaced 2026-11-17 by the encounter-binding work: HCXAIEncounters binds an
AI_ENCOUNTER mission only to a qualified patrol with a route point within the
site's ActivationRadius of the event anchor. No shipped route was within reach
of either police event site (coastal nearest about 2965 m, inland about 2126 m),
so both police AI missions would be refused at Start.

TDD record (2026-11-17): RED before the two village patrols were authored:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_expansion_ai_event_reach
failed with "no Guards patrol reaches coastal-police-source" and
"no Guards patrol reaches inland-police-source".

Offline only: authored waypoints are a proxy. The runtime qualifies each route
natively (FindPath chain, SurfaceY heights) and may skip points; the server log
line "site <id> route qualified" is the evidence, not this test.
"""
import json
import math
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVENT_SITES = REPO / 'mods/HollowCountry/scripts/4_World/Events/HCEventSites.c'
AI_SITES = REPO / 'mission/hollow-country/ai/sites.json'
# The route must come close enough that the patrol walks through the event,
# not merely activate somewhere in the surrounding square kilometre.
ROUTE_REACH = 150.0


def event_anchors():
    text = EVENT_SITES.read_text()
    ids = dict(re.findall(r'(\w+)\.Id = "([^"]+)";', text))
    anchors = {}
    for var, x, y, z in re.findall(r'(\w+)\.Position = Vector\(([-\d.]+), ([-\d.]+), ([-\d.]+)\);', text):
        anchors[ids[var]] = (float(x), float(z))
    return anchors


def flat(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class EventAnchorReachTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(AI_SITES.read_text())
        self.anchors = event_anchors()

    def test_event_sites_are_parsed(self):
        self.assertEqual({'coastal-police-source', 'inland-police-source'}, set(self.anchors))

    def test_every_event_anchor_has_a_guards_patrol_route_within_reach(self):
        for site_id, anchor in sorted(self.anchors.items()):
            with self.subTest(event=site_id):
                reaching = []
                for site in self.policy['Sites']:
                    if site['Kind'] != 'patrol' or site['Faction'] != 'Guards':
                        continue
                    gap = min(flat((p[0], p[2]), anchor) for p in site['Waypoints'])
                    if gap <= min(ROUTE_REACH, site['ActivationRadius']):
                        reaching.append(site['Id'])
                self.assertTrue(reaching, 'no Guards patrol reaches ' + site_id)

    def test_a_reaching_patrol_starts_beyond_the_player_spawn_distance(self):
        # Members spawn at the first route point, which must be at least
        # MinPlayerDistance from a player standing at the event anchor.
        for site_id, anchor in sorted(self.anchors.items()):
            for site in self.policy['Sites']:
                if site['Kind'] != 'patrol':
                    continue
                gap = min(flat((p[0], p[2]), anchor) for p in site['Waypoints'])
                if gap > ROUTE_REACH:
                    continue
                first = site['Waypoints'][0]
                with self.subTest(event=site_id, site=site['Id']):
                    self.assertGreaterEqual(flat((first[0], first[2]), anchor),
                                            self.policy['MinPlayerDistance'] + 25)


if __name__ == '__main__':
    unittest.main()
